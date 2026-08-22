"""YTAgent File Watcher — inotifywait hybrid mode.

Architecture
------------
Primary   : subprocess `inotifywait --monitor --recursive` on the OMV mount.
            This is *event-driven* — the kernel notifies us only when a file
            actually appears (CLOSE_WRITE or MOVED_TO). CPU/IO usage ≈ 0%
            while the directory is idle.

Fallback  : A background thread that walks the mount every POLL_INTERVAL
            seconds. This catches files that were copied while inotifywait
            was not yet running, or while an NFS reconnect caused missed events.
            Already-processed files are skipped via a deduplication set.
"""

import os
import sys
import time
import shutil
import logging
import signal
import subprocess
import threading

from services.filewatcher.src.config import settings
from services.filewatcher.src.watcher import process_file, scan_directory_for_new_files

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("filewatcher")

# ---------------------------------------------------------------------------
# Graceful shutdown
# ---------------------------------------------------------------------------
_shutdown = threading.Event()


def _sigterm_handler(signum, frame):
    logger.info("Shutdown signal received — stopping watcher...")
    _shutdown.set()


signal.signal(signal.SIGINT, _sigterm_handler)
signal.signal(signal.SIGTERM, _sigterm_handler)


# ---------------------------------------------------------------------------
# Fallback periodic scan thread
# ---------------------------------------------------------------------------

def _periodic_scan_thread():
    """Background thread that scans the mount on a fixed interval as a safety net."""
    logger.info(
        f"Periodic fallback scan thread started (interval={settings.POLL_INTERVAL}s)."
    )
    while not _shutdown.is_set():
        _shutdown.wait(timeout=settings.POLL_INTERVAL)
        if _shutdown.is_set():
            break
        try:
            scan_directory_for_new_files()
        except Exception as exc:
            logger.error(f"Periodic scan error: {exc}")

    logger.info("Periodic fallback scan thread stopped.")


# ---------------------------------------------------------------------------
# inotifywait primary listener
# ---------------------------------------------------------------------------

def _start_inotifywait(mount_path: str) -> subprocess.Popen | None:
    """Start inotifywait subprocess in monitor mode.

    Returns the Popen object or None if inotifywait is not available.
    Watches for CLOSE_WRITE (file fully written) and MOVED_TO (file renamed/moved in).
    """
    if not shutil.which("inotifywait"):
        logger.warning(
            "inotifywait not found in PATH — falling back to periodic scan only. "
            "Install inotify-tools in the container to enable event-driven watching."
        )
        return None

    cmd = [
        "inotifywait",
        "--monitor",          # keep running, print each event
        "--recursive",        # watch all subdirectories
        "--quiet",            # suppress startup messages (just events)
        "--format", "%w%f",   # output: directory + filename as one string
        "--event", "CLOSE_WRITE",
        "--event", "MOVED_TO",
        mount_path,
    ]
    logger.info(f"Starting inotifywait: {' '.join(cmd)}")
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,  # line-buffered
    )
    return proc


def _inotify_listener(mount_path: str) -> None:
    """Outer loop that (re-)starts inotifywait if it crashes and reads its stdout."""
    while not _shutdown.is_set():
        proc = _start_inotifywait(mount_path)

        if proc is None:
            # inotifywait not available; periodic scan is our only mechanism.
            logger.info("Running in periodic-scan-only mode (no inotifywait).")
            _shutdown.wait()  # block until shutdown
            return

        logger.info(f"inotifywait PID={proc.pid} listening on '{mount_path}'")

        try:
            for line in proc.stdout:
                if _shutdown.is_set():
                    break
                filepath = line.strip()
                if not filepath:
                    continue
                logger.debug(f"inotify event: {filepath}")
                try:
                    process_file(filepath)
                except Exception as exc:
                    logger.error(f"Error processing inotify event '{filepath}': {exc}")

        except Exception as exc:
            logger.error(f"inotifywait stdout read error: {exc}")
        finally:
            try:
                proc.kill()
                proc.wait(timeout=5)
            except Exception:
                pass

        if not _shutdown.is_set():
            logger.warning("inotifywait exited unexpectedly — restarting in 10 s...")
            _shutdown.wait(timeout=10)

    logger.info("inotifywait listener stopped.")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    logger.info("=" * 60)
    logger.info("YTAgent File Watcher starting (inotifywait hybrid mode)")
    logger.info(f"  Mount path  : {settings.OMV_MOUNT_PATH}")
    logger.info(f"  API URL     : {settings.API_URL}")
    logger.info(f"  Stable wait : {settings.STABLE_TIMEOUT}s")
    logger.info(f"  Fallback    : every {settings.POLL_INTERVAL}s")
    logger.info("=" * 60)

    mount_path = settings.OMV_MOUNT_PATH

    if not os.path.exists(mount_path):
        logger.warning(f"Mount path '{mount_path}' not found. Creating for local testing...")
        os.makedirs(mount_path, exist_ok=True)

    # --- Wait for API to be ready ---
    from services.filewatcher.src.api_client import APIClient
    api_client = APIClient()
    if not api_client.wait_for_api_ready(timeout_seconds=120):
        logger.error("API backend is not reachable. Proceeding, but scans may fail.")

    # --- Run initial scan to process files already present at startup ---
    logger.info("Running initial startup scan...")
    try:
        scan_directory_for_new_files()
    except Exception as exc:
        logger.error(f"Initial scan error: {exc}")

    # --- Start background periodic fallback scan thread ---
    scan_thread = threading.Thread(target=_periodic_scan_thread, daemon=True, name="periodic-scan")
    scan_thread.start()

    # --- Primary: inotifywait listener (blocks until shutdown) ---
    _inotify_listener(mount_path)

    # --- Cleanup ---
    _shutdown.set()
    scan_thread.join(timeout=5)
    logger.info("YTAgent File Watcher stopped cleanly.")


if __name__ == "__main__":
    main()
