from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import structlog

from app.api.v1.videos import router as videos_router
from app.api.v1.auth import router as auth_router
from app.api.v1.channels import router as channels_router
from app.api.v1.logs import router as logs_router
from app.api.v1.telegram import router as telegram_router
from app.api.v1.settings import router as settings_router
from app.api.v1.system import router as system_router
from app.utils.telegram_api import object_telegram_api
from app.core.config import settings

logger = structlog.get_logger()

WEBHOOK_URL = "https://ytagent.my.id/api/v1/telegram/webhook"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Register Telegram webhook on startup."""
    logger.info("app_startup_begin")

    # Register Telegram webhook (skip if using placeholder token)
    if "Placeholder" not in settings.TELEGRAM_BOT_TOKEN:
        result = await object_telegram_api.set_webhook(WEBHOOK_URL)
        if result.get("ok"):
            logger.info("telegram_webhook_registered_on_startup", url=WEBHOOK_URL)
        else:
            logger.warning("telegram_webhook_registration_failed_on_startup", result=result)
    else:
        logger.info("telegram_webhook_skipped_placeholder_token")

    yield

    logger.info("app_shutdown")


app = FastAPI(
    title="YTAgent API",
    description="AI orchestrator for YouTube multi-channel management",
    version="1.0.0",
    lifespan=lifespan,
)

# Security headers middleware
from fastapi import Request

@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    return response

# Configure CORS for Dashboard integration
cors_origins = [origin.strip() for origin in settings.CORS_ORIGINS.split(",") if origin.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API Gateways V1
app.include_router(auth_router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(channels_router, prefix="/api/v1/channels", tags=["channels"])
app.include_router(logs_router, prefix="/api/v1/logs", tags=["logs"])
app.include_router(telegram_router, prefix="/api/v1/telegram", tags=["telegram"])
app.include_router(videos_router, prefix="/api/v1/videos", tags=["videos"])
app.include_router(settings_router, prefix="/api/v1/settings", tags=["settings"])
app.include_router(system_router, prefix="/api/v1/system", tags=["system"])


@app.get("/health")
async def health_check():
    """Health check endpoint to verify API and dependencies are alive."""
    logger.info("health_check_called", status="ok")
    return {"status": "ok", "version": "1.0.0"}
