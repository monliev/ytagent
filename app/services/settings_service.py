from typing import Any, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.models.system_setting import SystemSetting
from app.core.config import settings

async def get_db_setting_async(db: AsyncSession, key: str, default: Any = None) -> Any:
    """Retrieve a setting value asynchronously from the database."""
    try:
        stmt = select(SystemSetting).where(SystemSetting.key == key)
        res = await db.execute(stmt)
        record = res.scalar_one_or_none()
        return record.value if (record and record.value is not None) else default
    except Exception:
        return default

def get_db_setting_sync(db: Session, key: str, default: Any = None) -> Any:
    """Retrieve a setting value synchronously from the database (e.g. Celery workers)."""
    try:
        record = db.query(SystemSetting).filter(SystemSetting.key == key).first()
        return record.value if (record and record.value is not None) else default
    except Exception:
        return default

async def get_telegram_bot_token_async(db: AsyncSession) -> str:
    return await get_db_setting_async(db, "telegram_bot_token", settings.TELEGRAM_BOT_TOKEN)

def get_telegram_bot_token_sync(db: Session) -> str:
    return get_db_setting_sync(db, "telegram_bot_token", settings.TELEGRAM_BOT_TOKEN)

async def get_supervisor_telegram_id_async(db: AsyncSession) -> int:
    val = await get_db_setting_async(db, "supervisor_telegram_id")
    if val is not None:
        try:
            return int(val)
        except (ValueError, TypeError):
            pass
    return settings.SUPERVISOR_TELEGRAM_ID

def get_supervisor_telegram_id_sync(db: Session) -> int:
    val = get_db_setting_sync(db, "supervisor_telegram_id")
    if val is not None:
        try:
            return int(val)
        except (ValueError, TypeError):
            pass
    return settings.SUPERVISOR_TELEGRAM_ID
