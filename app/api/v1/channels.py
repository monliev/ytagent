from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
import structlog

from app.api.deps import get_db, get_current_user
from app.models.channel import Channel
from app.models.user import User
from app.schemas.channel import ChannelCreate, ChannelUpdate, ChannelResponse

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
