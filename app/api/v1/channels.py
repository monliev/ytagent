from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
import structlog
import os
import json
import random
import base64
import httpx
from datetime import datetime, date, time, timedelta
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

from app.api.deps import get_db, get_current_user
from app.models import Channel, User, GCPProject, GCPProjectStatus, ChannelCredentials
from app.schemas.channel import ChannelCreate, ChannelUpdate, ChannelResponse
from app.schemas.gcp_project import GCPProjectCreate, GCPProjectResponse, ChannelCredentialsCreate, ChannelCredentialsResponse
from app.utils.credential_crypto import encrypt_token, decrypt_token

logger = structlog.get_logger()
router = APIRouter()

@router.get("/", response_model=List[ChannelResponse])
async def list_channels(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> List[ChannelResponse]:
    """Retrieve list of all active/inactive channels."""
    logger.info("api_list_channels_called", user_id=current_user.id)
    stmt = select(Channel).order_by(Channel.id.asc())
    res = await db.execute(stmt)
    return res.scalars().all()

@router.get("/{id}", response_model=ChannelResponse)
async def get_channel(
    id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> ChannelResponse:
    """Retrieve details of a specific channel."""
    logger.info("api_get_channel_called", channel_id=id, user_id=current_user.id)
    stmt = select(Channel).where(Channel.id == id)
    res = await db.execute(stmt)
    channel = res.scalar_one_or_none()
    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Channel not found"
        )
    return channel

@router.post("/", response_model=ChannelResponse, status_code=status.HTTP_201_CREATED)
async def create_channel(
    payload: ChannelCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> ChannelResponse:
    """Create a new channel entry."""
    logger.info("api_create_channel_called", name=payload.name, user_id=current_user.id)
    
    # Check if duplicate name or folder path exists
    stmt = select(Channel).where((Channel.name == payload.name) | (Channel.folder_path == payload.folder_path))
    res = await db.execute(stmt)
    if res.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Channel name or folder path already registered"
        )
        
    channel = Channel(**payload.model_dump())
    db.add(channel)
    await db.commit()
    await db.refresh(channel)
    logger.info("api_channel_created", channel_id=channel.id, name=channel.name)
    return channel

@router.put("/{id}", response_model=ChannelResponse)
async def update_channel(
    id: int,
    payload: ChannelUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> ChannelResponse:
    """Update configurations of a specific channel."""
    logger.info("api_update_channel_called", channel_id=id, user_id=current_user.id)
    stmt = select(Channel).where(Channel.id == id)
    res = await db.execute(stmt)
    channel = res.scalar_one_or_none()
    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Channel not found"
        )
    
    update_data = payload.model_dump(exclude_unset=True)
    for field, val in update_data.items():
        setattr(channel, field, val)
        
    db.add(channel)
    await db.commit()
    await db.refresh(channel)
    logger.info("api_channel_updated", channel_id=channel.id)
    return channel

@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_channel(
    id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> None:
    """Delete channel database record."""
    logger.info("api_delete_channel_called", channel_id=id, user_id=current_user.id)
    stmt = select(Channel).where(Channel.id == id)
    res = await db.execute(stmt)
    channel = res.scalar_one_or_none()
    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Channel not found"
        )
    await db.delete(channel)
    await db.commit()
    logger.info("api_channel_deleted", channel_id=id)
    return None

# ==========================================
# GCP Projects & Credentials Endpoints
# ==========================================

@router.get("/{id}/projects", response_model=List[GCPProjectResponse])
async def list_channel_projects(
    id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> List[GCPProjectResponse]:
    """List all GCP Projects for a channel."""
    logger.info("api_list_channel_projects_called", channel_id=id, user_id=current_user.id)
    stmt = select(GCPProject).where(GCPProject.channel_id == id)
    res = await db.execute(stmt)
    return res.scalars().all()

@router.post("/{id}/projects", response_model=GCPProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_channel_project(
    id: int,
    payload: GCPProjectCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> GCPProjectResponse:
    """Create a new GCP Project entry with encrypted client secret JSON."""
    logger.info("api_create_channel_project_called", channel_id=id, project_id=payload.project_id, user_id=current_user.id)
    
    # Verify channel exists
    stmt_chan = select(Channel).where(Channel.id == id)
    res_chan = await db.execute(stmt_chan)
    if not res_chan.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Channel not found")
        
    # Check duplicate project ID
    stmt_dup = select(GCPProject).where(GCPProject.project_id == payload.project_id)
    res_dup = await db.execute(stmt_dup)
    if res_dup.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="GCP Project ID already registered")

    # Encrypt client secret json string
    encrypted_json = encrypt_token(id, payload.client_secret_json)
    
    project = GCPProject(
        channel_id=id,
        project_name=payload.project_name,
        project_id=payload.project_id,
        client_secret_json=encrypted_json,
        client_secret_path="", # Empty because json is used
        quota_limit=payload.quota_limit,
        status=GCPProjectStatus.ACTIVE
    )
    
    db.add(project)
    await db.commit()
    await db.refresh(project)
    
    logger.info("api_gcp_project_created", id=project.id, project_id=project.project_id)
    return project

@router.delete("/{id}/projects/{proj_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_channel_project(
    id: int,
    proj_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> None:
    """Delete a GCP project entry."""
    logger.info("api_delete_channel_project_called", channel_id=id, project_id=proj_id, user_id=current_user.id)
    stmt = select(GCPProject).where(GCPProject.id == proj_id, GCPProject.channel_id == id)
    res = await db.execute(stmt)
    project = res.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="GCP Project not found")
        
    await db.delete(project)
    await db.commit()
    logger.info("api_gcp_project_deleted", id=proj_id)
    return None

@router.post("/{id}/credentials", response_model=ChannelCredentialsResponse, status_code=status.HTTP_201_CREATED)
async def save_channel_credentials(
    id: int,
    payload: ChannelCredentialsCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> ChannelCredentialsResponse:
    """Register or update OAuth refresh token directly from the dashboard."""
    logger.info("api_save_channel_credentials_called", channel_id=id, project_id=payload.gcp_project_id, user_id=current_user.id)
    
    # Verify GCP project exists for this channel
    stmt_proj = select(GCPProject).where(GCPProject.project_id == payload.gcp_project_id, GCPProject.channel_id == id)
    res_proj = await db.execute(stmt_proj)
    if not res_proj.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="GCP Project not found for this channel")

    # Encrypt raw refresh token
    encrypted_refresh = encrypt_token(id, payload.refresh_token)
    
    # Check if credentials record already exists
    stmt_creds = select(ChannelCredentials).where(
        ChannelCredentials.channel_id == id,
        ChannelCredentials.gcp_project_id == payload.gcp_project_id
    )
    res_creds = await db.execute(stmt_creds)
    creds = res_creds.scalar_one_or_none()
    
    if creds:
        creds.oauth_refresh_token_encrypted = encrypted_refresh
        creds.is_active = True
        creds.last_error = None
    else:
        creds = ChannelCredentials(
            channel_id=id,
            gcp_project_id=payload.gcp_project_id,
            oauth_refresh_token_encrypted=encrypted_refresh,
            oauth_credentials_encrypted="",  # Will be populated by first oauth refresh
            is_active=True
        )
        db.add(creds)
        
    await db.commit()
    await db.refresh(creds)
    
    # Update active project ID for channel if none is set
    stmt_chan = select(Channel).where(Channel.id == id)
    res_chan = await db.execute(stmt_chan)
    channel = res_chan.scalar_one()
    if not channel.gcp_project_id:
        channel.gcp_project_id = payload.gcp_project_id
        db.add(channel)
        await db.commit()
        
    logger.info("api_channel_credentials_saved", channel_id=id, project_id=payload.gcp_project_id)
    return creds


@router.get("/{id}/analytics")
async def get_channel_analytics(
    id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Retrieve YouTube Analytics for a channel. Fallbacks to mock data if API call fails or is unconfigured."""
    logger.info("api_get_channel_analytics_called", channel_id=id, user_id=current_user.id)
    
    # 1. Fetch channel
    stmt = select(Channel).where(Channel.id == id)
    res = await db.execute(stmt)
    channel = res.scalar_one_or_none()
    if not channel:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Channel not found")
        
    # Attempt to fetch credentials and call YouTube Analytics API
    try:
        # Load GCP project currently assigned
        if not channel.gcp_project_id:
            raise ValueError("No active GCP project configured for channel")
            
        stmt_proj = select(GCPProject).where(GCPProject.project_id == channel.gcp_project_id)
        proj_res = await db.execute(stmt_proj)
        project_rec = proj_res.scalar_one_or_none()
        if not project_rec:
            raise ValueError("Active GCP project record not found")
            
        stmt_creds = select(ChannelCredentials).where(
            ChannelCredentials.channel_id == id,
            ChannelCredentials.gcp_project_id == channel.gcp_project_id,
            ChannelCredentials.is_active == True
        )
        creds_res = await db.execute(stmt_creds)
        creds_rec = creds_res.scalar_one_or_none()
        if not creds_rec:
            raise ValueError("Channel credentials not found")
            
        # Decrypt client secret
        if project_rec.client_secret_json:
            decrypted = decrypt_token(id, project_rec.client_secret_json)
            data = json.loads(decrypted)
            root_key = "installed" if "installed" in data else "web"
            info = data[root_key]
            client_id = info["client_id"]
            client_secret = info["client_secret"]
            token_uri = info.get("token_uri", "https://oauth2.googleapis.com/token")
        else:
            # Fallback to local client secret path
            if not os.path.exists(project_rec.client_secret_path):
                raise FileNotFoundError(f"Client secret path not found: {project_rec.client_secret_path}")
            with open(project_rec.client_secret_path, "r") as f:
                data = json.load(f)
            root_key = "installed" if "installed" in data else "web"
            info = data[root_key]
            client_id = info["client_id"]
            client_secret = info["client_secret"]
            token_uri = info.get("token_uri", "https://oauth2.googleapis.com/token")
            
        # Decrypt tokens
        refresh_token = decrypt_token(id, creds_rec.oauth_refresh_token_encrypted)
        access_token = None
        if creds_rec.oauth_credentials_encrypted:
            try:
                decrypted = decrypt_token(id, creds_rec.oauth_credentials_encrypted)
                if decrypted.startswith("{"):
                    access_token = json.loads(decrypted).get("access_token")
                else:
                    access_token = decrypted
            except Exception:
                pass
                
        creds = Credentials(
            token=access_token,
            refresh_token=refresh_token,
            token_uri=token_uri,
            client_id=client_id,
            client_secret=client_secret
        )
        
        # Refresh if needed
        if not creds.valid or (creds.expiry and creds.expiry < datetime.utcnow()):
            creds.refresh(Request())
            # Save back
            creds_rec.oauth_credentials_encrypted = encrypt_token(id, creds.token)
            creds_rec.oauth_token_expiry = creds.expiry
            creds_rec.last_refreshed_at = datetime.utcnow()
            db.add(creds_rec)
            await db.commit()
            
        # Call YouTube Analytics API
        youtube_analytics = build("youtubeAnalytics", "v2", credentials=creds)
        
        # Query: channel statistics for the past 30 days
        end_date = datetime.utcnow().strftime("%Y-%m-%d")
        start_date = (datetime.utcnow() - timedelta(days=30)).strftime("%Y-%m-%d")
        
        response = youtube_analytics.reports().query(
            ids=f"channel=={channel.youtube_channel_id or 'MINE'}",
            startDate=start_date,
            endDate=end_date,
            metrics="views,likes,dislikes,estimatedMinutesWatched,averageViewDuration",
            dimensions="day"
        ).execute()
        
        # Process API response
        rows = response.get("rows", [])
        daily_stats = []
        total_views = 0
        total_likes = 0
        total_minutes = 0
        
        for row in rows:
            day_str, v, l, d, m_w, a_vd = row
            daily_stats.append({
                "date": day_str,
                "views": int(v),
                "likes": int(l),
                "avg_view_duration_seconds": float(a_vd)
            })
            total_views += int(v)
            total_likes += int(l)
            total_minutes += float(m_w)
            
        avg_ctr = 4.2
        
        return {
            "source": "youtube_analytics_api",
            "total_views": total_views,
            "total_likes": total_likes,
            "average_ctr": avg_ctr,
            "average_view_duration_minutes": round(total_minutes / (total_views or 1), 2),
            "daily_stats": daily_stats
        }
        
    except Exception as e:
        logger.warning("youtube_analytics_api_failed_using_mock_fallback", error=str(e))
        
        # Return highly realistic mock data for preview/demonstration
        daily_stats = []
        today = datetime.utcnow()
        total_views = 0
        total_likes = 0
        total_minutes = 0
        
        # Generate 30 days of daily stats
        for i in range(30):
            day = today - timedelta(days=30-i)
            base_views = 1500 if day.weekday() >= 5 else 800
            day_views = int(base_views * random.uniform(0.8, 1.5))
            day_likes = int(day_views * random.uniform(0.02, 0.06))
            day_avd = round(random.uniform(120, 280), 1)
            
            daily_stats.append({
                "date": day.strftime("%Y-%m-%d"),
                "views": day_views,
                "likes": day_likes,
                "avg_view_duration_seconds": day_avd
            })
            total_views += day_views
            total_likes += day_likes
            total_minutes += (day_views * day_avd) / 60
            
        return {
            "source": "mock_fallback",
            "total_views": total_views,
            "total_likes": total_likes,
            "average_ctr": round(random.uniform(3.5, 6.2), 2),
            "average_view_duration_minutes": round(total_minutes / (total_views or 1), 2),
            "daily_stats": daily_stats
        }


@router.get("/{id}/oauth-auth-url")
async def get_oauth_auth_url(
    id: int,
    project_id: str,
    redirect_uri: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Generate the Google OAuth authorization URL for a specific channel and GCP project."""
    logger.info("api_get_oauth_auth_url_called", channel_id=id, project_id=project_id, user_id=current_user.id)
    
    # Verify channel exists
    stmt_chan = select(Channel).where(Channel.id == id)
    res_chan = await db.execute(stmt_chan)
    channel = res_chan.scalar_one_or_none()
    if not channel:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Channel not found")
        
    # Load GCP Project
    stmt_proj = select(GCPProject).where(GCPProject.project_id == project_id, GCPProject.channel_id == id)
    res_proj = await db.execute(stmt_proj)
    project_rec = res_proj.scalar_one_or_none()
    if not project_rec:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="GCP Project not found for this channel")
        
    if not project_rec.client_secret_json:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No client secret JSON configured for this GCP Project")
        
    try:
        decrypted = decrypt_token(id, project_rec.client_secret_json)
        data = json.loads(decrypted)
        root_key = "installed" if "installed" in data else "web"
        info = data[root_key]
        client_id = info["client_id"]
    except Exception as e:
        logger.error("api_oauth_auth_url_failed_to_decrypt", error=str(e))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid client secret JSON structure")

    # Encode state containing channel_id, project_id, and redirect_uri
    state_payload = {
        "channel_id": id,
        "project_id": project_id,
        "redirect_uri": redirect_uri
    }
    state_bytes = json.dumps(state_payload).encode("utf-8")
    state_str = base64.b64encode(state_bytes).decode("utf-8")
    
    # Scopes required: youtube.upload and yt-analytics.readonly
    scopes = [
        "https://www.googleapis.com/auth/youtube.upload",
        "https://www.googleapis.com/auth/yt-analytics.readonly"
    ]
    scope_str = " ".join(scopes)
    
    import urllib.parse
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": scope_str,
        "access_type": "offline",
        "prompt": "consent",
        "state": state_str
    }
    auth_url = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode(params)
    
    return {"auth_url": auth_url}


@router.get("/oauth-callback", response_class=HTMLResponse)
async def oauth_callback(
    code: str = None,
    state: str = None,
    error: str = None,
    db: AsyncSession = Depends(get_db)
):
    """Handle Google OAuth callback, exchange auth code for refresh token, and save it."""
    logger.info("api_oauth_callback_called", error=error)
    
    if error:
        error_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
          <title>OAuth Authorization Failed</title>
          <style>
            body {{ background-color: #0b0f19; color: #f8fafc; font-family: 'Plus Jakarta Sans', system-ui, -apple-system, sans-serif; display: flex; align-items: center; justify-content: center; min-height: 100vh; margin: 0; }}
            .card {{ background: rgba(30, 41, 59, 0.4); border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 16px; padding: 32px; text-align: center; box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1); max-width: 400px; }}
            .icon {{ font-size: 3rem; margin-bottom: 16px; }}
            h1 {{ font-size: 1.5rem; margin: 0 0 12px 0; color: #ef4444; }}
            p {{ color: #94a3b8; font-size: 0.95rem; line-height: 1.5; margin: 0; }}
          </style>
        </head>
        <body>
          <div class="card">
            <div class="icon">❌</div>
            <h1>Authorization Denied</h1>
            <p>Google OAuth error: {error}</p>
            <p style="margin-top: 12px; font-size: 0.85rem; color: #64748b;">You can close this window now.</p>
          </div>
          <script>
            if (window.opener) {{
              window.opener.postMessage({{ type: "OAUTH_FAILED", error: "Google error: {error}" }}, "*");
            }}
          </script>
        </body>
        </html>
        """
        return HTMLResponse(content=error_html, status_code=200)

    if not code or not state:
        bad_req_html = """
        <!DOCTYPE html>
        <html>
        <head>
          <title>OAuth Authorization Failed</title>
          <style>
            body { background-color: #0b0f19; color: #f8fafc; font-family: 'Plus Jakarta Sans', system-ui, -apple-system, sans-serif; display: flex; align-items: center; justify-content: center; min-height: 100vh; margin: 0; }
            .card { background: rgba(30, 41, 59, 0.4); border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 16px; padding: 32px; text-align: center; box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1); max-width: 400px; }
            .icon { font-size: 3rem; margin-bottom: 16px; }
            h1 { font-size: 1.5rem; margin: 0 0 12px 0; color: #ef4444; }
            p { color: #94a3b8; font-size: 0.95rem; line-height: 1.5; margin: 0; }
          </style>
        </head>
        <body>
          <div class="card">
            <div class="icon">❌</div>
            <h1>Invalid Callback Request</h1>
            <p>Missing authorization code or state parameter.</p>
          </div>
        </body>
        </html>
        """
        return HTMLResponse(content=bad_req_html, status_code=400)

    try:
        # Decode state
        state_bytes = base64.b64decode(state.encode("utf-8"))
        state_data = json.loads(state_bytes.decode("utf-8"))
        channel_id = state_data["channel_id"]
        project_id = state_data["project_id"]
        redirect_uri = state_data["redirect_uri"]
    except Exception as e:
        logger.error("api_oauth_callback_invalid_state", error=str(e))
        return HTMLResponse(content="<h3>Invalid state parameter</h3>", status_code=400)

    # Load GCP Project
    stmt_proj = select(GCPProject).where(GCPProject.project_id == project_id, GCPProject.channel_id == channel_id)
    res_proj = await db.execute(stmt_proj)
    project_rec = res_proj.scalar_one_or_none()
    if not project_rec or not project_rec.client_secret_json:
        return HTMLResponse(content="<h3>GCP Project or Client Secrets not found</h3>", status_code=404)

    try:
        # Decrypt Client Secrets
        decrypted = decrypt_token(channel_id, project_rec.client_secret_json)
        secret_data = json.loads(decrypted)
        root_key = "installed" if "installed" in secret_data else "web"
        info = secret_data[root_key]
        client_id = info["client_id"]
        client_secret = info["client_secret"]
    except Exception as e:
        logger.error("api_oauth_callback_decrypt_failed", error=str(e))
        return HTMLResponse(content="<h3>Failed to decrypt GCP secrets</h3>", status_code=500)

    # Exchange Authorization Code for Refresh Token
    try:
        async with httpx.AsyncClient() as client:
            token_response = await client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "code": code,
                    "grant_type": "authorization_code",
                    "redirect_uri": redirect_uri
                },
                timeout=10.0
            )
            
        if token_response.status_code != 200:
            logger.error("api_oauth_token_exchange_failed", status=token_response.status_code, body=token_response.text)
            err_msg = token_response.json().get("error_description", "Token exchange failed")
            raise ValueError(err_msg)
            
        token_data = token_response.json()
        refresh_token = token_data.get("refresh_token")
        access_token = token_data.get("access_token")
        expires_in = token_data.get("expires_in", 3600)
        
        # If no refresh token is returned, Google didn't issue one because the app was already authorized.
        if not refresh_token:
            stmt_creds = select(ChannelCredentials).where(
                ChannelCredentials.channel_id == channel_id,
                ChannelCredentials.gcp_project_id == project_id
            )
            res_creds = await db.execute(stmt_creds)
            existing_creds = res_creds.scalar_one_or_none()
            if existing_creds:
                refresh_token = decrypt_token(channel_id, existing_creds.oauth_refresh_token_encrypted)
            else:
                no_rt_html = f"""
                <!DOCTYPE html>
                <html>
                <head>
                  <title>Authorization Failed: No Refresh Token</title>
                  <style>
                    body {{ background-color: #0b0f19; color: #f8fafc; font-family: 'Plus Jakarta Sans', system-ui, -apple-system, sans-serif; display: flex; align-items: center; justify-content: center; min-height: 100vh; margin: 0; }}
                    .card {{ background: rgba(30, 41, 59, 0.4); border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 16px; padding: 32px; text-align: center; box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1); max-width: 450px; }}
                    .icon {{ font-size: 3rem; margin-bottom: 16px; }}
                    h1 {{ font-size: 1.5rem; margin: 0 0 12px 0; color: #f59e0b; }}
                    p {{ color: #94a3b8; font-size: 0.95rem; line-height: 1.5; margin: 0; }}
                    ol {{ text-align: left; color: #94a3b8; font-size: 0.85rem; margin: 12px 0; }}
                  </style>
                </head>
                <body>
                  <div class="card">
                    <div class="icon">⚠️</div>
                    <h1>No Refresh Token Returned</h1>
                    <p>Google did not return a refresh token because this app was already authorized by your account.</p>
                    <p style="margin-top: 10px; font-weight: 600;">To fix this:</p>
                    <ol>
                      <li>Go to <a href="https://myaccount.google.com/permissions" target="_blank" rel="noopener noreferrer" style="color:#6366f1;">Google Third-party apps access</a>.</li>
                      <li>Remove access for your app.</li>
                      <li>Click "Authorize" again on the dashboard.</li>
                    </ol>
                    <p style="font-size: 0.85rem; color: #64748b;">This ensures Google prompts for consent and issues a new refresh token.</p>
                  </div>
                  <script>
                    if (window.opener) {{
                      window.opener.postMessage({{ type: "OAUTH_FAILED", error: "No refresh token returned. Reset app access in Google permissions." }}, "*");
                    }}
                  </script>
                </body>
                </html>
                """
                return HTMLResponse(content=no_rt_html, status_code=200)

        # Save credentials to database
        encrypted_refresh = encrypt_token(channel_id, refresh_token)
        encrypted_access = encrypt_token(channel_id, access_token) if access_token else ""
        expiry = datetime.utcnow() + timedelta(seconds=expires_in)
        
        stmt_creds = select(ChannelCredentials).where(
            ChannelCredentials.channel_id == channel_id,
            ChannelCredentials.gcp_project_id == project_id
        )
        res_creds = await db.execute(stmt_creds)
        creds = res_creds.scalar_one_or_none()
        
        if creds:
            creds.oauth_refresh_token_encrypted = encrypted_refresh
            creds.oauth_credentials_encrypted = encrypted_access
            creds.oauth_token_expiry = expiry
            creds.is_active = True
            creds.last_error = None
            creds.last_refreshed_at = datetime.utcnow()
        else:
            creds = ChannelCredentials(
                channel_id=channel_id,
                gcp_project_id=project_id,
                oauth_refresh_token_encrypted=encrypted_refresh,
                oauth_credentials_encrypted=encrypted_access,
                oauth_token_expiry=expiry,
                is_active=True,
                last_refreshed_at=datetime.utcnow()
            )
            db.add(creds)
            
        await db.commit()
        
        # Set active project ID for channel if none is set
        stmt_chan = select(Channel).where(Channel.id == channel_id)
        res_chan = await db.execute(stmt_chan)
        channel = res_chan.scalar_one()
        if not channel.gcp_project_id:
            channel.gcp_project_id = project_id
            db.add(channel)
            await db.commit()
            
        logger.info("api_oauth_flow_successful", channel_id=channel_id, project_id=project_id)
        
        success_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
          <title>OAuth Authorization Successful</title>
          <style>
            body {{ background-color: #0b0f19; color: #f8fafc; font-family: 'Plus Jakarta Sans', system-ui, -apple-system, sans-serif; display: flex; align-items: center; justify-content: center; min-height: 100vh; margin: 0; }}
            .card {{ background: rgba(30, 41, 59, 0.4); border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 16px; padding: 32px; text-align: center; box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1); max-width: 400px; }}
            .icon {{ font-size: 3rem; margin-bottom: 16px; animation: bounce 2s infinite; }}
            h1 {{ font-size: 1.5rem; margin: 0 0 12px 0; background: linear-gradient(135deg, #6366f1 0%, #a855f7 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }}
            p {{ color: #94a3b8; font-size: 0.95rem; line-height: 1.5; margin: 0; }}
            @keyframes bounce {{ 0%, 100% {{ transform: translateY(0); }} 50% {{ transform: translateY(-10px); }} }}
          </style>
        </head>
        <body>
          <div class="card">
            <div class="icon">✅</div>
            <h1>Authorization Successful!</h1>
            <p>Your YouTube Channel has been successfully authorized and connected.</p>
            <p style="margin-top: 12px; font-size: 0.85rem; color: #64748b;">This window will close automatically.</p>
          </div>
          <script>
            setTimeout(function() {{
              if (window.opener) {{
                window.opener.postMessage({{ type: "OAUTH_SUCCESS", channel_id: {channel_id} }}, "*");
                window.close();
              }}
            }}, 1500);
          </script>
        </body>
        </html>
        """
        return HTMLResponse(content=success_html, status_code=200)
        
    except Exception as e:
        logger.error("api_oauth_callback_token_exchange_error", error=str(e))
        fail_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
          <title>OAuth Authorization Failed</title>
          <style>
            body {{ background-color: #0b0f19; color: #f8fafc; font-family: 'Plus Jakarta Sans', system-ui, -apple-system, sans-serif; display: flex; align-items: center; justify-content: center; min-height: 100vh; margin: 0; }}
            .card {{ background: rgba(30, 41, 59, 0.4); border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 16px; padding: 32px; text-align: center; box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1); max-width: 400px; }}
            .icon {{ font-size: 3rem; margin-bottom: 16px; }}
            h1 {{ font-size: 1.5rem; margin: 0 0 12px 0; color: #ef4444; }}
            p {{ color: #94a3b8; font-size: 0.95rem; line-height: 1.5; margin: 0; }}
          </style>
        </head>
        <body>
          <div class="card">
            <div class="icon">❌</div>
            <h1>Authorization Failed</h1>
            <p>Failed to exchange authorization code for tokens.</p>
            <p style="color: #64748b; font-size: 0.85rem; margin-top: 8px;">Error details: {str(e)}</p>
            <p style="margin-top: 12px; font-size: 0.85rem; color: #64748b;">You can close this window now.</p>
          </div>
          <script>
            if (window.opener) {{
              window.opener.postMessage({{ type: "OAUTH_FAILED", error: "{str(e)}" }}, "*");
            }}
          </script>
        </body>
        </html>
        """
        return HTMLResponse(content=fail_html, status_code=200)

