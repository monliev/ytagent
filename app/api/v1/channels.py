from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
import structlog

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
