import os
import sys
import time
import logging
import signal
from watchdog.observers.polling import PollingObserver
from services.filewatcher.src.config import settings
from services.filewatcher.src.watcher import VideoFileHandler

# Configure basic console logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("filewatcher")

# Graceful shutdown flag
running = True

def sigterm_handler(signum, frame):
    """Gracefully terminate loop on SIGTERM or SIGINT."""
    global running
    logger.info("Shutdown signal received. Exiting watcher loop...")
    running = False

def main():
    logger.info("Starting YTAgent File Watcher Daemon...")
    logger.info(f"Target API Endpoint: {settings.API_URL}")
    logger.info(f"Monitoring Mount Directory: {settings.OMV_MOUNT_PATH}")
    logger.info(f"File Stability Delay: {settings.STABLE_TIMEOUT} seconds")

    # Connect signals
    signal.signal(signal.SIGINT, sigterm_handler)
    signal.signal(signal.SIGTERM, sigterm_handler)

    # Ensure path exists before starting
    if not os.path.exists(settings.OMV_MOUNT_PATH):
        logger.warning(f"Mount path '{settings.OMV_MOUNT_PATH}' not found. Creating it local for testing...")
        os.makedirs(settings.OMV_MOUNT_PATH, exist_ok=True)

    handler = VideoFileHandler()
    
    # Use PollingObserver for SMB/CIFS mount compatibility
    observer = PollingObserver()
    observer.schedule(handler, path=settings.OMV_MOUNT_PATH, recursive=True)

    try:
        observer.start()
        logger.info("Watchdog observer active. Waiting for file events...")
        
        while running:
            time.sleep(1)

    except Exception as e:
        logger.critical(f"Watcher crashed with unhandled exception: {e}")
    finally:
        logger.info("Requesting observer stop...")
        observer.stop()
        observer.join()
        logger.info("Watcher shutdown completed successfully.")

if __name__ == "__main__":
    main()
