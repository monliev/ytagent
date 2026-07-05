import asyncio
from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.models.channel import Channel
from app.models.video import Video, VideoStatus
from app.utils.scheduling import calculate_next_schedule_time

async def fix_schedules():
    print("Starting database schedule cleanup...")
    async with AsyncSessionLocal() as db:
        # Get all active channels
        res_ch = await db.execute(select(Channel).where(Channel.is_active == True))
        channels = res_ch.scalars().all()
        
        for channel in channels:
            print(f"\nProcessing channel: {channel.name} (ID: {channel.id})")
            
            # Fetch all approved and queued videos for this channel, sorted chronologically
            stmt = select(Video).where(
                Video.channel_id == channel.id,
                Video.status.in_([VideoStatus.APPROVED, VideoStatus.QUEUED])
            ).order_by(Video.scheduled_time.asc(), Video.id.asc())
            res_vid = await db.execute(stmt)
            videos = res_vid.scalars().all()
            
            if not videos:
                print("  No approved or queued videos found.")
                continue
                
            print(f"  Found {len(videos)} videos. Temporarily clearing their scheduled times to rebuild queue...")
            
            # 1. Temporarily clear scheduled times to prevent the scheduler from building
            # on top of existing/collided schedules for the same videos we are reorganizing.
            for video in videos:
                video.scheduled_time = None
                db.add(video)
            await db.commit()
            
            # 2. Re-calculate and assign schedule times sequentially
            for idx, video in enumerate(videos):
                new_time = await calculate_next_schedule_time(db, channel)
                video.scheduled_time = new_time
                db.add(video)
                # Commit each one immediately so it is seen by the next calculate_next_schedule_time query
                await db.commit()
                print(f"    [{idx+1}/{len(videos)}] Rescheduled video ID {video.id} -> {new_time.strftime('%Y-%m-%d %H:%M:%S')}")
                
        print("\nAll channel queues reorganized successfully (1 video per active slot)!")

if __name__ == "__main__":
    asyncio.run(fix_schedules())
