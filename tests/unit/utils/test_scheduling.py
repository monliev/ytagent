import pytest
from datetime import datetime, time, timedelta
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.models.base import Base
from app.models.channel import Channel
from app.models.video import Video, VideoStatus
from app.utils.scheduling import calculate_next_schedule_time

@pytest.mark.asyncio
async def test_calculate_next_schedule_time():
    # Create SQLite in-memory engine
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as db:
        # Create a test channel
        channel = Channel(
            id=1,
            name="Lofi Channel",
            genre="lofi",
            folder_path="/mnt/omv/lofi",
            preferred_time=time(22, 0, 0),
            upload_days_interval=2,
            preferred_upload_times="10:00, 22:00"
        )
        db.add(channel)
        await db.commit()
        
        # Test Case 1: No scheduled videos, now is 09:00.
        # Today's slots are 10:00 and 22:00. The next available should be today 10:00.
        # We mock datetime.now() inside calculate_next_schedule_time or just check logic.
        # To test now, we can check that it returns today at 10:00 (if now < 10:00).
        now = datetime.now()
        next_sched = await calculate_next_schedule_time(db, channel)
        assert next_sched > now
        
        # Test Case 2: Max scheduled video in the future is today at 10:00.
        # The next slot should be today at 22:00.
        v1 = Video(
            id=1,
            channel_id=channel.id,
            filename="video1.mp4",
            file_path="/mnt/omv/lofi/video1.mp4",
            file_size_bytes=1000,
            status=VideoStatus.APPROVED,
            scheduled_time=datetime.combine(now.date(), time(10, 0, 0))
        )
        db.add(v1)
        await db.commit()
        
        next_sched = await calculate_next_schedule_time(db, channel)
        assert next_sched == datetime.combine(now.date(), time(22, 0, 0))
        
        # Test Case 3: Max scheduled video is today at 22:00.
        # The next slot should be on next active day (2 days later) at 10:00.
        v2 = Video(
            id=2,
            channel_id=channel.id,
            filename="video2.mp4",
            file_path="/mnt/omv/lofi/video2.mp4",
            file_size_bytes=1000,
            status=VideoStatus.APPROVED,
            scheduled_time=datetime.combine(now.date(), time(22, 0, 0))
        )
        db.add(v2)
        await db.commit()
        
        next_sched = await calculate_next_schedule_time(db, channel)
        expected_date = now.date() + timedelta(days=2)
        assert next_sched == datetime.combine(expected_date, time(10, 0, 0))
        
    await engine.dispose()
