import os
import logging
from watchdog.events import FileSystemEventHandler
from services.filewatcher.src.detector import wait_for_file_stability
from services.filewatcher.src.api_client import APIClient
from services.filewatcher.src.config import settings

logger = logging.getLogger("filewatcher")

class VideoFileHandler(FileSystemEventHandler):
    """EventHandler that monitors for video files inside channel subdirectories."""

    def __init__(self):
        super().__init__()
        self.api_client = APIClient()
        self.allowed_extensions = {".mp4", ".mov", ".avi"}

    def on_created(self, event):
        """Triggered when a file or directory is created."""
        if event.is_directory:
            return

        filepath = event.src_path
        self.handle_file_event(filepath)

    def handle_file_event(self, filepath: str) -> None:
        """Parse file path, validate parameters, stability test, and notify backend."""
        abs_mount = os.path.abspath(settings.OMV_MOUNT_PATH)
        abs_file = os.path.abspath(filepath)

        # Safety check: must be inside mount
        if not abs_file.startswith(abs_mount):
            return

        # Get path relative to the OMV mount
        rel_path = os.path.relpath(abs_file, abs_mount)
        parts = rel_path.split(os.sep)

        # Expected parts structure: [channel_name, filename]
        # Length 2 means it is inside a channel folder, not a root file or deeper thumbnail subfolder
        if len(parts) != 2:
            return

        channel_name, filename = parts

        # Ignore hidden/system folders or files (like .DS_Store or .tmp files)
        if channel_name.startswith(".") or filename.startswith("."):
            return

        # Check extension
        _, ext = os.path.splitext(filename)
        if ext.lower() not in self.allowed_extensions:
            return

        logger.info(f"New video detected: {filename} in folder '{channel_name}'")

        # Wait for copy to complete (file stability check)
        if wait_for_file_stability(abs_file, settings.STABLE_TIMEOUT):
            file_size = os.path.getsize(abs_file)
            
            # Send detection ping to the FastAPI API
            success = self.api_client.notify_video_detected(
                filename=filename,
                file_path=abs_file,
                file_size_bytes=file_size,
                channel_name=channel_name
            )
            if success:
                logger.info(f"Successfully processed and logged video: {filename}")
            else:
                logger.warning(f"Failed to submit video detection to API for: {filename}")
        else:
            logger.warning(f"File size was unstable or copy was aborted for: {filename}")
