from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel
import os
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
from app.schemas.video import VideoDetectRequest, VideoResponse, VideoMetadataUpdate, VideoThumbnailSelect, ThumbnailDraftResponse, AIEnhancementResponse
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
    
    # Save hybrid overrides
    if payload.playlist_id is not None:
        video.playlist_id = payload.playlist_id
    if payload.default_language is not None:
        video.default_language = payload.default_language
    if payload.age_restricted is not None:
        video.age_restricted = payload.age_restricted
    if payload.ai_generated is not None:
        video.ai_generated = payload.ai_generated
    if payload.category_id is not None:
        video.category_id = payload.category_id
    if payload.made_for_kids is not None:
        video.made_for_kids = payload.made_for_kids

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


@router.post("/{id}/enhance", response_model=AIEnhancementResponse)
async def enhance_video_metadata(
    id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> AIEnhancementResponse:
    """Enhance and optimize Title and Description using Cloudflare AI LLM."""
    logger.info("api_enhance_metadata_called", video_id=id, user_id=current_user.id)
    
    # 1. Fetch Video and its Channel
    stmt = select(Video).where(Video.id == id)
    res = await db.execute(stmt)
    video = res.scalar_one_or_none()
    if not video:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found")
        
    stmt_chan = select(Channel).where(Channel.id == video.channel_id)
    res_chan = await db.execute(stmt_chan)
    channel = res_chan.scalar_one()

    default_response = AIEnhancementResponse(
        titles=[video.current_title or video.filename],
        description=video.current_description or "",
        tags=video.current_tags or []
    )

    from app.core.config import settings
    import httpx
    import json
    from app.models.system_setting import SystemSetting

    # Fetch AI URL from db settings, fallback to environment variable config
    stmt_setting = select(SystemSetting).where(SystemSetting.key == "cf_ai_url")
    res_setting = await db.execute(stmt_setting)
    setting_rec = res_setting.scalar_one_or_none()
    ai_url = (setting_rec.value if setting_rec else None) or settings.CF_AI_URL

    # Fetch AI Token from db settings, fallback to environment variable config
    stmt_token = select(SystemSetting).where(SystemSetting.key == "cf_ai_token")
    res_token = await db.execute(stmt_token)
    token_rec = res_token.scalar_one_or_none()
    ai_token = (token_rec.value if token_rec else None) or settings.CF_AI_TOKEN

    logger.info("Loaded AI URL: %s | AI Token loaded: %s (length: %d)", 
                ai_url, 
                "Yes" if ai_token else "No", 
                len(ai_token) if ai_token else 0)

    if not ai_url or "dummy" in ai_url:
        logger.info("Hermes AI is not configured or dummy URL is active. AI URL: %s", ai_url)
        return default_response

    prompt = f"""
    You are Hermes, a professional YouTube SEO strategist.
    Optimize the metadata for this video:
    Channel Name: {channel.name}
    Channel Niche/Genre: {channel.genre}
    Current Title: {video.current_title or video.filename}
    Current Description: {video.current_description or ''}
    Current Tags: {', '.join(video.current_tags or [])}

    Your tasks:
    1. Generate exactly 3 highly clickable, optimized alternative Title variations (each maximum 100 characters) in Indonesian.
    2. Rewrite/enhance the video Description to make it more engaging and optimized for YouTube's SEO algorithm. Keep it in Indonesian, include a hook, summary, and relevant tags.
    3. Generate a refined list of 10-15 Tags (keywords) to boost search discovery.

    Format your output strictly as a JSON object:
    {{
      "titles": ["Variation 1", "Variation 2", "Variation 3"],
      "description": "...",
      "tags": ["tag1", "tag2", ...]
    }}
    """
    try:
        url = f"{ai_url.rstrip('/')}/chat/completions"
        payload = {
            "model": "hermes",
            "messages": [
                {"role": "system", "content": "You are a professional YouTube SEO strategist named Hermes."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.7
        }
        
        headers = {"Content-Type": "application/json"}
        if ai_token:
            headers["Authorization"] = f"Bearer {ai_token}"
            
        def mask_auth_value(val: str | None) -> str | None:
            if not val:
                return val
            if len(val) > 11 and val.startswith("Bearer "):
                token = val[7:]
                return "Bearer " + "*" * (len(token) - 4) + token[-4:]
            return "****"
            
        logger.info("Sending request to Hermes AI URL: %s with headers: %s and payload model: %s", 
                    url, 
                    {k: (mask_auth_value(v) if k == "Authorization" else v) for k, v in headers.items()}, 
                    payload["model"])
            
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                url,
                json=payload,
                headers=headers,
                timeout=18.0
            )
        logger.info("Hermes AI responded with status_code: %d", resp.status_code)
        if resp.status_code == 200:
            ai_data = resp.json()
            logger.info("Hermes AI response json: %s", json.dumps(ai_data))
            if "choices" in ai_data and len(ai_data["choices"]) > 0:
                text = ai_data["choices"][0]["message"]["content"]
                logger.info("Hermes AI response content text: %s", text)
                start_idx = text.find("{")
                end_idx = text.rfind("}")
                if start_idx != -1 and end_idx != -1:
                    parsed = json.loads(text[start_idx:end_idx+1])
                    logger.info("Hermes AI parsed json successfully: %s", json.dumps(parsed))
                    
                    # Extract titles robustly (fallback to single 'title' key or list format)
                    titles_val = parsed.get("titles") or parsed.get("title")
                    if isinstance(titles_val, str):
                        extracted_titles = [titles_val]
                    elif isinstance(titles_val, list):
                        extracted_titles = [str(t)[:100] for t in titles_val if t]
                    else:
                        extracted_titles = default_response.titles
                        
                    # Extract description robustly
                    extracted_desc = parsed.get("description", default_response.description)
                    
                    # Extract tags robustly
                    tags_val = parsed.get("tags")
                    if isinstance(tags_val, list):
                        extracted_tags = [str(t) for t in tags_val if t][:15]
                    else:
                        extracted_tags = default_response.tags
                        
                    return AIEnhancementResponse(
                        titles=extracted_titles[:3] or default_response.titles,
                        description=extracted_desc,
                        tags=extracted_tags
                    )
                else:
                    logger.warning("Hermes AI response text did not contain JSON delimiters '{' and '}'")
            else:
                logger.warning("Hermes AI choices are empty or missing in response JSON")
        else:
            logger.warning("Hermes AI request failed. Status code: %d, Response: %s", resp.status_code, resp.text)
    except Exception as e:
        logger.warning("cf_ai_enhance_metadata_failed", video_id=video.id, error=str(e), exc_info=True)
        
    return default_response

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


@router.get("/thumbnails/{thumbnail_id}/image")
async def get_thumbnail_image(
    thumbnail_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Retrieve the actual binary image file for a thumbnail draft."""
    stmt = select(ThumbnailDraft).where(ThumbnailDraft.id == thumbnail_id)
    res = await db.execute(stmt)
    draft = res.scalar_one_or_none()
    if not draft:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Thumbnail draft not found")
        
    if not draft.image_path or not os.path.exists(draft.image_path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Thumbnail image file not found on disk")
        
    return FileResponse(draft.image_path)


@router.get("/{id}/screenshot")
async def get_video_screenshot(
    id: int,
    db: AsyncSession = Depends(get_db)
):
    """Retrieve the actual video screenshot image file."""
    stmt = select(Video).where(Video.id == id)
    res = await db.execute(stmt)
    video = res.scalar_one_or_none()
    if not video:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found")
        
    if not video.screenshot_path or not os.path.exists(video.screenshot_path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Screenshot file not found on disk")
        
    return FileResponse(video.screenshot_path)


class BulkVideoAction(BaseModel):
    video_ids: list[int]


@router.post("/bulk-approve", status_code=status.HTTP_200_OK)
async def bulk_approve_videos(
    payload: BulkVideoAction,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Bulk approve staging videos and dispatch upload tasks."""
    logger.info("api_bulk_approve_videos_called", count=len(payload.video_ids), user_id=current_user.id)
    
    results = {"success": [], "failed": []}
    
    for video_id in payload.video_ids:
        lock_key = f"approve:lock:{video_id}"
        is_locked = await redis_client.set(lock_key, "1", ex=300, nx=True)
        if not is_locked:
            results["failed"].append({"id": video_id, "detail": "Approval in progress"})
            continue
            
        try:
            stmt = select(Video).where(Video.id == video_id).with_for_update()
            res = await db.execute(stmt)
            video = res.scalar_one_or_none()
            
            if not video:
                results["failed"].append({"id": video_id, "detail": "Video not found"})
                continue
                
            if video.status != VideoStatus.STAGING:
                if video.status in [VideoStatus.APPROVED, VideoStatus.QUEUED, VideoStatus.UPLOADING, VideoStatus.UPLOADED]:
                    results["success"].append(video_id)
                else:
                    results["failed"].append({"id": video_id, "detail": f"Invalid status: {video.status}"})
                continue
                
            # Get Channel
            stmt_chan = select(Channel).where(Channel.id == video.channel_id)
            res_chan = await db.execute(stmt_chan)
            channel = res_chan.scalar_one()
            
            # Scheduling calculation
            if not video.scheduled_time:
                stmt_max = select(func.max(Video.scheduled_time)).where(
                    Video.channel_id == video.channel_id,
                    Video.scheduled_time >= datetime.now(),
                    Video.status.in_([VideoStatus.APPROVED, VideoStatus.QUEUED, VideoStatus.UPLOADING, VideoStatus.UPLOADED])
                )
                res_max = await db.execute(stmt_max)
                max_sched = res_max.scalar()
                
                pref_time = channel.preferred_time or time(10, 0, 0)
                
                if max_sched:
                    scheduled_dt = datetime.combine(max_sched.date(), pref_time) + timedelta(days=1)
                else:
                    today_dt = datetime.combine(date.today(), pref_time)
                    if today_dt > datetime.now():
                        scheduled_dt = today_dt
                    else:
                        scheduled_dt = today_dt + timedelta(days=1)
                        
                video.scheduled_time = scheduled_dt
                
            # Mark latest metadata approved
            stmt_meta = select(MetadataDraft).where(MetadataDraft.video_id == video_id).order_by(MetadataDraft.version_number.desc())
            meta_res = await db.execute(stmt_meta)
            latest_meta = meta_res.scalars().first()
            if latest_meta:
                latest_meta.is_approved = True
                latest_meta.approved_by = current_user.id
                latest_meta.approved_at = datetime.utcnow()
                db.add(latest_meta)
                
            video.status = VideoStatus.APPROVED
            db.add(video)
            await db.commit()
            
            await _log_video_event(
                db=db,
                level=LogLevel.INFO,
                service="approval",
                event_type="video_approved_bulk",
                message=f"Video approved via bulk action by user ID {current_user.id}",
                video_id=video.id,
                channel_id=video.channel_id,
                user_id=current_user.id
            )
            
            # Dispatch Celery task
            upload_video_task.delay(video.id)
            results["success"].append(video_id)
            
        except Exception as e:
            results["failed"].append({"id": video_id, "detail": str(e)})
            logger.error("bulk_approve_video_error", video_id=video_id, error=str(e))
        finally:
            await redis_client.delete(lock_key)
            
    return results


@router.post("/bulk-discard", status_code=status.HTTP_200_OK)
async def bulk_discard_videos(
    payload: BulkVideoAction,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Bulk discard staging/detected/errored videos."""
    logger.info("api_bulk_discard_videos_called", count=len(payload.video_ids), user_id=current_user.id)
    
    results = {"success": [], "failed": []}
    
    for video_id in payload.video_ids:
        try:
            stmt = select(Video).where(Video.id == video_id)
            res = await db.execute(stmt)
            video = res.scalar_one_or_none()
            
            if not video:
                results["failed"].append({"id": video_id, "detail": "Video not found"})
                continue
                
            if video.status not in [VideoStatus.STAGING, VideoStatus.DETECTED, VideoStatus.ERROR]:
                results["failed"].append({"id": video_id, "detail": f"Cannot discard video in status: {video.status}"})
                continue
                
            video.status = VideoStatus.DISCARDED
            db.add(video)
            await db.commit()
            
            await _log_video_event(
                db=db,
                level=LogLevel.WARNING,
                service="approval",
                event_type="video_discarded_bulk",
                message=f"Video discarded via bulk action by user ID {current_user.id}",
                video_id=video.id,
                channel_id=video.channel_id,
                user_id=current_user.id
            )
            results["success"].append(video_id)
            
        except Exception as e:
            results["failed"].append({"id": video_id, "detail": str(e)})
            
    return results



