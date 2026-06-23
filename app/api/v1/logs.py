from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Optional

from app.api.deps import get_db, get_current_user
from app.models.system_log import SystemLog, LogLevel
from app.models.user import User
from app.schemas.log import SystemLogsPaginated

router = APIRouter()

@router.get("/", response_model=SystemLogsPaginated)
async def list_logs(
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(50, ge=1, le=100, description="Items per page"),
    level: Optional[LogLevel] = Query(None, description="Filter by log level"),
    service: Optional[str] = Query(None, description="Filter by service name"),
    event_type: Optional[str] = Query(None, description="Filter by event type"),
    video_id: Optional[int] = Query(None, description="Filter by related video ID"),
    channel_id: Optional[int] = Query(None, description="Filter by related channel ID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> SystemLogsPaginated:
    """Retrieve system logs with pagination and filters."""
    # Build count and select query
    query = select(SystemLog)
    
    if level:
        query = query.where(SystemLog.level == level)
    if service:
        query = query.where(SystemLog.service == service)
    if event_type:
        query = query.where(SystemLog.event_type == event_type)
    if video_id:
        query = query.where(SystemLog.video_id == video_id)
    if channel_id:
        query = query.where(SystemLog.channel_id == channel_id)
        
    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    count_res = await db.execute(count_query)
    total = count_res.scalar() or 0
    
    # Get paginated items
    offset = (page - 1) * size
    stmt = query.order_by(SystemLog.created_at.desc()).offset(offset).limit(size)
    res = await db.execute(stmt)
    items = res.scalars().all()
    
    return SystemLogsPaginated(
        items=items,
        total=total,
        page=page,
        size=size
    )
