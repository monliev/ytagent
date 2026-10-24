import os
import time
import logging

logger = logging.getLogger("filewatcher")

def wait_for_file_stability(filepath: str, stable_seconds: int = 5) -> bool:
    """Wait for the size of a file to remain unchanged for stable_seconds.
    
    This indicates that the file copy/render process is complete and the file
    is safe to process.
    """
    if not os.path.exists(filepath):
        logger.warning(f"File does not exist for stability check: {filepath}")
        return False

    try:
        previous_size = -1
        while True:
            if not os.path.exists(filepath):
                logger.warning(f"File vanished during stability check: {filepath}")
                return False

            current_size = os.path.getsize(filepath)
            
            # If the size is non-zero and matches the previous size check, it is stable
            if current_size > 0 and current_size == previous_size:
                logger.info(f"File size stable at {current_size} bytes: {filepath}")
                return True

            previous_size = current_size
            time.sleep(stable_seconds)
            
    except Exception as e:
        logger.error(f"Error checking stability for file {filepath}: {e}")
        return False


def check_files_stability_batch(filepaths: list[str], stable_seconds: int = 5) -> list[str]:
    """Check stability of multiple files in a single sleep window.
    
    Takes snapshot of all file sizes, sleeps once for stable_seconds, and compares.
    Returns only the files whose size remained stable (> 0 and unchanged).
    This transforms N * 5s blocking into a single 5s wait for large batches.
    """
    if not filepaths:
        return []

    # First snapshot
    snapshot_1 = {}
    for p in filepaths:
        try:
            if os.path.isfile(p):
                size = os.path.getsize(p)
                if size > 0:
                    snapshot_1[p] = size
        except OSError:
            pass

    if not snapshot_1:
        return []

    logger.info(f"Checking batch stability for {len(snapshot_1)} file(s) (waiting {stable_seconds}s once)...")
    time.sleep(stable_seconds)

    # Second snapshot & verification
    stable_files = []
    for p, initial_size in snapshot_1.items():
        try:
            if os.path.isfile(p):
                new_size = os.path.getsize(p)
                if new_size == initial_size and new_size > 0:
                    stable_files.append(p)
                else:
                    logger.warning(f"File size still changing (copying in progress): {p}")
        except OSError as e:
            logger.warning(f"File access error during batch check for {p}: {e}")

    logger.info(f"Batch stability check complete: {len(stable_files)}/{len(filepaths)} file(s) are stable and ready.")
    return stable_files
