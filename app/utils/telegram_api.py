import httpx
import structlog
from typing import Optional, Any
from app.core.config import settings

logger = structlog.get_logger()

class TelegramAPI:
    """Lightweight client wrapper to interact asynchronously with Telegram Bot API."""

    def __init__(self):
        self.token = settings.TELEGRAM_BOT_TOKEN
        self.base_url = f"https://api.telegram.org/bot{self.token}"

    async def send_message(self, chat_id: int, text: str, reply_markup: Optional[dict[str, Any]] = None) -> bool:
        """Send HTML text message to a specific Telegram chat."""
        url = f"{self.base_url}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML"
        }
        if reply_markup:
            payload["reply_markup"] = reply_markup
            
        # Bypass network call if using dummy credentials during local E2E simulation
        if "Placeholder" in self.token:
            logger.info("telegram_send_message_skipped_placeholder", chat_id=chat_id, text=text[:100])
            return True

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=payload, timeout=10.0)
                if response.status_code == 200:
                    return True
                logger.error("telegram_send_message_rejected", status=response.status_code, body=response.text)
                return False
        except Exception as e:
            logger.error("telegram_send_message_failed", error=str(e))
            return False

    async def answer_callback_query(self, callback_query_id: str, text: Optional[str] = None) -> bool:
        """Answer Telegram inline callback query to clear button loading state."""
        url = f"{self.base_url}/answerCallbackQuery"
        payload = {
            "callback_query_id": callback_query_id
        }
        if text:
            payload["text"] = text
            
        if "Placeholder" in self.token:
            logger.info("telegram_answer_callback_skipped_placeholder", callback_id=callback_query_id, text=text)
            return True

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=payload, timeout=10.0)
                return response.status_code == 200
        except Exception as e:
            logger.error("telegram_answer_callback_failed", error=str(e))
            return False

    async def edit_message_text(self, chat_id: int, message_id: int, text: str, reply_markup: Optional[dict[str, Any]] = None) -> bool:
        """Replace text content of an existing Telegram message."""
        url = f"{self.base_url}/editMessageText"
        payload = {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": text,
            "parse_mode": "HTML"
        }
        if reply_markup:
            payload["reply_markup"] = reply_markup

        if "Placeholder" in self.token:
            logger.info("telegram_edit_message_skipped_placeholder", chat_id=chat_id, message_id=message_id, text=text[:100])
            return True

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=payload, timeout=10.0)
                return response.status_code == 200
        except Exception as e:
            logger.error("telegram_edit_message_failed", error=str(e))
            return False
object_telegram_api = TelegramAPI()
