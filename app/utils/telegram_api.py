import httpx
import structlog
from typing import Optional, Any
from app.core.config import settings
from app.services.settings_service import get_telegram_bot_token_async

logger = structlog.get_logger()

class TelegramAPI:
    """Lightweight client wrapper to interact asynchronously with Telegram Bot API."""

    def __init__(self):
        self.default_token = settings.TELEGRAM_BOT_TOKEN

    async def _get_token(self, db: Optional[Any] = None) -> str:
        if db is not None:
            return await get_telegram_bot_token_async(db)
        return self.default_token

    async def _get_base_url(self, db: Optional[Any] = None) -> str:
        token = await self._get_token(db)
        return f"https://api.telegram.org/bot{token}"

    async def send_message(self, chat_id: int, text: str, reply_markup: Optional[dict[str, Any]] = None, db: Optional[Any] = None) -> bool:
        """Send HTML text message to a specific Telegram chat."""
        base_url = await self._get_base_url(db)
        token = await self._get_token(db)
        url = f"{base_url}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML"
        }
        if reply_markup:
            payload["reply_markup"] = reply_markup
            
        # Bypass network call if using dummy credentials during local E2E simulation
        if "Placeholder" in token:
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

    async def answer_callback_query(self, callback_query_id: str, text: Optional[str] = None, db: Optional[Any] = None) -> bool:
        """Answer Telegram inline callback query to clear button loading state."""
        base_url = await self._get_base_url(db)
        token = await self._get_token(db)
        url = f"{base_url}/answerCallbackQuery"
        payload = {
            "callback_query_id": callback_query_id
        }
        if text:
            payload["text"] = text
            
        if "Placeholder" in token:
            logger.info("telegram_answer_callback_skipped_placeholder", callback_id=callback_query_id, text=text)
            return True

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=payload, timeout=10.0)
                return response.status_code == 200
        except Exception as e:
            logger.error("telegram_answer_callback_failed", error=str(e))
            return False

    async def edit_message_text(self, chat_id: int, message_id: int, text: str, reply_markup: Optional[dict[str, Any]] = None, db: Optional[Any] = None) -> bool:
        """Replace text content of an existing Telegram message."""
        base_url = await self._get_base_url(db)
        token = await self._get_token(db)
        url = f"{base_url}/editMessageText"
        payload = {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": text,
            "parse_mode": "HTML"
        }
        if reply_markup:
            payload["reply_markup"] = reply_markup

        if "Placeholder" in token:
            logger.info("telegram_edit_message_skipped_placeholder", chat_id=chat_id, message_id=message_id, text=text[:100])
            return True

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=payload, timeout=10.0)
                return response.status_code == 200
        except Exception as e:
            logger.error("telegram_edit_message_failed", error=str(e))
            return False
    async def set_webhook(self, webhook_url: str, db: Optional[Any] = None) -> dict:
        """Register a webhook URL with the Telegram Bot API."""
        base_url = await self._get_base_url(db)
        token = await self._get_token(db)
        url = f"{base_url}/setWebhook"

        if "Placeholder" in token:
            logger.info("telegram_set_webhook_skipped_placeholder", webhook_url=webhook_url)
            return {"ok": True, "skipped": True, "reason": "placeholder_token"}

        try:
            # Generate a secret token using a SHA-256 hash of the application's SECRET_KEY
            import hashlib
            secret_token = hashlib.sha256(settings.SECRET_KEY.encode("utf-8")).hexdigest()

            payload = {
                "url": webhook_url,
                "allowed_updates": ["callback_query", "message"],
                "secret_token": secret_token
            }

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url,
                    json=payload,
                    timeout=10.0,
                )
                data = response.json()
                if data.get("ok"):
                    logger.info("telegram_webhook_registered", webhook_url=webhook_url)
                else:
                    logger.error("telegram_webhook_registration_failed", response=data)
                return data
        except Exception as e:
            logger.error("telegram_set_webhook_failed", error=str(e))
            return {"ok": False, "error": str(e)}

    async def get_webhook_info(self, db: Optional[Any] = None) -> dict:
        """Retrieve current webhook configuration from Telegram."""
        base_url = await self._get_base_url(db)
        token = await self._get_token(db)
        url = f"{base_url}/getWebhookInfo"

        if "Placeholder" in token:
            return {"ok": True, "skipped": True, "reason": "placeholder_token"}

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, timeout=10.0)
                return response.json()
        except Exception as e:
            logger.error("telegram_get_webhook_info_failed", error=str(e))
            return {"ok": False, "error": str(e)}

object_telegram_api = TelegramAPI()
