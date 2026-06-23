from celery import Celery
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
        "app.tasks.analytics.*": {"queue": "analytics"},
        "app.tasks.maintenance.*": {"queue": "maintenance"},
    }
)

# Autodiscover tasks from app package
celery_app.autodiscover_tasks(["app"])
