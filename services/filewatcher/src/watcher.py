import os
import json
import logging
from services.filewatcher.src.detector import wait_for_file_stability, check_files_stability_batch
from services.filewatcher.src.api_client import APIClient
from services.filewatcher.src.config import settings

logger = logging.getLogger("filewatcher")

ALLOWED_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm"}

# Persistent cache path for processed files and directory mtimes
CACHE_FILE = os.getenv("WATCHER_CACHE_FILE", "/tmp/watcher_processed_files.json")

_processed_files: set[str] = set()
_folder_mtimes: dict[str, float] = {}


def _load_cache() -> None:
    """Load processed file paths and directory mtimes from persistent disk cache."""
    global _processed_files, _folder_mtimes
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                _processed_files = set(data.get("processed_files", []))
                _folder_mtimes = data.get("folder_mtimes", {})
                logger.info(f"Loaded {len(_processed_files)} processed files from cache ({CACHE_FILE}).")
        except Exception as e:
            logger.warning(f"Failed to load cache file {CACHE_FILE}: {e}")


def _save_cache() -> None:
    """Persist processed file paths and directory mtimes to disk."""
    try:
        data = {
            "processed_files": list(_processed_files),
            "folder_mtimes": _folder_mtimes,
        }
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f)
    except Exception as e:
        logger.warning(f"Failed to save watcher cache {CACHE_FILE}: {e}")


# Initialize cache at import time
_load_cache()


def is_valid_video_file(filepath: str, abs_mount: str) -> bool:
    """Check if a file is an eligible video file inside a channel directory."""
    abs_file = os.path.abspath(filepath)
    if not abs_file.startswith(abs_mount):
        return False

    parent_dir = os.path.dirname(abs_file)
    filename = os.path.basename(abs_file)

    if parent_dir == abs_mount:
        return False
    if filename.startswith("."):
        return False

    rel_path = os.path.relpath(abs_file, abs_mount)
    parts = rel_path.split(os.sep)
    if any(part.startswith(".") for part in parts[:-1]):
        return False

    _, ext = os.path.splitext(filename)
    return ext.lower() in ALLOWED_EXTENSIONS


def process_file(filepath: str) -> bool:
    """Validate, stability-check, and notify backend about a single video file.
    
    Used primarily by the inotify event handler.
    """
    abs_mount = os.path.abspath(settings.OMV_MOUNT_PATH)
    abs_file = os.path.abspath(filepath)

    if not is_valid_video_file(abs_file, abs_mount):
        return False

    if abs_file in _processed_files:
        logger.debug(f"Skipping already-processed file: {os.path.basename(abs_file)}")
        return False

    filename = os.path.basename(abs_file)
    parent_dir = os.path.dirname(abs_file)
    channel_name = parent_dir
    logger.info(f"New video detected: {filename} in folder '{channel_name}'")

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
            _save_cache()
            logger.info(f"Successfully processed and logged video: {filename}")
            return True
        else:
            logger.warning(f"Failed to submit video detection to API for: {filename}")
    else:
        logger.warning(f"File size was unstable or copy was aborted for: {filename}")
    return False


def scan_directory_for_new_files(force_full_scan: bool = False) -> int:
    """Scan OMV mount for new videos using smart mtime checks to minimize disk I/O.
    
    When force_full_scan is False (the default periodic behavior), checks whether
    directory modified times have changed. If unchanged, skips walking subdirectories.
    When multiple new files are found (batch render), checks stability concurrently in a single window.
    """
    global _folder_mtimes
    abs_mount = os.path.abspath(settings.OMV_MOUNT_PATH)
    if not os.path.isdir(abs_mount):
        logger.warning(f"Mount path not accessible during scan: {abs_mount}")
        return 0

    # 1. Check top-level mount and subfolders' mtimes
    has_changes = force_full_scan
    current_mtimes = {}

    try:
        mount_mtime = os.stat(abs_mount).st_mtime
        current_mtimes[abs_mount] = mount_mtime
        if _folder_mtimes.get(abs_mount) != mount_mtime:
            has_changes = True

        for entry in os.scandir(abs_mount):
            if entry.is_dir() and not entry.name.startswith("."):
                dir_mtime = entry.stat().st_mtime
                current_mtimes[entry.path] = dir_mtime
                if _folder_mtimes.get(entry.path) != dir_mtime:
                    has_changes = True
    except OSError as e:
        logger.warning(f"Failed checking directory mtimes: {e}")
        has_changes = True

    if not has_changes:
        logger.debug("Smart scan: OMV folder mtimes unchanged — 0% disk I/O, scan skipped.")
        return 0

    # 2. Collect candidate files that have not yet been processed
    logger.info("Folder change detected on OMV. Scanning for new candidate videos...")
    candidate_files = []
    for root, _dirs, files in os.walk(abs_mount):
        for fname in files:
            full_path = os.path.join(root, fname)
            if is_valid_video_file(full_path, abs_mount) and full_path not in _processed_files:
                candidate_files.append(full_path)

    if not candidate_files:
        logger.info("Scan completed: no new unprocessed video files found.")
        _folder_mtimes = current_mtimes
        _save_cache()
        return 0

    logger.info(f"Found {len(candidate_files)} new unprocessed video file(s). Performing batch stability check...")

    # 3. Batch stability check (1 sleep window for all files, instead of N * 5s)
    stable_files = check_files_stability_batch(candidate_files, settings.STABLE_TIMEOUT)
    if not stable_files:
        logger.info("All candidate files are still being rendered or copied. Will check again on next scan.")
        return 0

    # 4. Notify backend for all stable files
    api_client = APIClient()
    processed_count = 0
    for full_path in stable_files:
        filename = os.path.basename(full_path)
        channel_name = os.path.dirname(full_path)
        try:
            file_size = os.path.getsize(full_path)
            success = api_client.notify_video_detected(
                filename=filename,
                file_path=full_path,
                file_size_bytes=file_size,
                channel_name=channel_name,
            )
            if success:
                _processed_files.add(full_path)
                processed_count += 1
                logger.info(f"Processed batch item: {filename}")
        except Exception as e:
            logger.error(f"Error submitting batch file {filename}: {e}")

    # 5. Update mtime cache & save
    _folder_mtimes = current_mtimes
    _save_cache()
    logger.info(f"Smart scan finished — successfully processed {processed_count} new video(s).")
    return processed_count
