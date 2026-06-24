"""
Celery maintenance tasks:
- dispatch_scheduled_uploads : every 60s — dispatch approved videos whose scheduled_time has passed
- reset_daily_gcp_quota      : daily 00:01 WIB — reset QUOTA_EXCEEDED projects → ACTIVE
- rotate_system_logs         : weekly Sunday 03:00 — delete logs older than 30 days
- backup_database            : daily 03:00 WIB — mysqldump to NAS backup dir
"""
import os
import subprocess
import structlog
from datetime import datetime, timedelta

from app.tasks.celery_app import celery_app
from app.core.database import SessionLocal
from app.models import Video, VideoStatus, SystemLog, LogLevel
from app.models.gcp_project import GCPProject, GCPProjectStatus

logger = structlog.get_logger()


# ─────────────────────────────────────────────────────────────
# 1. Dispatch Scheduled Uploads
# ─────────────────────────────────────────────────────────────

@celery_app.task(name="app.tasks.maintenance.dispatch_scheduled_uploads")
def dispatch_scheduled_uploads() -> dict:
    """
    Check for APPROVED videos whose scheduled_time <= now and dispatch upload tasks.
    Runs every 60 seconds via Celery Beat.
    """
    from app.tasks.upload import upload_video_task

    dispatched = []
    now = datetime.utcnow()

    with SessionLocal() as db:
        videos = (
            db.query(Video)
            .filter(
                Video.status == VideoStatus.APPROVED,
                Video.scheduled_time <= now,
            )
            .all()
        )

        for video in videos:
            try:
                # Transition to QUEUED immediately to prevent double-dispatch
                video.status = VideoStatus.QUEUED
                db.add(video)
                db.commit()

                upload_video_task.delay(video.id)
                dispatched.append(video.id)
                logger.info(
                    "scheduled_upload_dispatched",
                    video_id=video.id,
                    scheduled_time=str(video.scheduled_time),
                )

                _log(db, LogLevel.INFO, "maintenance",
                     "scheduled_upload_dispatched",
                     f"Dispatched upload for video ID {video.id} (scheduled: {video.scheduled_time})",
                     video_id=video.id, channel_id=video.channel_id)

            except Exception as e:
                db.rollback()
                logger.error("scheduled_dispatch_error", video_id=video.id, error=str(e))

    return {"dispatched_video_ids": dispatched, "count": len(dispatched)}


# ─────────────────────────────────────────────────────────────
# 2. Reset Daily GCP Quota
# ─────────────────────────────────────────────────────────────

@celery_app.task(name="app.tasks.maintenance.reset_daily_gcp_quota")
def reset_daily_gcp_quota() -> dict:
    """
    Reset all QUOTA_EXCEEDED GCP projects back to ACTIVE.
    Runs daily at 00:01 WIB (YouTube quota resets at midnight Pacific time).
    """
    with SessionLocal() as db:
        exhausted = (
            db.query(GCPProject)
            .filter(GCPProject.status == GCPProjectStatus.QUOTA_EXCEEDED)
            .all()
        )
        count = 0
        for proj in exhausted:
            proj.status = GCPProjectStatus.ACTIVE
            db.add(proj)
            count += 1

        if count:
            db.commit()
            logger.info("daily_gcp_quota_reset", projects_reset=count)
            _log(db, LogLevel.INFO, "maintenance",
                 "daily_gcp_quota_reset",
                 f"Reset {count} GCP project(s) from QUOTA_EXCEEDED to ACTIVE.")
        else:
            logger.info("daily_gcp_quota_reset_nothing_to_reset")

    return {"projects_reset": count}


# ─────────────────────────────────────────────────────────────
# 3. Rotate System Logs
# ─────────────────────────────────────────────────────────────

