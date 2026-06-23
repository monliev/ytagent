from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import structlog

from app.api.deps import get_db, get_current_user
from app.models.user import User
from app.models.system_setting import SystemSetting
from app.schemas.settings import SystemSettingsResponse, SystemSettingsUpdate, PublicSettingsResponse
from app.core.config import settings

logger = structlog.get_logger()
router = APIRouter()

KEYS = ["telegram_bot_token", "supervisor_telegram_id", "cf_ai_url", "recaptcha_site_key", "recaptcha_secret_key"]

def mask_value(key: str, val: str | None) -> str | None:
    if not val:
        return val
    if key == "telegram_bot_token":
        # Keep last 4 chars, mask rest
        if len(val) > 4:
            return "*" * (len(val) - 4) + val[-4:]
        return "****"
    if key in ("recaptcha_secret_key", "telegram_bot_token"):
        return "********"
    return val

@router.get("/", response_model=SystemSettingsResponse)
async def get_settings(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> SystemSettingsResponse:
    """Retrieve all global settings (sensoring sensitive ones)."""
    logger.info("api_get_settings_called", user_id=current_user.id)
    
    # Query database values
    stmt = select(SystemSetting).where(SystemSetting.key.in_(KEYS))
    res = await db.execute(stmt)
    db_records = {r.key: r.value for r in res.scalars().all()}

    # Resolve settings (fallback to config/env)
    resolved = {}
    resolved["telegram_bot_token"] = db_records.get("telegram_bot_token") or settings.TELEGRAM_BOT_TOKEN
    
    supervisor_id = db_records.get("supervisor_telegram_id")
    resolved["supervisor_telegram_id"] = int(supervisor_id) if supervisor_id else settings.SUPERVISOR_TELEGRAM_ID
    
    resolved["cf_ai_url"] = db_records.get("cf_ai_url") or settings.CF_AI_URL
    resolved["recaptcha_site_key"] = db_records.get("recaptcha_site_key") or ""
    resolved["recaptcha_secret_key"] = db_records.get("recaptcha_secret_key") or ""

    # Mask sensitive credentials
    return SystemSettingsResponse(
        telegram_bot_token=mask_value("telegram_bot_token", resolved["telegram_bot_token"]),
        supervisor_telegram_id=resolved["supervisor_telegram_id"],
        cf_ai_url=resolved["cf_ai_url"],
        recaptcha_site_key=resolved["recaptcha_site_key"],
        recaptcha_secret_key=mask_value("recaptcha_secret_key", resolved["recaptcha_secret_key"])
    )

@router.post("/", response_model=SystemSettingsResponse)
async def update_settings(
    payload: SystemSettingsUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> SystemSettingsResponse:
    """Update global settings."""
    logger.info("api_update_settings_called", user_id=current_user.id)
    
    updates = payload.model_dump(exclude_unset=True)
    
    for key, new_val in updates.items():
        if new_val is None:
            continue
            
        # Skip if placeholder mask was posted
        if isinstance(new_val, str) and "*" in new_val:
            continue
            
        stmt = select(SystemSetting).where(SystemSetting.key == key)
        res = await db.execute(stmt)
        record = res.scalar_one_or_none()
        
        val_str = str(new_val)
        if record:
            record.value = val_str
        else:
            record = SystemSetting(key=key, value=val_str)
            db.add(record)
            
    await db.commit()
    logger.info("api_settings_updated", user_id=current_user.id)
    return await get_settings(db, current_user)

@router.get("/public", response_model=PublicSettingsResponse)
async def get_public_settings(
    db: AsyncSession = Depends(get_db)
) -> PublicSettingsResponse:
    """Retrieve public configurations (e.g. reCAPTCHA site key for login validation)."""
    stmt = select(SystemSetting).where(SystemSetting.key == "recaptcha_site_key")
    res = await db.execute(stmt)
    record = res.scalar_one_or_none()
    site_key = record.value if record else None
    return PublicSettingsResponse(recaptcha_site_key=site_key)

@router.get("/watch-folders", response_model=list[str])
async def get_watch_folders(
    current_user: User = Depends(get_current_user)
) -> list[str]:
    """Retrieve subdirectories of the OMV NAS mount path."""
    import os
    logger.info("api_get_watch_folders_called", user_id=current_user.id)
    path = settings.OMV_MOUNT_PATH
    if not os.path.exists(path):
        logger.warning("omv_mount_path_not_exists", path=path)
        return []
    try:
        dirs = [d for d in os.listdir(path) if os.path.isdir(os.path.join(path, d))]
        return sorted(dirs)
    except Exception as e:
        logger.error("failed_to_list_watch_folders", error=str(e))
        return []
