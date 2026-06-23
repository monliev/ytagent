from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import structlog

from app.api.v1.videos import router as videos_router
from app.api.v1.auth import router as auth_router
from app.api.v1.channels import router as channels_router
from app.api.v1.logs import router as logs_router
from app.api.v1.telegram import router as telegram_router

logger = structlog.get_logger()

app = FastAPI(
    title="YTAgent API",
    description="AI orchestrator for YouTube multi-channel management",
    version="1.0.0",
)

# Configure CORS for Dashboard integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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

@app.get("/health")
async def health_check():
    """Health check endpoint to verify API and dependencies are alive."""
    logger.info("health_check_called", status="ok")
    return {"status": "ok", "version": "1.0.0"}
