from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
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


from pydantic import BaseModel
import httpx
from sqlalchemy import select
from app.models.system_setting import SystemSetting

async def resolve_setting_value(key: str, user_input: str | None, db: AsyncSession) -> str | None:
    if not user_input:
        return None
    # If user_input contains only asterisks or starts with asterisks, it is a mask. Load from DB.
    if set(user_input) <= {"*"} or (user_input.startswith("****") and "*" in user_input):
        stmt = select(SystemSetting).where(SystemSetting.key == key)
        res = await db.execute(stmt)
        record = res.scalar_one_or_none()
        if record:
            return record.value
        # Fallbacks to default config values if not in DB
        if key == "telegram_bot_token":
            return settings.TELEGRAM_BOT_TOKEN
        elif key == "recaptcha_secret_key":
            return settings.RECAPTCHA_SECRET_KEY
    return user_input


class TelegramTestPayload(BaseModel):
    telegram_bot_token: str
    supervisor_telegram_id: Optional[int] = None



@router.post("/test-telegram")
async def test_telegram_connection(
    payload: TelegramTestPayload,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    token = await resolve_setting_value("telegram_bot_token", payload.telegram_bot_token, db)
    if not token or "Placeholder" in token:
        raise HTTPException(status_code=400, detail="Telegram bot token is not configured.")
        
    url = f"https://api.telegram.org/bot{token}/getMe"
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, timeout=5.0)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("ok"):
                bot_info = data.get("result", {})
                return {
                    "status": "connected",
                    "detail": f"Connected to Bot: @{bot_info.get('username')} ({bot_info.get('first_name')})"
                }
            else:
                return {
                    "status": "failed",
                    "detail": f"Telegram API error: {data.get('description')}"
                }
        else:
            return {
                "status": "failed",
                "detail": f"Failed with HTTP status code {resp.status_code}"
            }
    except Exception as e:
        return {
            "status": "failed",
            "detail": f"Connection error: {str(e)}"
        }


class CloudflareTestPayload(BaseModel):
    cf_ai_url: str


@router.post("/test-cloudflare")
async def test_cloudflare_connection(
    payload: CloudflareTestPayload,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    url = payload.cf_ai_url
    if not url or "dummy" in url:
        raise HTTPException(status_code=400, detail="Cloudflare AI URL is not configured.")
        
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, timeout=5.0)
        return {
            "status": "connected",
            "detail": f"Endpoint responded with HTTP {resp.status_code}."
        }
    except Exception as e:
        return {
            "status": "failed",
            "detail": f"Connection error: {str(e)}"
        }


class RecaptchaTestPayload(BaseModel):
    recaptcha_site_key: str
    recaptcha_secret_key: str


@router.post("/test-recaptcha")
async def test_recaptcha_connection(
    payload: RecaptchaTestPayload,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    site_key = payload.recaptcha_site_key
    secret_key = await resolve_setting_value("recaptcha_secret_key", payload.recaptcha_secret_key, db)
    
    if not site_key or not secret_key:
        raise HTTPException(status_code=400, detail="reCAPTCHA site key or secret key is not configured.")
        
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://www.google.com/recaptcha/api/siteverify",
                data={"secret": secret_key, "response": "test-token-ping"},
                timeout=5.0
            )
        if resp.status_code == 200:
            return {
                "status": "connected",
                "detail": "Successfully reached Google reCAPTCHA verification service."
            }
        else:
            return {
                "status": "failed",
                "detail": f"Failed with HTTP status code {resp.status_code}"
            }
    except Exception as e:
        return {
            "status": "failed",
            "detail": f"Connection error: {str(e)}"
        }


class SFTPTestPayload(BaseModel):
    sftp_host: str
    sftp_port: int
    sftp_user: str
    sftp_password: str
    sftp_base_path: str


@router.post("/test-sftp")
async def test_sftp_connection(
    payload: SFTPTestPayload,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    host = payload.sftp_host
    port = payload.sftp_port
    user = payload.sftp_user
    password = await resolve_setting_value("sftp_password", payload.sftp_password, db)
    base_path = payload.sftp_base_path
    
    if not host or not user or not password:
        raise HTTPException(status_code=400, detail="SFTP host, user, or password is not configured.")
        
    try:
        import paramiko
        transport = paramiko.Transport((host, port))
        transport.connect(username=user, password=password)
        sftp = paramiko.SFTPClient.from_transport(transport)
        try:
            sftp.listdir(base_path)
            return {
                "status": "connected",
                "detail": f"SFTP Connected successfully! Base path '{base_path}' is accessible."
            }
        finally:
            sftp.close()
            transport.close()
    except Exception as e:
        return {
            "status": "failed",
            "detail": f"SFTP Connection failed: {str(e)}"
        }
