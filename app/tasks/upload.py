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
from app.models.channel import Channel
from app.utils.telegram_api import object_telegram_api
from app.services.settings_service import get_supervisor_telegram_id_sync
import asyncio

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

        # Concurrency check via per-channel Redis lock (allows distinct channels to upload in parallel)
        lock = redis_sync_client.lock(f"youtube_upload_lock:channel:{video.channel_id}", timeout=1800)
        acquired = lock.acquire(blocking=False)
        if not acquired:
            logger.info("celery_upload_channel_lock_busy", video_id=video_id, channel_id=video.channel_id)
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

                try:
                    channel = db.query(Channel).filter(Channel.id == video.channel_id).first()
                    channel_name = channel.name if channel else "Unknown Channel"
                    supervisor_id = get_supervisor_telegram_id_sync(db)
                    
                    success_msg = (
                        f"✅ <b>YOUTUBE UPLOAD SUCCESSFUL</b>\n\n"
                        f"<b>Channel:</b> {channel_name}\n"
                        f"<b>Title:</b> {video.current_title or video.filename}\n"
                        f"<b>YouTube Link:</b> https://youtu.be/{youtube_video_id}\n\n"
                        f"Video has been successfully uploaded and is now live/processing on YouTube!"
                    )
                    
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        loop.create_task(object_telegram_api.send_message(chat_id=supervisor_id, text=success_msg))
                    else:
                        asyncio.run(object_telegram_api.send_message(chat_id=supervisor_id, text=success_msg))
                except Exception as tg_err:
                    logger.error("failed_to_send_upload_success_notification", error=str(tg_err))

                return youtube_video_id
                
            except Exception as e:
                db.rollback()
                logger.exception("celery_upload_step_failed", video_id=video_id, error=str(e))
                
                video.retry_count += 1
                video.last_error = str(e)
                
                # Check for OAuth / Credential errors
                err_str = str(e).lower()
                if "oauth" in err_str or "invalid_grant" in err_str or "credential" in err_str:
                    try:
                        channel = db.query(Channel).filter(Channel.id == video.channel_id).first()
                        channel_name = channel.name if channel else "Unknown Channel"
                        supervisor_id = get_supervisor_telegram_id_sync(db)
                        
                        oauth_msg = (
                            f"🔴 <b>ALERT: CHANNEL OAUTH DISCONNECTED</b>\n\n"
                            f"Connection to YouTube OAuth for channel <b>{channel_name}</b> failed during upload task!\n"
                            f"<b>Error:</b> <code>{str(e)}</code>\n\n"
                            f"Please go to Channel Settings on the dashboard, disconnect and reconnect Google Auth to resolve scheduled upload failures."
                        )
                        
                        sent_lock_key = f"lock:oauth_alert_sent:{video.channel_id}"
                        if not redis_sync_client.get(sent_lock_key):
                            redis_sync_client.set(sent_lock_key, "1", ex=3600)  # 1 hour expiry
                            loop = asyncio.get_event_loop()
                            if loop.is_running():
                                loop.create_task(object_telegram_api.send_message(chat_id=supervisor_id, text=oauth_msg))
                            else:
                                asyncio.run(object_telegram_api.send_message(chat_id=supervisor_id, text=oauth_msg))
                    except Exception as tg_err:
                        logger.error("failed_to_send_oauth_realtime_notification", error=str(tg_err))

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

                    try:
                        channel = db.query(Channel).filter(Channel.id == video.channel_id).first()
                        channel_name = channel.name if channel else "Unknown Channel"
                        supervisor_id = get_supervisor_telegram_id_sync(db)
                        
                        failed_msg = (
                            f"❌ <b>YOUTUBE UPLOAD FAILED PERMANENTLY</b>\n\n"
                            f"<b>Channel:</b> {channel_name}\n"
                            f"<b>Title:</b> {video.current_title or video.filename}\n"
                            f"<b>Error:</b> <code>{str(e)}</code>\n\n"
                            f"The video upload failed after maximum retry attempts. Please review the issue on the dashboard."
                        )
                        
                        loop = asyncio.get_event_loop()
                        if loop.is_running():
                            loop.create_task(object_telegram_api.send_message(chat_id=supervisor_id, text=failed_msg))
                        else:
                            asyncio.run(object_telegram_api.send_message(chat_id=supervisor_id, text=failed_msg))
                    except Exception as tg_err:
                        logger.error("failed_to_send_upload_failure_notification", error=str(tg_err))

                    return None
        finally:
            try:
                redis_sync_client.delete(f"video:{video_id}:progress")
            except Exception:
                pass
            try:
                lock.release()
                logger.info("celery_upload_lock_released", video_id=video_id)
            except Exception as le:
                logger.warning("celery_upload_lock_release_failed", error=str(le))
