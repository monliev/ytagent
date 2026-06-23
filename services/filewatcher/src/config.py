import os
import sys

class Settings:
    """Filewatcher configuration settings loaded from environment variables."""
    def __init__(self):
        self.API_URL = os.getenv("API_URL", "http://localhost:8000").rstrip("/")
        self.SCAN_INTERVAL = int(os.getenv("SCAN_INTERVAL", "120"))
        self.OMV_MOUNT_PATH = os.getenv("OMV_MOUNT_PATH", "/mnt/omv")
        self.STABLE_TIMEOUT = int(os.getenv("STABLE_TIMEOUT", "5"))

settings = Settings()
