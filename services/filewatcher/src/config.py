import os


class Settings:
    """Filewatcher configuration settings loaded from environment variables."""
    def __init__(self):
        self.API_URL = os.getenv("API_URL", "http://localhost:8000").rstrip("/")
        self.OMV_MOUNT_PATH = os.getenv("OMV_MOUNT_PATH", "/mnt/omv")
        self.STABLE_TIMEOUT = int(os.getenv("STABLE_TIMEOUT", "5"))

        # Primary: inotifywait event-driven polling (near-zero I/O)
        # Fallback: periodic scan interval in seconds (safety net for missed inotify events)
        self.POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", "300"))  # 5 minutes

        # Backward-compat alias (SCAN_INTERVAL was the old name)
        self.SCAN_INTERVAL = int(os.getenv("SCAN_INTERVAL", str(self.POLL_INTERVAL)))


settings = Settings()
