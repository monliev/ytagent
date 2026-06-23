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
