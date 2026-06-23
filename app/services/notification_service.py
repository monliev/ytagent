import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Video, Channel, MetadataDraft
from app.utils.telegram_api import object_telegram_api
from app.core.config import settings

logger = structlog.get_logger()

class NotificationService:
    """Manages Telegram bot notifications to the supervisor chat."""

    def __init__(self):
        self.telegram_api = object_telegram_api
        self.supervisor_id = settings.SUPERVISOR_TELEGRAM_ID

    async def notify_video_ready(self, db: AsyncSession, video: Video) -> bool:
        """Construct and send an interactive video approval notification to the supervisor."""
        logger.info("notify_video_ready_started", video_id=video.id)
        
        # Load associated Channel
        stmt_channel = select(Channel).where(Channel.id == video.channel_id)
        channel_res = await db.execute(stmt_channel)
        channel = channel_res.scalar_one()

        # Load latest Metadata Draft
        stmt_meta = select(MetadataDraft).where(MetadataDraft.video_id == video.id).order_by(MetadataDraft.version_number.desc())
        meta_res = await db.execute(stmt_meta)
        metadata_draft = meta_res.scalars().first()

        if not metadata_draft:
            logger.error("notify_video_ready_no_metadata_draft", video_id=video.id)
            return False

        # Format scheduled time or scheduling hint
        if video.scheduled_time:
            scheduled_str = video.scheduled_time.strftime("%d-%m-%Y %H:%M WIB")
        else:
            scheduled_str = f"Harian @ {channel.preferred_time.strftime('%H:%M WIB')}"

        text = (
            f"🎵 <b>NEW VIDEO DETECTED & PREPARED</b>\n\n"
            f"<b>Channel:</b> {channel.name}\n"
            f"<b>File:</b> {video.filename}\n"
            f"<b>Title Draft:</b> {metadata_draft.title}\n"
            f"<b>Schedule:</b> {scheduled_str}\n"
            f"<b>Confidence:</b> {metadata_draft.confidence_score}%\n\n"
            f"Please approve or review the draft details on the dashboard."
        )

        reply_markup = {
            "inline_keyboard": [
                [
                    {
                        "text": "✅ Approve", 
                        "callback_data": f"approve:{video.id}"
                    },
                    {
                        "text": "✏️ Edit (Dashboard)", 
                        "callback_data": f"edit:{video.id}"
                    },
                    {
                        "text": "🗑️ Discard", 
                        "callback_data": f"discard:{video.id}"
                    }
                ]
            ]
        }

        # Resolve supervisor ID dynamically
        from app.services.settings_service import get_supervisor_telegram_id_async
        supervisor_id = await get_supervisor_telegram_id_async(db)

        # Send Telegram notification
        success = await self.telegram_api.send_message(
            chat_id=supervisor_id,
            text=text,
            reply_markup=reply_markup,
            db=db
        )
        if success:
            logger.info("notify_video_ready_success", video_id=video.id)
        return success
