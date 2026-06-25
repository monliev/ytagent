from fastapi import APIRouter, Depends, HTTPException, status, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
import structlog
from typing import Optional
from datetime import datetime, date, time, timedelta
from pydantic import BaseModel, Field

from app.api.deps import get_db
from app.core.config import settings
from app.core.redis_client import redis_client
from app.models.user import User, UserRole
from app.models.video import Video, VideoStatus
from app.models.channel import Channel
from app.models.metadata_draft import MetadataDraft
from app.models.system_log import SystemLog, LogLevel
from app.tasks.upload import upload_video_task
from app.utils.telegram_api import object_telegram_api

logger = structlog.get_logger()
router = APIRouter()

# --- Pydantic Schemas for Telegram Webhook Update ---
class TelegramUser(BaseModel):
    id: int
    is_bot: bool
    first_name: str
    username: Optional[str] = None

class TelegramChat(BaseModel):
    id: int
    type: str

class TelegramMessage(BaseModel):
    message_id: int
    chat: TelegramChat
    text: Optional[str] = None

class TelegramCallbackQuery(BaseModel):
    id: str
    from_user: TelegramUser = Field(..., alias="from")
    message: Optional[TelegramMessage] = None
    data: Optional[str] = None

class TelegramUpdate(BaseModel):
    update_id: int
    callback_query: Optional[TelegramCallbackQuery] = None


async def _log_telegram_event(
    db: AsyncSession,
    level: LogLevel,
    event_type: str,
    message: str,
    video_id: Optional[int] = None,
    channel_id: Optional[int] = None,
    user_id: Optional[int] = None,
    details: Optional[dict] = None
) -> None:
    """Helper to log event in the database."""
    log_entry = SystemLog(
        level=level,
        service="telegram_bot",
        event_type=event_type,
        message=message,
        video_id=video_id,
        channel_id=channel_id,
        user_id=user_id,
        details=details
    )
    db.add(log_entry)
    await db.commit()



WEBHOOK_URL = "https://ytagent.my.id/api/v1/telegram/webhook"


@router.get("/webhook-info")
async def get_webhook_info(db: AsyncSession = Depends(get_db)):
    """Return current Telegram webhook configuration (token, URL, pending updates)."""
    info = await object_telegram_api.get_webhook_info(db=db)
    return info


@router.post("/register-webhook")
async def register_webhook(db: AsyncSession = Depends(get_db)):
    """Manually (re-)register the Telegram webhook. Useful after token changes."""
    result = await object_telegram_api.set_webhook(WEBHOOK_URL, db=db)
    if result.get("ok"):
        return {"status": "registered", "url": WEBHOOK_URL}
    return {"status": "failed", "detail": result}


