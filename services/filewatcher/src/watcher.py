import os
import logging
from services.filewatcher.src.detector import wait_for_file_stability
from services.filewatcher.src.api_client import APIClient
from services.filewatcher.src.config import settings

logger = logging.getLogger("filewatcher")

ALLOWED_EXTENSIONS = {".mp4", ".mov", ".avi"}

# Global deduplication set — prevents sending duplicate detections for the
# same physical file from both the inotify listener and the periodic fallback scan.
_processed_files: set[str] = set()


def process_file(filepath: str) -> None:
    """Validate, stability-check, and notify backend about a new video file.

    This is the single entry point called by both the inotify listener and the
    periodic fallback scan so all validation & dedup logic lives in one place.
    """
    abs_mount = os.path.abspath(settings.OMV_MOUNT_PATH)
    abs_file = os.path.abspath(filepath)

    # Safety check: must be inside mount path
    if not abs_file.startswith(abs_mount):
        return

    parent_dir = os.path.dirname(abs_file)
    filename = os.path.basename(abs_file)

    # Ignore files directly in the root mount (must be inside a channel subfolder)
    if parent_dir == abs_mount:
        return

    # Ignore hidden/system files (.DS_Store, .tmp, etc.)
    if filename.startswith("."):
        return

    # Ignore hidden parent directories
    rel_path = os.path.relpath(abs_file, abs_mount)
    parts = rel_path.split(os.sep)
    if any(part.startswith(".") for part in parts[:-1]):
        return

    # Extension whitelist
    _, ext = os.path.splitext(filename)
    if ext.lower() not in ALLOWED_EXTENSIONS:
        return

    # Deduplication: skip if already processed in this session
    if abs_file in _processed_files:
        logger.debug(f"Skipping already-processed file: {filename}")
        return

    channel_name = parent_dir
    logger.info(f"New video detected: {filename} in folder '{channel_name}'")

    # Wait for the copy/render to finish before notifying the API
    if wait_for_file_stability(abs_file, settings.STABLE_TIMEOUT):
        file_size = os.path.getsize(abs_file)
        api_client = APIClient()
        success = api_client.notify_video_detected(
            filename=filename,
            file_path=abs_file,
            file_size_bytes=file_size,
            channel_name=channel_name,
        )
        if success:
            _processed_files.add(abs_file)
            logger.info(f"Successfully processed and logged video: {filename}")
        else:
            logger.warning(f"Failed to submit video detection to API for: {filename}")
    else:
        logger.warning(f"File size was unstable or copy was aborted for: {filename}")


def scan_directory_for_new_files() -> None:
    """Walk the entire OMV mount and process any video files not yet processed.

    Used by the periodic fallback thread to recover files that may have been
    missed by inotify (e.g. files copied while the NFS connection was interrupted).
    """
    abs_mount = os.path.abspath(settings.OMV_MOUNT_PATH)
    if not os.path.isdir(abs_mount):
        logger.warning(f"Mount path not accessible during periodic scan: {abs_mount}")
        return

    logger.debug("Periodic fallback scan started...")
    found = 0
    for root, _dirs, files in os.walk(abs_mount):
        for fname in files:
            full_path = os.path.join(root, fname)
            _, ext = os.path.splitext(fname)
            if ext.lower() in ALLOWED_EXTENSIONS and full_path not in _processed_files:
                found += 1
                process_file(full_path)

    if found:
        logger.info(f"Periodic scan finished — processed {found} new file(s).")
    else:
        logger.debug("Periodic scan finished — no new files found.")
