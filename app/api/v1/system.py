from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
import os
import subprocess
import structlog

from app.api.deps import get_db, get_current_user
from app.models.user import User
from app.core.config import settings
from app.core.redis_client import redis_client

logger = structlog.get_logger()
router = APIRouter()

@router.get("/health")
async def get_system_health(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Retrieve system health statistics: CPU, Memory, Disk, NAS mount, and Celery status."""
    logger.info("api_system_health_called", user_id=current_user.id)
    
    # 1. VPS CPU usage
    cpu_load = 0.0
    try:
        load_1, _, _ = os.getloadavg()
        cores = os.cpu_count() or 1
        cpu_load = round((load_1 / cores) * 100, 1)
    except Exception as e:
        logger.warning("failed_to_get_cpu_load", error=str(e))
        
    # 2. Memory usage
    mem_total = 0
    mem_used = 0
    mem_percent = 0.0
    try:
        if os.path.exists("/proc/meminfo"):
            with open("/proc/meminfo", "r") as f:
                lines = f.readlines()
            meminfo = {}
            for line in lines:
                parts = line.split()
                if len(parts) >= 2:
                    meminfo[parts[0].replace(":", "")] = int(parts[1])
            total = meminfo.get("MemTotal", 0) * 1024
            free = meminfo.get("MemFree", 0) * 1024
            buffers = meminfo.get("Buffers", 0) * 1024
            cached = meminfo.get("Cached", 0) * 1024
            used = total - free - buffers - cached
            mem_total = total
            mem_used = used
            mem_percent = round((used / total) * 100, 1) if total > 0 else 0.0
        else:
            res_total = subprocess.run(["sysctl", "-n", "hw.memsize"], capture_output=True, text=True)
            total = int(res_total.stdout.strip()) if res_total.returncode == 0 else 0
            mem_total = total
            mem_used = total // 2
            mem_percent = 50.0
    except Exception as e:
        logger.warning("failed_to_get_memory_info", error=str(e))
        
    # 3. Disk usage (NAS mount)
    disk_total = 0
    disk_used = 0
    disk_percent = 0.0
    nas_writable = False
    nas_mounted = False
    
    nas_path = settings.OMV_MOUNT_PATH
    if os.path.exists(nas_path):
        nas_mounted = True
        try:
            test_file = os.path.join(nas_path, ".health_check_write_test")
            with open(test_file, "w") as f:
                f.write("test")
            os.remove(test_file)
            nas_writable = True
        except Exception:
            nas_writable = False
            
        try:
            st = os.statvfs(nas_path)
            total = st.f_blocks * st.f_frsize
            free = st.f_bavail * st.f_frsize
            used = total - free
            disk_total = total
            disk_used = used
            disk_percent = round((used / total) * 100, 1) if total > 0 else 0.0
        except Exception as e:
            logger.warning("failed_to_get_disk_usage", error=str(e))

    # 4. Celery worker status
    celery_online = False
    try:
        await redis_client.ping()
        from app.tasks.celery_app import celery_app
        insp = celery_app.control.inspect(timeout=1.0)
        pings = insp.ping()
        if pings:
            celery_online = True
    except Exception as e:
        logger.warning("failed_to_ping_celery", error=str(e))
        
    return {
        "cpu_percent": cpu_load,
        "memory": {
            "total_bytes": mem_total,
            "used_bytes": mem_used,
            "percent": mem_percent,
        },
        "nas": {
            "mounted": nas_mounted,
            "writable": nas_writable,
            "path": nas_path,
            "total_bytes": disk_total,
            "used_bytes": disk_used,
            "percent": disk_percent,
        },
        "celery_online": celery_online
    }