@router.post("/webhook", status_code=status.HTTP_200_OK)
async def telegram_webhook(
    update: TelegramUpdate,
    x_telegram_bot_api_secret_token: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db)
):
    """Webhook callback endpoint registered with Telegram to receive button clicks."""
    # Verify Telegram Webhook Secret Token to prevent spoofing
    import hashlib
    expected_token = hashlib.sha256(settings.SECRET_KEY.encode("utf-8")).hexdigest()
    if x_telegram_bot_api_secret_token != expected_token:
        logger.warning(
            "telegram_webhook_invalid_secret_token", 
            received=x_telegram_bot_api_secret_token
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Invalid webhook secret token."
        )

    logger.info("telegram_webhook_received", update_id=update.update_id)
    
    cb = update.callback_query
    if not cb:
        # We only care about callback query clicks (Approve/Discard/Edit)
        return {"status": "ignored"}
        
    user_tg_id = cb.from_user.id
    callback_id = cb.id
    data = cb.data
    
    # 1. Authorize sender (must match SUPERVISOR_TELEGRAM_ID or exist in database as SUPERVISOR/ADMIN)
    stmt_user = select(User).where(User.telegram_id == user_tg_id, User.is_active == True)
    res_user = await db.execute(stmt_user)
    user = res_user.scalar_one_or_none()
    
    is_authorized = (user_tg_id == settings.SUPERVISOR_TELEGRAM_ID) or (user and user.role in [UserRole.SUPERVISOR, UserRole.ADMIN])
    if not is_authorized:
        logger.warning("telegram_webhook_unauthorized_access", telegram_id=user_tg_id, callback_data=data)
        await object_telegram_api.answer_callback_query(
            callback_query_id=callback_id, 
            text="❌ Unauthorized! You are not a supervisor."
        )
        return {"status": "unauthorized"}
        
    if not data or ":" not in data:
        await object_telegram_api.answer_callback_query(callback_query_id=callback_id, text="❌ Invalid query data.")
        return {"status": "invalid_data"}
        
    action, video_id_str = data.split(":", 1)
    if not video_id_str.isdigit():
        await object_telegram_api.answer_callback_query(callback_query_id=callback_id, text="❌ Invalid video ID.")
        return {"status": "invalid_video_id"}
        
    video_id = int(video_id_str)
    
    # Load user DB id if exists, or use None
    user_id = user.id if user else None
    
    # Execute corresponding action
    if action == "edit":
        # Edit cannot be processed over telegram buttons, direct them to dashboard
        await object_telegram_api.answer_callback_query(
            callback_query_id=callback_id,
            text="✏️ Open the dashboard to edit video details."
        )
        return {"status": "ok"}
        
    elif action == "approve":
        # Acquire Redis Lock
        lock_key = f"approve:lock:{video_id}"
        is_locked = await redis_client.set(lock_key, "1", ex=300, nx=True)
        if not is_locked:
            await object_telegram_api.answer_callback_query(
                callback_query_id=callback_id,
                text="⚠️ Operation in progress. Please wait."
            )
            return {"status": "locked"}
            
        try:
            # DB SELECT FOR UPDATE
            stmt_vid = select(Video).where(Video.id == video_id).with_for_update()
            res_vid = await db.execute(stmt_vid)
            video = res_vid.scalar_one_or_none()
            
            if not video:
                await object_telegram_api.answer_callback_query(callback_query_id=callback_id, text="❌ Video not found.")
                return {"status": "video_not_found"}
                
            if video.status != VideoStatus.STAGING:
                if video.status in [VideoStatus.APPROVED, VideoStatus.QUEUED, VideoStatus.UPLOADING, VideoStatus.UPLOADED]:
                    await object_telegram_api.answer_callback_query(
                        callback_query_id=callback_id,
                        text="✅ Video was already approved."
                    )
                    # Update Telegram message just in case
                    if cb.message:
                        new_text = f"{cb.message.text}\n\n✅ <b>APPROVED (already processed)</b>"
                        await object_telegram_api.edit_message_text(
                            chat_id=cb.message.chat.id,
                            message_id=cb.message.message_id,
                            text=new_text,
                            reply_markup=None
                        )
                    return {"status": "already_approved"}
                    
                await object_telegram_api.answer_callback_query(
                    callback_query_id=callback_id,
                    text=f"❌ Cannot approve video in status '{video.status}'"
                )
                return {"status": "invalid_status"}
                
            # Get Channel
            stmt_chan = select(Channel).where(Channel.id == video.channel_id)
            res_chan = await db.execute(stmt_chan)
            channel = res_chan.scalar_one()
            
            # Scheduling calculation
            if not video.scheduled_time:
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
                
            # Mark metadata approved
            stmt_meta = select(MetadataDraft).where(MetadataDraft.video_id == video_id).order_by(MetadataDraft.version_number.desc())
            meta_res = await db.execute(stmt_meta)
            latest_meta = meta_res.scalars().first()
            if latest_meta:
                latest_meta.is_approved = True
                latest_meta.approved_by = user_id
                latest_meta.approved_at = datetime.utcnow()
                db.add(latest_meta)
                
            video.status = VideoStatus.APPROVED
            db.add(video)
            await db.commit()
            await db.refresh(video)
            
            await _log_telegram_event(
                db=db,
                level=LogLevel.INFO,
                event_type="video_approved_via_telegram",
                message=f"Video approved via Telegram by user {cb.from_user.first_name}",
                video_id=video.id,
                channel_id=video.channel_id,
                user_id=user_id,
                details={"scheduled_time": str(video.scheduled_time)}
            )
            
            # Acknowledge callback query
            await object_telegram_api.answer_callback_query(
                callback_query_id=callback_id,
                text="✅ Approved successfully!"
            )
            
            # Edit Telegram Message to display outcome
            if cb.message:
                timestamp_str = datetime.now().strftime("%d-%m-%Y %H:%M WIB")
                new_text = (
                    f"{cb.message.text}\n\n"
                    f"✅ <b>APPROVED by {cb.from_user.first_name}</b>\n"
                    f"📅 Scheduled: {video.scheduled_time.strftime('%d-%m-%Y %H:%M WIB')}\n"
                    f"⏰ Processed: {timestamp_str}"
                )
                await object_telegram_api.edit_message_text(
                    chat_id=cb.message.chat.id,
                    message_id=cb.message.message_id,
                    text=new_text,
                    reply_markup=None
                )
                
            # Dispatch upload task
            upload_video_task.delay(video.id)
            logger.info("telegram_approve_celery_dispatched", video_id=video.id)
            
        finally:
            await redis_client.delete(lock_key)
            
        return {"status": "approved"}
        
    elif action == "discard":
        stmt_vid = select(Video).where(Video.id == video_id)
        res_vid = await db.execute(stmt_vid)
        video = res_vid.scalar_one_or_none()
        
        if not video:
            await object_telegram_api.answer_callback_query(callback_query_id=callback_id, text="❌ Video not found.")
            return {"status": "video_not_found"}
            
        if video.status not in [VideoStatus.STAGING, VideoStatus.DETECTED, VideoStatus.ERROR]:
            await object_telegram_api.answer_callback_query(
                callback_query_id=callback_id,
                text=f"❌ Cannot discard video in status '{video.status}'"
            )
            return {"status": "invalid_status"}
            
        video.status = VideoStatus.DISCARDED
        db.add(video)
        await db.commit()
        
        await _log_telegram_event(
            db=db,
            level=LogLevel.WARNING,
            event_type="video_discarded_via_telegram",
            message=f"Video discarded via Telegram by user {cb.from_user.first_name}",
            video_id=video.id,
            channel_id=video.channel_id,
            user_id=user_id
        )
        
        # Acknowledge callback
        await object_telegram_api.answer_callback_query(
            callback_query_id=callback_id,
            text="🗑️ Discarded successfully!"
        )
        
        # Edit message
        if cb.message:
            timestamp_str = datetime.now().strftime("%d-%m-%Y %H:%M WIB")
            new_text = (
                f"{cb.message.text}\n\n"
                f"🗑️ <b>DISCARDED by {cb.from_user.first_name}</b>\n"
                f"⏰ Processed: {timestamp_str}"
            )
            await object_telegram_api.edit_message_text(
                chat_id=cb.message.chat.id,
                message_id=cb.message.message_id,
                text=new_text,
                reply_markup=None
            )
            
        return {"status": "discarded"}
        
    return {"status": "unknown_action"}
