import os
import json
import subprocess
import logging

logger = logging.getLogger("api")

def get_video_metadata(filepath: str) -> dict:
    """Query video file metadata using ffprobe.
    
    Returns a dict with:
        duration_seconds (int): Video duration in seconds
        resolution (str): Video dimensions, e.g., '1920x1080'
    """
    cmd = [
        "ffprobe",
        "-v", "error",
        "-show_entries", "format=duration:stream=width,height",
        "-of", "json",
        filepath
    ]
    try:
        logger.info(f"Running ffprobe metadata extraction on: {filepath}")
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        data = json.loads(result.stdout)
        
        # Get duration
        duration = float(data.get("format", {}).get("duration", 0))
        
        # Find video stream and parse resolution
        width, height = 0, 0
        for stream in data.get("streams", []):
            if "width" in stream and "height" in stream:
                width = int(stream["width"])
                height = int(stream["height"])
                break
                
        resolution = f"{width}x{height}" if width and height else None
        
        return {
            "duration_seconds": int(duration),
            "resolution": resolution
        }
    except Exception as e:
        logger.error(f"ffprobe metadata extraction failed for {filepath}: {e}")
        return {
            "duration_seconds": 0,
            "resolution": None
        }

def extract_screenshot(video_path: str, screenshot_path: str, duration_seconds: int = 0) -> bool:
    """Extract a representative frame at second 30 using ffmpeg.
    
    If the video duration is under 30 seconds, falls back to the 50% midpoint mark.
    Saves the extracted frame to screenshot_path.
    """
    if duration_seconds <= 0:
        meta = get_video_metadata(video_path)
        duration_seconds = meta["duration_seconds"]

    time_offset = 30
    if duration_seconds > 0 and duration_seconds < 30:
        time_offset = duration_seconds // 2

    # Format time offset to HH:MM:SS
    h = time_offset // 3600
    m = (time_offset % 3600) // 60
    s = time_offset % 60
    time_str = f"{h:02d}:{m:02d}:{s:02d}"

    # Ensure output directory exists
    os.makedirs(os.path.dirname(screenshot_path), exist_ok=True)

    cmd = [
        "ffmpeg",
        "-y",
        "-ss", time_str,
        "-i", video_path,
        "-frames:v", "1",
        "-s", "1280x720",
        "-q:v", "2",
        screenshot_path
    ]
    try:
        logger.info(f"Extracting frame at {time_str} from: {video_path}")
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        return os.path.exists(screenshot_path)
    except Exception as e:
        logger.error(f"ffmpeg frame extraction failed for {video_path}: {e}")
        return False
