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

KEYS = [
    "telegram_bot_token", "supervisor_telegram_id", "cf_ai_url",
    "recaptcha_site_key", "recaptcha_secret_key",
    "sftp_host", "sftp_port", "sftp_user", "sftp_password", "sftp_base_path",
]

SENSITIVE_KEYS = {"recaptcha_secret_key", "sftp_password", "telegram_bot_token"}


def mask_value(key: str, val: str | None) -> str | None:
    if not val:
        return val
    if key in SENSITIVE_KEYS:
        if len(val) > 4:
            return "*" * (len(val) - 4) + val[-4:]
        return "****"
    return val


async def _load_all_settings(db: AsyncSession) -> dict:
    """Load all setting keys from DB and return as plain dict."""
    stmt = select(SystemSetting).where(SystemSetting.key.in_(KEYS))
    res = await db.execute(stmt)
    return {r.key: r.value for r in res.scalars().all()}


@router.get("/", response_model=SystemSettingsResponse)
async def get_settings(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> SystemSettingsResponse:
    """Retrieve all global settings (censoring sensitive ones)."""
    logger.info("api_get_settings_called", user_id=current_user.id)

    db_records = await _load_all_settings(db)

    resolved = {
        "telegram_bot_token": mask_value(
            "telegram_bot_token",
            db_records.get("telegram_bot_token") or settings.TELEGRAM_BOT_TOKEN
        ),
        "supervisor_telegram_id": (
            int(db_records["supervisor_telegram_id"])
            if db_records.get("supervisor_telegram_id")
            else settings.SUPERVISOR_TELEGRAM_ID
        ),
        "cf_ai_url": db_records.get("cf_ai_url") or settings.CF_AI_URL,
        "recaptcha_site_key": db_records.get("recaptcha_site_key") or "",
        "recaptcha_secret_key": mask_value(
            "recaptcha_secret_key", db_records.get("recaptcha_secret_key") or ""
        ),
        "sftp_host": db_records.get("sftp_host") or "",
        "sftp_port": int(db_records["sftp_port"]) if db_records.get("sftp_port") else 22,
        "sftp_user": db_records.get("sftp_user") or "",
        "sftp_password": mask_value("sftp_password", db_records.get("sftp_password") or ""),
        "sftp_base_path": db_records.get("sftp_base_path") or "/",
    }

    return SystemSettingsResponse(**resolved)


@router.post("/", response_model=SystemSettingsResponse)
async def update_settings(
    payload: SystemSettingsUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> SystemSettingsResponse:
    """Update global settings."""
    logger.info("api_update_settings_called", user_id=current_user.id)

    import json
    updates = payload.model_dump(exclude_unset=True)
    logger.info("Incoming settings update payload: %s", json.dumps({k: mask_value(k, str(v)) for k, v in updates.items()}))

    for key, new_val in updates.items():
        if new_val is None:
            logger.info("Setting %s is None, skipping", key)
            continue
        # Skip if placeholder mask was posted back
        if isinstance(new_val, str) and new_val != "":
            if set(new_val) <= {"*"} or (key in SENSITIVE_KEYS and new_val.startswith("****") and "*" in new_val):
                logger.info("Setting %s matches mask placeholder (%s), skipping overwrite", key, new_val)
                continue

        stmt = select(SystemSetting).where(SystemSetting.key == key)
        res = await db.execute(stmt)
        record = res.scalar_one_or_none()

        val_str = str(new_val)
        if record:
            logger.info("Updating existing setting in DB: %s = %s (previously: %s)", key, mask_value(key, val_str), mask_value(key, record.value))
            record.value = val_str
        else:
            logger.info("Inserting new setting in DB: %s = %s", key, mask_value(key, val_str))
            record = SystemSetting(key=key, value=val_str)
            db.add(record)

    await db.commit()
    logger.info("api_settings_updated_successfully", user_id=current_user.id)
    return await get_settings(db, current_user)


@router.get("/public", response_model=PublicSettingsResponse)
async def get_public_settings(
    db: AsyncSession = Depends(get_db)
) -> PublicSettingsResponse:
    """Retrieve public configurations (e.g. reCAPTCHA site key for login page)."""
    stmt = select(SystemSetting).where(SystemSetting.key == "recaptcha_site_key")
    res = await db.execute(stmt)
    record = res.scalar_one_or_none()
    site_key = record.value if record else None
    return PublicSettingsResponse(recaptcha_site_key=site_key)


@router.get("/watch-folders", response_model=list[str])
async def get_watch_folders(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> list[str]:
    """
    List available watch folders.

    Priority:
    1. SFTP scan using saved sftp_host / sftp_user / sftp_password / sftp_base_path
       (if sftp_host is configured in DB settings)
    2. Local filesystem scan of OMV_MOUNT_PATH from env/config
    """
    import os

    logger.info("api_get_watch_folders_called", user_id=current_user.id)

    db_records = await _load_all_settings(db)
    sftp_host = db_records.get("sftp_host") or ""

    if sftp_host:
        # --- SFTP scan ---
        sftp_port = int(db_records.get("sftp_port") or 22)
        sftp_user = db_records.get("sftp_user") or ""
        sftp_pass = db_records.get("sftp_password") or ""
        sftp_base = db_records.get("sftp_base_path") or "/"

        try:
            import paramiko  # type: ignore
        except ImportError:
            logger.error("paramiko_not_installed")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="SFTP library (paramiko) is not installed on the server."
            )

        try:
            transport = paramiko.Transport((sftp_host, sftp_port))
            transport.connect(username=sftp_user, password=sftp_pass)
            sftp = paramiko.SFTPClient.from_transport(transport)
            dirs = []
            try:
                import stat as stat_mod
                # Level 1 scan
                entries1 = sftp.listdir_attr(sftp_base)
                for e1 in entries1:
                    if stat_mod.S_ISDIR(e1.st_mode) and not e1.filename.startswith("."):
                        p1 = f"{sftp_base.rstrip('/')}/{e1.filename}"
                        dirs.append(p1)
                        # Level 2 scan
                        try:
                            entries2 = sftp.listdir_attr(p1)
                            for e2 in entries2:
                                if stat_mod.S_ISDIR(e2.st_mode) and not e2.filename.startswith("."):
                                    p2 = f"{p1}/{e2.filename}"
                                    dirs.append(p2)
                        except Exception:
                            pass
            finally:
                sftp.close()
                transport.close()

            dirs.sort()
            logger.info("sftp_watch_folders_listed", count=len(dirs))
            return dirs

        except Exception as e:
            logger.error("sftp_watch_folders_error", error=str(e))
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"SFTP connection failed: {str(e)}"
            )

    else:
        # --- Local mount scan ---
        mount_path = settings.OMV_MOUNT_PATH
        if not os.path.exists(mount_path):
            logger.warning("omv_mount_path_not_exists", path=mount_path)
            return []
        try:
            dirs = []
            # Level 1 scan
            for d1 in os.listdir(mount_path):
                p1 = os.path.join(mount_path, d1)
                if os.path.isdir(p1) and not d1.startswith("."):
                    dirs.append(p1)
                    # Level 2 scan
                    try:
                        for d2 in os.listdir(p1):
                            p2 = os.path.join(p1, d2)
                            if os.path.isdir(p2) and not d2.startswith("."):
                                dirs.append(p2)
                    except Exception:
                        pass
            dirs.sort()
            logger.info("local_watch_folders_listed", count=len(dirs))
            return dirs
        except Exception as e:
            logger.error("failed_to_list_watch_folders", error=str(e))
            return []
