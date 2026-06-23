import logging
import httpx
from services.filewatcher.src.config import settings

logger = logging.getLogger("filewatcher")

class APIClient:
    """Client for communicating with the YTAgent API backend."""

    def __init__(self):
        self.base_url = settings.API_URL
        self.client = httpx.Client(timeout=15.0)

    def notify_video_detected(self, filename: str, file_path: str, file_size_bytes: int, channel_name: str) -> bool:
        """Send a POST request to FastAPI backend notifying it of a detected video."""
        url = f"{self.base_url}/api/v1/videos/detect"
        payload = {
            "filename": filename,
            "file_path": file_path,
            "file_size_bytes": file_size_bytes,
            "channel_name": channel_name
        }
        try:
            logger.info(f"Notifying backend of file detection: {filename} ({channel_name})")
            response = self.client.post(url, json=payload)
            if response.status_code in (200, 201):
                logger.info(f"API accepted file detection for: {filename}")
                return True
            else:
                logger.error(f"API rejected file detection. Status: {response.status_code}, Body: {response.text}")
                return False
        except Exception as e:
            logger.error(f"Failed to communicate with API server at {url}: {e}")
            return False