@celery_app.task(name="app.tasks.maintenance.rotate_system_logs")
def rotate_system_logs(days_to_keep: int = 30) -> dict:
    """
    Delete system log entries older than `days_to_keep` days.
    Runs every Sunday at 03:00 WIB.
    """
    cutoff = datetime.utcnow() - timedelta(days=days_to_keep)

    with SessionLocal() as db:
        deleted = (
            db.query(SystemLog)
            .filter(SystemLog.created_at < cutoff)
            .delete(synchronize_session=False)
        )
        db.commit()
        logger.info("system_logs_rotated", deleted=deleted, cutoff=str(cutoff))

    return {"deleted_log_entries": deleted}


# ─────────────────────────────────────────────────────────────
# 4. Database Backup
# ─────────────────────────────────────────────────────────────

@celery_app.task(name="app.tasks.maintenance.backup_database")
def backup_database() -> dict:
    """
    Run mysqldump and compress to NAS backup directory.
    Keeps last 14 days of backups.
    Runs daily at 03:00 WIB.
    """
    from app.core.config import settings

    omv_path = settings.OMV_MOUNT_PATH
    backup_dir = os.path.join(omv_path, "backups", "mysql")
    os.makedirs(backup_dir, exist_ok=True)

    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    backup_file = os.path.join(backup_dir, f"ytagent_{timestamp}.sql.gz")

    # Build mysqldump command piped through gzip
    dump_cmd = [
        "docker", "compose", "exec", "-T", "mysql",
        "mysqldump",
        f"-u{settings.MYSQL_USER}",
        f"-p{settings.MYSQL_PASSWORD}",
        settings.MYSQL_DATABASE,
    ]

    try:
        # Run dump → compress → write to file
        with open(backup_file, "wb") as f_out:
            dump_proc = subprocess.Popen(
                dump_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd="/home/monliev/ytagent",  # docker compose working dir on VPS
            )
            gzip_proc = subprocess.Popen(
                ["gzip"],
                stdin=dump_proc.stdout,
                stdout=f_out,
                stderr=subprocess.PIPE,
            )
            dump_proc.stdout.close()
            gzip_proc.communicate()

        if not os.path.exists(backup_file) or os.path.getsize(backup_file) < 100:
            raise RuntimeError("Backup file is empty or missing after dump.")

        file_size_kb = os.path.getsize(backup_file) // 1024
        logger.info("database_backup_success", file=backup_file, size_kb=file_size_kb)

        # Prune backups older than 14 days
        cutoff = datetime.utcnow() - timedelta(days=14)
        pruned = 0
        for fname in os.listdir(backup_dir):
            fpath = os.path.join(backup_dir, fname)
            if fname.endswith(".sql.gz") and os.path.isfile(fpath):
                mtime = datetime.utcfromtimestamp(os.path.getmtime(fpath))
                if mtime < cutoff:
                    os.remove(fpath)
                    pruned += 1

        return {
            "status": "success",
            "backup_file": backup_file,
            "size_kb": file_size_kb,
            "pruned_old_backups": pruned,
        }

    except Exception as e:
        logger.error("database_backup_failed", error=str(e))
        # Try to clean up partial file
        if os.path.exists(backup_file):
            os.remove(backup_file)
        return {"status": "error", "error": str(e)}


# ─────────────────────────────────────────────────────────────
# Internal helper
# ─────────────────────────────────────────────────────────────

def _log(
    db,
    level: LogLevel,
    service: str,
    event_type: str,
    message: str,
    video_id=None,
    channel_id=None,
    details=None,
) -> None:
    """Insert a SystemLog entry synchronously (Celery context)."""
    try:
        entry = SystemLog(
            level=level,
            service=service,
            event_type=event_type,
            message=message,
            video_id=video_id,
            channel_id=channel_id,
            details=details,
        )
        db.add(entry)
        db.commit()
    except Exception as e:
        logger.error("maintenance_log_insert_failed", error=str(e))
        db.rollback()


