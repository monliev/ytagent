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
