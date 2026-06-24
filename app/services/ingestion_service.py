import os
import structlog
from datetime import datetime, date, time, timedelta
from typing import Optional, Any
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Channel,
    ChannelCredentials,
    Video,
    VideoStatus,
    MetadataDraft,
    MetadataGenerationType,
    ThumbnailDraft,
    SystemLog,
    LogLevel
)
from app.utils.ffmpeg import get_video_metadata, extract_screenshot
from app.services.metadata_service import MetadataService
from app.services.thumbnail_service import ThumbnailService
from app.services.notification_service import NotificationService

logger = structlog.get_logger()

class IngestionService:
    """Manages the ingestion pipeline for newly detected video files.
    
    Coordinates channel matching, metadata/screenshot extraction, 
    and AI drafting for thumbnail and description before transitioning 
    videos to the staging environment.
    """
    
    def __init__(self):
        self.metadata_service = MetadataService()
        self.thumbnail_service = ThumbnailService()
        self.notification_service = NotificationService()

    async def process_detection(
        self,
        db: AsyncSession,
        filename: str,
        file_path: str,
        file_size_bytes: int,
        channel_name: str
    ) -> Video:
        """Process a newly detected video file from OMV watcher.
        
        Args:
            db: Async database session.
            filename: Video file name.
            file_path: Absolute video path.
            file_size_bytes: Video size in bytes.
            channel_name: Video channel name or folder identifier.
            
        Returns:
            Video: The updated Video database record.
            
        Raises:
            ValueError: If the target active channel cannot be found.
            RuntimeError: If preparation or screenshot extraction fails.
        """
        logger.info(
            "ingestion_started", 
            filename=filename, 
            file_path=file_path, 
            channel_name=channel_name
        )

        # 1. Match Channel (Robust exact and prefix/subdirectory directory match)
        stmt = select(Channel).where(Channel.is_active == True)
        result = await db.execute(stmt)
        active_channels = result.scalars().all()
        
        channel = None
        # Try exact match first (by name or folder_path)
        for chan in active_channels:
            if chan.name == channel_name or chan.folder_path == channel_name:
                channel = chan
                break
                
        # Try prefix/subdirectory match
        if not channel:
            # Sort channels by folder_path length descending to match the most specific directory first
            sorted_chans = sorted(active_channels, key=lambda c: len(c.folder_path or ""), reverse=True)
            for chan in sorted_chans:
                if chan.folder_path and (
                    channel_name.startswith(chan.folder_path) or 
                    chan.folder_path.startswith(channel_name)
                ):
                    channel = chan
                    break
        
        if not channel:
            logger.error("channel_not_found", channel_name=channel_name)
            raise ValueError(f"Active channel matching '{channel_name}' not found.")

        # 2. Idempotency Check: check if already exists
        stmt_video = select(Video).where(Video.file_path == file_path)
        result_video = await db.execute(stmt_video)
        existing_video = result_video.scalar_one_or_none()
        
        if existing_video:
            logger.warning(
                "video_already_exists", 
                file_path=file_path, 
                video_id=existing_video.id, 
                status=existing_video.status
            )
            return existing_video

        # Map channel category/genre to YouTube category ID
        YOUTUBE_CATEGORY_MAP = {
            "Film & Animation": "1",
            "Autos & Vehicles": "2",
            "Music": "10",
            "Pets & Animals": "15",
            "Sports": "17",
            "Travel & Events": "19",
            "Gaming": "20",
            "People & Blogs": "22",
            "Comedy": "23",
            "Entertainment": "24",
            "News & Politics": "25",
            "Howto & Style": "26",
            "Education": "27",
            "Science & Technology": "28",
            "Nonprofits & Activism": "29"
        }
        category_id = channel.category_id or YOUTUBE_CATEGORY_MAP.get(channel.genre, "10")

        # 3. Create Video Entry in DETECTED state
        video = Video(
            channel_id=channel.id,
            filename=filename,
            file_path=file_path,
            file_size_bytes=file_size_bytes,
            status=VideoStatus.DETECTED,
            playlist_id=channel.playlist_id,
            default_language=channel.default_language,
            age_restricted=channel.age_restricted,
            ai_generated=channel.ai_generated,
            category_id=category_id,
            made_for_kids=channel.made_for_kids
        )
        db.add(video)
        await db.commit()
        await db.refresh(video)

        await self._log_event(
            db=db,
            level=LogLevel.INFO,
            service="ingestion",
            event_type="video_detected",
            message=f"Video file '{filename}' detected & registered for channel '{channel.name}'",
            video_id=video.id,
            channel_id=channel.id,
            details={"file_path": file_path, "file_size_bytes": file_size_bytes}
        )

        # 4. Ingest and Prepare the video
        try:
            # Transition to PREPARING
            video.status = VideoStatus.PREPARING
            db.add(video)
            await db.commit()
            await db.refresh(video)

            # A. Extract Video Metadata (ffprobe)
            meta = get_video_metadata(file_path)
            video.duration_seconds = meta.get("duration_seconds", 0)
            video.resolution = meta.get("resolution")
            db.add(video)
            await db.flush()

            # B. Extract frame screenshot
            raw_thumb_dir = os.path.join(channel.folder_path, "thumbnails", "raw")
            os.makedirs(raw_thumb_dir, exist_ok=True)
            screenshot_path = os.path.join(raw_thumb_dir, f"vid_{video.id}_screenshot.jpg")

            logger.info("extracting_screenshot", video_id=video.id, path=screenshot_path)
            success = extract_screenshot(file_path, screenshot_path, video.duration_seconds or 0)
            if not success:
                raise RuntimeError(f"ffmpeg failed to extract screenshot for video ID {video.id}")

            video.screenshot_path = screenshot_path
            db.add(video)
            await db.flush()

            # C. Generate metadata draft
            logger.info("generating_metadata_draft", video_id=video.id)
            draft_data = await self.metadata_service.generate_ai_draft(
                filename=filename,
                channel=channel,
                duration_seconds=video.duration_seconds or 0,
                db=db
            )

            # Check if the channel qualifies for auto-approve:
            # 1. auto_approve is True
            # 2. preset templates are set
            # 3. gcp_project_id is set
            # 4. GCP project credentials exist & active
            qualifies_for_auto_approve = False
            if channel.auto_approve:
                if (channel.preset_title_template and 
                    channel.preset_description_template and 
                    channel.gcp_project_id):
                    # Check for active GCP project credentials
                    stmt_creds = select(ChannelCredentials).where(
                        ChannelCredentials.channel_id == channel.id,
                        ChannelCredentials.gcp_project_id == channel.gcp_project_id,
                        ChannelCredentials.is_active == True
                    )
                    res_creds = await db.execute(stmt_creds)
                    active_credentials = res_creds.scalar_one_or_none()
                    if active_credentials:
                        qualifies_for_auto_approve = True

            metadata_draft = MetadataDraft(
                video_id=video.id,
                version_number=1,
                generation_type=MetadataGenerationType.AUTO,
                title=draft_data["title"],
                description=draft_data["description"],
                tags=draft_data["tags"],
                confidence_score=draft_data["confidence_score"],
                is_approved=qualifies_for_auto_approve,
                approved_by=None,
                approved_at=datetime.utcnow() if qualifies_for_auto_approve else None
            )
            db.add(metadata_draft)

            # Denormalize current draft details onto video model
            video.current_title = draft_data["title"]
            video.current_description = draft_data["description"]
            video.current_tags = draft_data["tags"]
            video.ai_review_note = draft_data.get("ai_review_note")
            db.add(video)
            await db.flush()

            # D. Generate 3 thumbnail draft options
            logger.info("generating_thumbnail_options", video_id=video.id)
            thumbnail_options = await self.thumbnail_service.generate_options(
                screenshot_path=screenshot_path,
                channel_name=channel.name,
                genre=channel.genre,
                style_prompt=channel.thumbnail_style_prompt or "ambient soft lofi artwork",
                video_title=draft_data["title"],
                video_id=video.id,
                channel_folder_path=channel.folder_path
            )

            for opt in thumbnail_options:
                thumb_draft = ThumbnailDraft(
                    video_id=video.id,
                    image_path=opt["image_path"],
                    style_name=opt["style_name"],
                    prompt_used=opt["prompt_used"],
                    confidence_score=opt["confidence_score"],
                    is_selected=opt["is_selected"]
                )
                db.add(thumb_draft)
            await db.flush()

            # E. Transition status and schedule
            if qualifies_for_auto_approve:
                video.status = VideoStatus.APPROVED
                
                # Compute schedule time if not set
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
            else:
                video.status = VideoStatus.STAGING
                
            db.add(video)
            await db.commit()
            await db.refresh(video)

            status_str = "APPROVED" if qualifies_for_auto_approve else "STAGING"
            await self._log_event(
                db=db,
                level=LogLevel.INFO,
                service="ingestion",
                event_type="video_prepared",
                message=f"Video ID {video.id} preparation complete. Status transitioned to {status_str}.",
                video_id=video.id,
                channel_id=channel.id,
                details={
                    "title": draft_data["title"], 
                    "duration": video.duration_seconds,
                    "scheduled_time": str(video.scheduled_time) if video.scheduled_time else None
                }
            )

            # Trigger Telegram notification
            try:
                if qualifies_for_auto_approve:
                    await self.notification_service.notify_video_auto_approved(db, video)
                else:
                    await self.notification_service.notify_video_ready(db, video)
            except Exception as notify_err:
                logger.error("ingestion_notify_failed", video_id=video.id, error=str(notify_err))

            return video

        except Exception as e:
            logger.exception("ingestion_failed", video_id=video.id, error=str(e))
            
            # Rollback current open subtransaction modifications (like failed draft inserts)
            await db.rollback()

            # Update status to ERROR
            video.status = VideoStatus.ERROR
            video.last_error = str(e)
            db.add(video)
            await db.commit()

            # Attempt to write error audit event to system_logs
            try:
                await self._log_event(
                    db=db,
                    level=LogLevel.ERROR,
                    service="ingestion",
                    event_type="preparation_failed",
                    message=f"Preparation failed for video ID {video.id}: {str(e)}",
                    video_id=video.id,
                    channel_id=channel.id,
                    details={"error_detail": str(e)}
                )
            except Exception as log_err:
                logger.error("logging_failure_event_failed", error=str(log_err))
                
            raise RuntimeError(f"Preparation failed for video ID {video.id}: {e}") from e

    async def _log_event(
        self,
        db: AsyncSession,
        level: LogLevel,
        service: str,
        event_type: str,
        message: str,
        video_id: Optional[int] = None,
        channel_id: Optional[int] = None,
        details: Optional[dict[str, Any]] = None
    ) -> None:
        """Helper to insert audit log records directly into database logs."""
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
            await db.commit()
        except Exception as e:
            logger.error("database_log_insert_failed", error=str(e))
            await db.rollback()