@celery_app.task(name="app.tasks.maintenance.check_copyright_claims")
def check_copyright_claims() -> dict:
    """
    Check recently uploaded videos on active channels for copyright claims/restrictions.
    If claims are found, pause the channel's queue to protect it and alert the supervisor.
    """
    from app.core.config import settings
    from app.services.upload_service_sync import UploadServiceSync
    from app.utils.telegram_api import object_telegram_api
    from app.models.channel import Channel
    import asyncio
    
    upload_service = UploadServiceSync()
    paused_channels = []
    
    with SessionLocal() as db:
        # Get active channels
        channels = db.query(Channel).filter(Channel.is_active == True).all()
        
        for channel in channels:
            # Get last 5 uploaded videos
            videos = (
                db.query(Video)
                .filter(
                    Video.channel_id == channel.id,
                    Video.status == VideoStatus.UPLOADED,
                    Video.youtube_video_id != None
                )
                .order_by(Video.uploaded_at.desc())
                .limit(5)
                .all()
            )
            
            if not videos:
                continue
                
            try:
                # Instantiate YouTube client for this channel
                youtube = upload_service.get_youtube_client(db, channel.id, channel.gcp_project_id)
                video_ids = [v.youtube_video_id for v in videos]
                
                # Fetch video status from YouTube API
                response = youtube.videos().list(
                    part="contentDetails,status",
                    id=",".join(video_ids)
                ).execute()
                
                items = response.get("items", [])
                for item in items:
                    vid_id = item.get("id")
                    status_info = item.get("status", {})
                    content_details = item.get("contentDetails", {})
                    
                    has_claim = False
                    reason = ""
                    
                    # Check for region restrictions
                    region_restriction = content_details.get("regionRestriction", {})
                    if "blocked" in region_restriction:
                        has_claim = True
                        reason = "Blocked in countries: " + ", ".join(region_restriction["blocked"][:5])
                        
                    # Check rejection reason
                    rejection_reason = status_info.get("rejectionReason")
                    if rejection_reason in ["copyright", "termsOfUse", "trademark"]:
                        has_claim = True
                        reason = f"Rejected due to {rejection_reason}"
                        
                    if has_claim:
                        # Pause channel
                        channel.is_active = False
                        db.add(channel)
                        db.commit()
                        
                        # Find DB video record
                        db_video = db.query(Video).filter(Video.youtube_video_id == vid_id).first()
                        if db_video:
                            db_video.notes = f"Copyright issue detected: {reason}"
                            db.add(db_video)
                            db.commit()
                            
                        # Log critical event
                        _log(db, LogLevel.CRITICAL, "maintenance", "copyright_claim_detected",
                             f"PAUSED CHANNEL '{channel.name}' due to copyright check on video {vid_id}: {reason}",
                             video_id=db_video.id if db_video else None, channel_id=channel.id)
                             
                        # Send Telegram Notification
                        alert_msg = (
                            f"🚨 <b>CRITICAL: COPYRIGHT CLAIM DETECTED</b>\n\n"
                            f"Channel: <b>{channel.name}</b> has been <b>PAUSED</b> (is_active = False).\n"
                            f"Video ID: <code>{vid_id}</code>\n"
                            f"Issue: <i>{reason}</i>\n\n"
                            f"Please check YouTube Studio immediately."
                        )
                        try:
                            loop = asyncio.get_event_loop()
                            if loop.is_running():
                                loop.create_task(object_telegram_api.send_message(
                                    chat_id=settings.SUPERVISOR_TELEGRAM_ID,
                                    text=alert_msg
                                ))
                            else:
                                asyncio.run(object_telegram_api.send_message(
                                    chat_id=settings.SUPERVISOR_TELEGRAM_ID,
                                    text=alert_msg
                                ))
                        except Exception as tg_err:
                            logger.error("failed_to_send_telegram_copyright_alert", error=str(tg_err))
                            
                        paused_channels.append(channel.name)
                        break
                        
            except Exception as e:
                logger.error("copyright_check_failed_for_channel", channel_id=channel.id, error=str(e))
                
    return {"status": "complete", "paused_channels": paused_channels, "count": len(paused_channels)}


