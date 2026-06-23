from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
import structlog
from typing import List, Optional
from datetime import datetime, date, time, timedelta

from app.api.deps import get_db, get_current_user
from app.models.user import User
from app.models.video import Video, VideoStatus
from app.models.channel import Channel
from app.models.metadata_draft import MetadataDraft, MetadataGenerationType
from app.models.thumbnail_draft import ThumbnailDraft
from app.models.system_log import SystemLog, LogLevel
from app.core.redis_client import redis_client
from app.tasks.upload import upload_video_task
from app.schemas.video import VideoDetectRequest, VideoResponse, VideoMetadataUpdate, VideoThumbnailSelect, ThumbnailDraftResponse
from app.services.ingestion_service import IngestionService

logger = structlog.get_logger()
router = APIRouter()
ingestion_service = IngestionService()

async def _log_video_event(
    db: AsyncSession,
    level: LogLevel,
    service: str,
    event_type: str,
    message: str,
    video_id: int,
    channel_id: int,
    user_id: Optional[int] = None,
    details: Optional[dict] = None
) -> None:
    """Helper to log events in the database."""
    log_entry = SystemLog(
        level=level,
        service=service,
        event_type=event_type,
        message=message,
        video_id=video_id,
        channel_id=channel_id,
        user_id=user_id,
        details=details
    )
    db.add(log_entry)
    await db.commit()

