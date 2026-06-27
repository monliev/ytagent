from datetime import datetime, date, time, timedelta
from typing import Optional
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.channel import Channel
from app.models.video import Video, VideoStatus

async def calculate_next_schedule_time(db: AsyncSession, channel: Channel) -> datetime:
    """Calculate the next available schedule time slot for a video on the channel.
    
    Considers the channel's `upload_days_interval` and `preferred_upload_times`.
    """
    # 1. Parse preferred times
    pref_times_str = getattr(channel, "preferred_upload_times", None)
    times = []
    if pref_times_str and pref_times_str.strip():
        # Split by comma and parse each as HH:MM
        for part in pref_times_str.split(","):
            part = part.strip()
            if not part:
                continue
            try:
                t_parts = [int(x) for x in part.split(":")]
                if len(t_parts) >= 2:
                    h, m = t_parts[0], t_parts[1]
                    s = t_parts[2] if len(t_parts) > 2 else 0
                    times.append(time(h, m, s))
            except Exception:
                pass
                
    # Sort times chronologically
    times = sorted(list(set(times)))
    if not times:
        # Fall back to single preferred_time
        pref_time = channel.preferred_time or time(10, 0, 0)
        times = [pref_time]
        
    # 2. Get days interval
    days_interval = getattr(channel, "upload_days_interval", 1) or 1
    if days_interval <= 0:
        days_interval = 1

    # 3. Check for any future scheduled/queued/uploaded videos
    stmt_max = select(func.max(Video.scheduled_time)).where(
        Video.channel_id == channel.id,
        Video.scheduled_time >= datetime.now(),
        Video.status.in_([VideoStatus.APPROVED, VideoStatus.QUEUED, VideoStatus.UPLOADING, VideoStatus.UPLOADED])
    )
    res_max = await db.execute(stmt_max)
    max_sched = res_max.scalar()
    
    if max_sched:
        max_date = max_sched.date()
        max_time = max_sched.time()
        
        # Find the first preferred time strictly greater than max_time
        next_time = None
        for t in times:
            if t > max_time:
                next_time = t
                break
                
        if next_time:
            return datetime.combine(max_date, next_time)
        else:
            # Move to next active day
            next_date = max_date + timedelta(days=days_interval)
            return datetime.combine(next_date, times[0])
    else:
        # Relative to now
        now = datetime.now()
        now_date = now.date()
        
        # Find the first preferred time today that is in the future
        next_time = None
        for t in times:
            if datetime.combine(now_date, t) > now:
                next_time = t
                break
                
        if next_time:
            return datetime.combine(now_date, next_time)
        else:
            # Tomorrow at first slot
            return datetime.combine(now_date + timedelta(days=1), times[0])