@celery_app.task(name="app.tasks.maintenance.send_daily_hermes_report")
def send_daily_hermes_report() -> dict:
    """
    Daily scheduled task that compiles and sends channel briefings to the supervisor via Telegram.
    Includes views gained in the last 24h, top performing video, staging and queue counts.
    """
    from app.core.config import settings
    from app.utils.telegram_api import object_telegram_api
    from app.models import Channel, Video, VideoStatus, AnalyticsRecord
    import asyncio
    from sqlalchemy import func

    reports_sent = []

    with SessionLocal() as db:
        channels = db.query(Channel).filter(Channel.is_active == True).all()
        if not channels:
            logger.info("send_daily_hermes_report_no_active_channels")
            return {"status": "complete", "reports_sent": 0}

        yesterday = datetime.utcnow() - timedelta(days=1)

        for channel in channels:
            try:
                # 1. Views Gained in the last 24h
                views_gained = db.query(func.sum(AnalyticsRecord.views_gained)).filter(
                    AnalyticsRecord.channel_id == channel.id,
                    AnalyticsRecord.recorded_at >= yesterday
                ).scalar() or 0

                # 2. Top Performing Video in last 24h
                top_video_query = (
                    db.query(
                        AnalyticsRecord.video_id,
                        func.sum(AnalyticsRecord.views_gained).label("total_gained")
                    )
                    .filter(
                        AnalyticsRecord.channel_id == channel.id,
                        AnalyticsRecord.recorded_at >= yesterday
                    )
                    .group_by(AnalyticsRecord.video_id)
                    .order_by(func.sum(AnalyticsRecord.views_gained).desc())
                    .first()
                )

                top_video_title = "N/A"
                top_video_views = 0
                if top_video_query and top_video_query.video_id:
                    v = db.query(Video).filter(Video.id == top_video_query.video_id).first()
                    if v:
                        top_video_title = v.title or v.filename or "Untitled"
                        top_video_views = top_video_query.total_gained

                # 3. Current Queue Count (APPROVED + QUEUED)
                queue_count = db.query(Video).filter(
                    Video.channel_id == channel.id,
                    Video.status.in_([VideoStatus.APPROVED, VideoStatus.QUEUED])
                ).count()

                # 4. Current Staging Count (STAGING + DETECTED)
                staging_count = db.query(Video).filter(
                    Video.channel_id == channel.id,
                    Video.status.in_([VideoStatus.STAGING, VideoStatus.DETECTED])
                ).count()

                # Format Hermes Persona Briefing
                message = (
                    f"🤖 <b>Hermes AI Channel Briefing</b>\n"
                    f"Channel: <b>{channel.name}</b>\n"
                    f"Date: {datetime.utcnow().strftime('%Y-%m-%d')}\n\n"
                    f"📈 <b>Performance (Last 24h):</b>\n"
                    f"• Views Gained: <code>{views_gained:,}</code>\n"
                    f"• Top Video: <i>{top_video_title}</i> (+{top_video_views:,} views)\n\n"
                    f"📦 <b>Staging & Queue Status:</b>\n"
                    f"• In Staging: <code>{staging_count}</code> video(s) awaiting review.\n"
                    f"• In Queue: <code>{queue_count}</code> video(s) scheduled/queued.\n\n"
                    f"<i>Hermes Suggestion: Keep staging clean to ensure consistent uploads!</i>"
                )

                # Send via Telegram
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(object_telegram_api.send_message(
                        chat_id=settings.SUPERVISOR_TELEGRAM_ID,
                        text=message
                    ))
                else:
                    asyncio.run(object_telegram_api.send_message(
                        chat_id=settings.SUPERVISOR_TELEGRAM_ID,
                        text=message
                    ))

                reports_sent.append(channel.name)

            except Exception as e:
                logger.error("failed_to_send_daily_hermes_report", channel_id=channel.id, error=str(e))

    return {"status": "complete", "reports_sent": len(reports_sent), "channels": reports_sent}


