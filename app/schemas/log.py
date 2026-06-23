from datetime import datetime
from typing import Optional, Any, List, Dict
from pydantic import BaseModel
from app.models.system_log import LogLevel

class SystemLogResponse(BaseModel):
    id: int
    level: LogLevel
    service: str
    event_type: str
    video_id: Optional[int] = None
    channel_id: Optional[int] = None
    user_id: Optional[int] = None
    message: str
    details: Optional[Dict[str, Any]] = None
    source_ip: Optional[str] = None
    request_id: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True

class SystemLogsPaginated(BaseModel):
    items: List[SystemLogResponse]
    total: int
    page: int
    size: int
