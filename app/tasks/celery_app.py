from celery import Celery
from celery.schedules import crontab
from app.core.config import settings

celery_app = Celery("ytagent")

celery_app.conf.update(
    broker_url=settings.REDIS_URL,
    result_backend=settings.REDIS_URL,
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone=settings.TZ,
    enable_utc=True,

    # CRITICAL: Strict sequential execution requires worker concurrency = 1
    worker_concurrency=1,

    # Late acknowledgment so tasks are retried or logged if worker crashes
    task_acks_late=True,
    worker_prefetch_multiplier=1,

    # Task routing
    task_routes={
        "app.tasks.upload.*": {"queue": "upload"},
        "app.tasks.maintenance.*": {"queue": "maintenance"},
        "app.tasks.analytics.*": {"queue": "analytics"},
    },

    # ── Celery Beat periodic schedule ─────────────────────────────────────────
    # All times in Asia/Jakarta (WIB) because timezone=settings.TZ is set above.
    beat_schedule={
        # Every 60 seconds: dispatch APPROVED videos whose scheduled_time has passed
        "dispatch-scheduled-uploads": {
            "task": "app.tasks.maintenance.dispatch_scheduled_uploads",
            "schedule": 60.0,
        },
        # Daily at 00:01 WIB: reset GCP projects from QUOTA_EXCEEDED → ACTIVE
        # (YouTube quota resets daily, so we mirror that)
        "reset-daily-gcp-quota": {
            "task": "app.tasks.maintenance.reset_daily_gcp_quota",
            "schedule": crontab(hour=0, minute=1),
        },
        # Daily at 03:00 WIB: dump MySQL database to NAS backup directory
        "backup-database": {
            "task": "app.tasks.maintenance.backup_database",
            "schedule": crontab(hour=3, minute=0),
        },
        # Every Sunday at 04:00 WIB: delete system log entries older than 30 days
        "rotate-system-logs": {
            "task": "app.tasks.maintenance.rotate_system_logs",
            "schedule": crontab(hour=4, minute=0, day_of_week=0),
        },
        # Every 6 hours: scan uploaded videos for copyright claims and auto-pause channel on alert
        "check-copyright-claims": {
            "task": "app.tasks.maintenance.check_copyright_claims",
            "schedule": crontab(hour="*/6", minute=0),
        },
        # Every 6 hours: pull video-level analytics and update DB
        "sync-youtube-analytics": {
            "task": "app.tasks.analytics.sync_youtube_analytics",
            "schedule": crontab(hour="*/6", minute=30),
        },
    },
)

# Autodiscover tasks from app package
celery_app.autodiscover_tasks(["app.tasks"])