@celery_app.task(name="app.tasks.maintenance.auto_patrol_queue_integrity")
def auto_patrol_queue_integrity() -> dict:
    """
    Patrol task to scan all APPROVED and QUEUED videos.
    If a video file is missing on OMV:
    1. Mark video status as ERROR.
    2. Log the event.
    3. Send Telegram alert to supervisor.
    4. Auto-shift the scheduled_time of all subsequent videos in the channel's queue.
    """
    from app.utils.telegram_api import object_telegram_api
    from app.core.config import settings
    import asyncio

    missing_count = 0
    shifted_videos = []

    with SessionLocal() as db:
        # Fetch all approved and queued videos that have a scheduled time
        videos = (
            db.query(Video)
            .filter(
                Video.status.in_([VideoStatus.APPROVED, VideoStatus.QUEUED]),
                Video.scheduled_time.is_not(None)
            )
            .order_by(Video.scheduled_time.asc())
            .all()
        )

        for video in videos:
            # Check if file path exists
            if not os.path.exists(video.file_path):
                # Detected missing file!
                missing_count += 1
                orig_scheduled_time = video.scheduled_time
                channel_id = video.channel_id
                
                # 1. Update video status
                video.status = VideoStatus.ERROR
                video.last_error = f"File missing from OMV path: {video.file_path}"
                db.add(video)
                db.commit()

                # 2. Log event
                _log(db, LogLevel.ERROR, "maintenance", "queue_file_missing",
                     f"Video ID {video.id} file is missing from OMV. Removed from active queue and marked as ERROR.",
                     video_id=video.id, channel_id=channel_id)

                # 3. Fetch remaining approved/queued videos scheduled AFTER this video
                stmt_subsequent = (
                    db.query(Video)
                    .filter(
                        Video.channel_id == channel_id,
                        Video.status.in_([VideoStatus.APPROVED, VideoStatus.QUEUED]),
                        Video.scheduled_time > orig_scheduled_time
                    )
                    .order_by(Video.scheduled_time.asc())
                    .all()
                )

                # 4. Auto-shift scheduled times:
                # Video_k scheduled time becomes the scheduled_time of the video that was scheduled right before it!
                # We start with the original scheduled time of the deleted video as the target slot.
                next_slot = orig_scheduled_time
                for sub_video in stmt_subsequent:
                    old_time = sub_video.scheduled_time
                    sub_video.scheduled_time = next_slot
                    db.add(sub_video)
                    shifted_videos.append({"id": sub_video.id, "from": str(old_time), "to": str(next_slot)})
                    next_slot = old_time
                
                db.commit()

                # 5. Send Telegram alert
                alert_msg = (
                    f"⚠️ <b>WARNING: OMV FILE MISSING</b>\n\n"
                    f"Video file was deleted or missing from OMV mount.\n"
                    f"<b>ID:</b> <code>{video.id}</code>\n"
                    f"<b>Title:</b> {video.current_title or video.filename}\n"
                    f"<b>Missing Path:</b> <code>{video.file_path}</code>\n\n"
                    f"This video has been marked as <b>ERROR</b> and removed from queue. "
                    f"Subsequent upload schedules for this channel have been automatically shifted up by 1 slot."
                )

                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        loop.create_task(object_telegram_api.send_message(
                            chat_id=settings.SUPERVISOR_TELEGRAM_ID,
                            text=alert_msg
                        ))
                    else:
                        asyncio.run(object_telegram_api.send_message(
                            chat_id=settings.SUPERVISOR_TELEGRAM_ID,
                            text=alert_msg
                        ))
                except Exception as tg_err:
                    logger.error("failed_to_send_telegram_missing_file_alert", error=str(tg_err))

    return {
        "status": "complete",
        "missing_videos_detected": missing_count,
        "shifted_videos_count": len(shifted_videos),
        "shifted_videos": shifted_videos
    }