@router.post("/detect", response_model=VideoResponse, status_code=status.HTTP_201_CREATED)
async def detect_video(
    payload: VideoDetectRequest,
    db: AsyncSession = Depends(get_db)
) -> VideoResponse:
    """Webhook endpoint triggered by the standalone filewatcher.
    
    Registers the video, triggers metadata and frame extraction, generates AI presets,
    and transitions the state to STAGING.
    """
    logger.info(
        "api_video_detect_received", 
        filename=payload.filename, 
        channel=payload.channel_name
    )
    try:
        video = await ingestion_service.process_detection(
            db=db,
            filename=payload.filename,
            file_path=payload.file_path,
            file_size_bytes=payload.file_size_bytes,
            channel_name=payload.channel_name
        )
        return video
    except ValueError as e:
        logger.warning("api_video_detect_not_found", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except RuntimeError as e:
        logger.exception("api_video_detect_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.get("/", response_model=List[VideoResponse])
async def list_videos(
    channel_id: Optional[int] = Query(None, description="Filter by channel ID"),
    status: Optional[str] = Query(None, description="Filter by video status"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> List[VideoResponse]:
    """Retrieve all video records with optional status and channel filters."""
    logger.info("api_list_videos_called", channel_id=channel_id, status=status, user_id=current_user.id)
    query = select(Video)
    if channel_id:
        query = query.where(Video.channel_id == channel_id)
    if status:
        query = query.where(Video.status == status)
    
    query = query.order_by(Video.created_at.desc())
    res = await db.execute(query)
    return res.scalars().all()

@router.get("/staging", response_model=List[VideoResponse])
async def list_staging_videos(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> List[VideoResponse]:
    """Retrieve all video records currently in STAGING status."""
    logger.info("api_list_staging_called", user_id=current_user.id)
    stmt = select(Video).where(Video.status == VideoStatus.STAGING).order_by(Video.id.desc())
    res = await db.execute(stmt)
    return res.scalars().all()

@router.put("/{id}/metadata", response_model=VideoResponse)
async def update_video_metadata(
    id: int,
    payload: VideoMetadataUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> VideoResponse:
    """Modify draft metadata and create a new version of MetadataDraft."""
    logger.info("api_update_metadata_called", video_id=id, user_id=current_user.id)
    
    # Check if video exists
    stmt = select(Video).where(Video.id == id)
    res = await db.execute(stmt)
    video = res.scalar_one_or_none()
    if not video:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found")
        
    if video.status not in [VideoStatus.STAGING, VideoStatus.DETECTED]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail=f"Cannot edit metadata of a video in status {video.status}"
        )
        
    # Get latest version number
    stmt_version = select(func.max(MetadataDraft.version_number)).where(MetadataDraft.video_id == id)
    res_version = await db.execute(stmt_version)
    max_ver = res_version.scalar() or 0
    next_ver = max_ver + 1
    
    # Create new MetadataDraft
    new_draft = MetadataDraft(
        video_id=id,
        version_number=next_ver,
        generation_type=MetadataGenerationType.MANUAL_EDIT,
        title=payload.title,
        description=payload.description,
        tags=payload.tags,
        confidence_score=100.0,  # Manual edit is 100% confident
        is_approved=False
    )
    db.add(new_draft)
    
    # Denormalize onto video
    video.current_title = payload.title
    video.current_description = payload.description
    video.current_tags = payload.tags
    db.add(video)
    await db.commit()
    await db.refresh(video)
    
    await _log_video_event(
        db=db,
        level=LogLevel.INFO,
        service="metadata",
        event_type="metadata_updated",
        message=f"Metadata draft updated to version {next_ver} by user ID {current_user.id}",
        video_id=video.id,
        channel_id=video.channel_id,
        user_id=current_user.id,
        details={"version": next_ver, "title": payload.title}
    )
    
    return video

@router.get("/{id}/thumbnails", response_model=List[ThumbnailDraftResponse])
async def get_video_thumbnails(
    id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> List[ThumbnailDraftResponse]:
    """Retrieve all thumbnail drafts for a specific video."""
    logger.info("api_get_thumbnails_called", video_id=id, user_id=current_user.id)
    stmt = select(ThumbnailDraft).where(ThumbnailDraft.video_id == id)
    res = await db.execute(stmt)
    return res.scalars().all()

@router.post("/{id}/thumbnail", response_model=VideoResponse)
async def select_video_thumbnail(
    id: int,
    payload: VideoThumbnailSelect,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> VideoResponse:
    """Mark the selected thumbnail draft option as active."""
    logger.info("api_select_thumbnail_called", video_id=id, thumbnail_id=payload.thumbnail_id, user_id=current_user.id)
    
    stmt = select(Video).where(Video.id == id)
    res = await db.execute(stmt)
    video = res.scalar_one_or_none()
    if not video:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found")
        
    # Check if target thumbnail belongs to this video
    stmt_thumb = select(ThumbnailDraft).where(
        ThumbnailDraft.id == payload.thumbnail_id, 
        ThumbnailDraft.video_id == id
    )
    res_thumb = await db.execute(stmt_thumb)
    selected_draft = res_thumb.scalar_one_or_none()
    if not selected_draft:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Thumbnail draft option not found for this video")
        
    # Unselect all other options and select this one
    stmt_all_thumbs = select(ThumbnailDraft).where(ThumbnailDraft.video_id == id)
    all_thumbs_res = await db.execute(stmt_all_thumbs)
    all_thumbs = all_thumbs_res.scalars().all()
    
    for t in all_thumbs:
        t.is_selected = (t.id == payload.thumbnail_id)
        db.add(t)
        
    await db.commit()
    await db.refresh(video)
    
    await _log_video_event(
        db=db,
        level=LogLevel.INFO,
        service="thumbnail",
        event_type="thumbnail_selected",
        message=f"Thumbnail draft ID {payload.thumbnail_id} selected by user ID {current_user.id}",
        video_id=video.id,
        channel_id=video.channel_id,
        user_id=current_user.id,
        details={"thumbnail_id": payload.thumbnail_id, "style_name": selected_draft.style_name}
    )
    
    return video

@router.post("/{id}/approve", response_model=VideoResponse)
async def approve_video(
    id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> VideoResponse:
    """Approve video, calculate scheduling queue date, and dispatch Celery worker task."""
    logger.info("api_approve_video_called", video_id=id, user_id=current_user.id)
    
    lock_key = f"approve:lock:{id}"
    is_locked = await redis_client.set(lock_key, "1", ex=300, nx=True)
    if not is_locked:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Approval operation is currently in progress for this video."
        )
        
    try:
        # Row lock SELECT FOR UPDATE
        stmt = select(Video).where(Video.id == id).with_for_update()
        res = await db.execute(stmt)
        video = res.scalar_one_or_none()
        
        if not video:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found")
            
        if video.status != VideoStatus.STAGING:
            # If already approved, return success/current record to remain idempotent
            if video.status in [VideoStatus.APPROVED, VideoStatus.QUEUED, VideoStatus.UPLOADING, VideoStatus.UPLOADED]:
                return video
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Video is in status '{video.status}' and cannot be approved."
            )
            
        # Get Channel Config
        stmt_chan = select(Channel).where(Channel.id == video.channel_id)
        res_chan = await db.execute(stmt_chan)
        channel = res_chan.scalar_one()
        
        # Scheduling algorithm
        if not video.scheduled_time:
            # Find maximum scheduled time of approved/queued/uploaded videos in the future
            stmt_max = select(func.max(Video.scheduled_time)).where(
                Video.channel_id == video.channel_id,
                Video.scheduled_time >= datetime.now(),
                Video.status.in_([VideoStatus.APPROVED, VideoStatus.QUEUED, VideoStatus.UPLOADING, VideoStatus.UPLOADED])
            )
            res_max = await db.execute(stmt_max)
            max_sched = res_max.scalar()
            
            pref_time = channel.preferred_time or time(10, 0, 0)
            
            if max_sched:
                # Sequence sequentially 1 day after the latest scheduled video
                # Ensure the time matches the preferred time
                scheduled_dt = datetime.combine(max_sched.date(), pref_time) + timedelta(days=1)
            else:
                # Check if today's preferred time is in the future
                today_dt = datetime.combine(date.today(), pref_time)
                if today_dt > datetime.now():
                    scheduled_dt = today_dt
                else:
                    scheduled_dt = today_dt + timedelta(days=1)
                    
            video.scheduled_time = scheduled_dt
            
        # Mark metadata draft as approved
        stmt_meta = select(MetadataDraft).where(MetadataDraft.video_id == id).order_by(MetadataDraft.version_number.desc())
        meta_res = await db.execute(stmt_meta)
        latest_meta = meta_res.scalars().first()
        if latest_meta:
            latest_meta.is_approved = True
            latest_meta.approved_by = current_user.id
            latest_meta.approved_at = datetime.utcnow()
            db.add(latest_meta)
            
        # Transition status
        video.status = VideoStatus.APPROVED
        db.add(video)
        await db.commit()
        await db.refresh(video)
        
        await _log_video_event(
            db=db,
            level=LogLevel.INFO,
            service="approval",
            event_type="video_approved",
            message=f"Video approved and scheduled for {video.scheduled_time} by user ID {current_user.id}",
            video_id=video.id,
            channel_id=video.channel_id,
            user_id=current_user.id,
            details={"scheduled_time": str(video.scheduled_time)}
        )
        
        # Dispatch task to Celery queue asynchronously
        upload_video_task.delay(video.id)
        logger.info("celery_upload_task_dispatched", video_id=video.id)
        
        return video
        
    finally:
        # Release the lock
        await redis_client.delete(lock_key)

@router.post("/{id}/discard", response_model=VideoResponse)
async def discard_video(
    id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> VideoResponse:
    """Discard a video from the pipeline."""
    logger.info("api_discard_video_called", video_id=id, user_id=current_user.id)
    
    stmt = select(Video).where(Video.id == id)
    res = await db.execute(stmt)
    video = res.scalar_one_or_none()
    if not video:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found")
        
    if video.status not in [VideoStatus.STAGING, VideoStatus.DETECTED, VideoStatus.ERROR]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Video in status '{video.status}' cannot be discarded."
        )
        
    video.status = VideoStatus.DISCARDED
    db.add(video)
    await db.commit()
    await db.refresh(video)
    
    await _log_video_event(
        db=db,
        level=LogLevel.WARNING,
        service="approval",
        event_type="video_discarded",
        message=f"Video discarded by user ID {current_user.id}",
        video_id=video.id,
        channel_id=video.channel_id,
        user_id=current_user.id
    )
    
    return video


@router.post("/{id}/retry", response_model=VideoResponse)
async def retry_video(
    id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> VideoResponse:
    """Retry a failed or errored video upload."""
    logger.info("api_retry_video_called", video_id=id, user_id=current_user.id)
    
    stmt = select(Video).where(Video.id == id)
    res = await db.execute(stmt)
    video = res.scalar_one_or_none()
    if not video:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found")
        
    if video.status not in [VideoStatus.FAILED, VideoStatus.ERROR]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Video in status '{video.status}' cannot be retried."
        )
        
    video.status = VideoStatus.APPROVED
    video.retry_count = 0
    video.last_error = None
    db.add(video)
    await db.commit()
    await db.refresh(video)
    
    await _log_video_event(
        db=db,
        level=LogLevel.INFO,
        service="approval",
        event_type="video_retry_initiated",
        message=f"Video retry initiated by user ID {current_user.id}",
        video_id=video.id,
        channel_id=video.channel_id,
        user_id=current_user.id
    )
    
    # Dispatch task to Celery queue asynchronously
    upload_video_task.delay(video.id)
    logger.info("celery_upload_task_dispatched_via_retry", video_id=video.id)
    
    return video

