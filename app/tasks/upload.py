import redis
import structlog
from datetime import datetime
from typing import Optional, Any
from sqlalchemy.orm import Session

from app.core.config import settings
from app.tasks.celery_app import celery_app
from app.core.database import SessionLocal
from app.models import Video, VideoStatus, SystemLog, LogLevel
from app.services.upload_service_sync import UploadServiceSync

logger = structlog.get_logger()
redis_sync_client = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)

def _log_event_sync(
    db: Session,
    level: LogLevel,
    service: str,
    event_type: str,
    message: str,
    video_id: Optional[int] = None,
    channel_id: Optional[int] = None,
    details: Optional[dict[str, Any]] = None
) -> None:
    """Helper to log event synchronously in the database."""
    try:
        log_entry = SystemLog(
            level=level,
            service=service,
            event_type=event_type,
            message=message,
            video_id=video_id,
            channel_id=channel_id,
            details=details
        )
        db.add(log_entry)
        db.commit()
    except Exception as e:
        logger.error("sync_database_log_insert_failed", error=str(e))
        db.rollback()

@celery_app.task(bind=True, max_retries=5)
def upload_video_task(self, video_id: int) -> Optional[str]:
    """Celery task executing video uploads to YouTube sequentially.
    
    Manages transitions: APPROVED -> UPLOADING -> UPLOADED / FAILED.
    Retries transient failures with exponential backoff.
    """
    logger.info("celery_upload_task_triggered", video_id=video_id)
    
    with SessionLocal() as db:
        video = db.query(Video).filter(Video.id == video_id).first()
        if not video:
            logger.error("celery_upload_video_not_found", video_id=video_id)
            return None
            
        if video.status not in [VideoStatus.APPROVED, VideoStatus.QUEUED]:
            logger.warning(
                "celery_upload_invalid_status", 
                video_id=video_id, 
                current_status=video.status
            )
            return None

        # Concurrency check via Redis lock
        lock = redis_sync_client.lock("youtube_upload_global_lock", timeout=1800)
        acquired = lock.acquire(blocking=False)
        if not acquired:
            logger.info("celery_upload_lock_busy", video_id=video_id)
            raise self.retry(countdown=60)

        try:
            # Transition to UPLOADING
            video.status = VideoStatus.UPLOADING
            db.add(video)
            db.commit()
            
            _log_event_sync(
                db=db,
                level=LogLevel.INFO,
                service="upload",
                event_type="upload_started",
                message=f"Starting YouTube video upload for video ID {video_id}",
                video_id=video.id,
                channel_id=video.channel_id
            )

            try:
                uploader = UploadServiceSync()
                youtube_video_id = uploader.execute_upload(db, video)
                
                # Transition to UPLOADED
                video.status = VideoStatus.UPLOADED
                video.youtube_video_id = youtube_video_id
                video.uploaded_at = datetime.utcnow()
                db.add(video)
                db.commit()
                
                _log_event_sync(
                    db=db,
                    level=LogLevel.INFO,
                    service="upload",
                    event_type="upload_success",
                    message=f"Successfully uploaded video to YouTube. YouTube ID: {youtube_video_id}",
                    video_id=video.id,
                    channel_id=video.channel_id,
                    details={"youtube_video_id": youtube_video_id}
                )
                return youtube_video_id
                
            except Exception as e:
                db.rollback()
                logger.exception("celery_upload_step_failed", video_id=video_id, error=str(e))
                
                video.retry_count += 1
                video.last_error = str(e)
                
                if self.request.retries < self.max_retries:
                    # Requeue status back to QUEUED for celery retry
                    video.status = VideoStatus.QUEUED
                    db.add(video)
                    db.commit()
                    
                    _log_event_sync(
                        db=db,
                        level=LogLevel.WARNING,
                        service="upload",
                        event_type="upload_transient_failure",
                        message=f"Upload failed temporarily: {str(e)}. Retrying ({self.request.retries + 1}/5)...",
                        video_id=video.id,
                        channel_id=video.channel_id
                    )
                    
                    # Retry celery task with exponential backoff (e.g. 60s, 120s, 240s...)
                    countdown = 60 * (2 ** self.request.retries)
                    raise self.retry(exc=e, countdown=countdown)
                else:
                    # Transition to FAILED state
                    video.status = VideoStatus.FAILED
                    db.add(video)
                    db.commit()
                    
                    _log_event_sync(
                        db=db,
                        level=LogLevel.CRITICAL,
                        service="upload",
                        event_type="upload_failed",
                        message=f"Upload failed permanently after maximum retries. Error: {str(e)}",
                        video_id=video.id,
                        channel_id=video.channel_id,
                        details={"error": str(e)}
                    )
                    return None
        finally:
            try:
                lock.release()
                logger.info("celery_upload_lock_released", video_id=video_id)
            except Exception as le:
                logger.warning("celery_upload_lock_release_failed", error=str(le))
