import os
import shutil
import subprocess
import pytest
from sqlalchemy import select
from httpx import AsyncClient

from app.main import app
from app.core.database import AsyncSessionLocal, engine
from app.models import Channel, Video, MetadataDraft, ThumbnailDraft, SystemLog, VideoStatus
import asyncio

@pytest.fixture(scope="module", autouse=True)
def event_loop():
    """Create a module-scoped event loop so all tests run inside the same event loop context."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    loop.close()

@pytest.fixture(scope="module", autouse=True)
async def dispose_engine():
    """Dispose the SQLAlchemy engine connection pool at the end of the module test run."""
    yield
    await engine.dispose()

TEST_NAS_DIR = os.path.abspath("test_nas")
CHANNEL_NAME = "Lofi_Relaxing"
CHANNEL_DIR = os.path.join(TEST_NAS_DIR, CHANNEL_NAME)
VIDEO_FILENAME = "lofi_chill_study_03h.mp4"
VIDEO_PATH = os.path.join(CHANNEL_DIR, VIDEO_FILENAME)

@pytest.fixture(scope="module", autouse=True)
def setup_dummy_video():
    """Create directory structure and generate a dummy 5-second MP4 video using ffmpeg."""
    from app.core.database import sync_engine
    from sqlalchemy.orm import Session
    
    # Sync database cleanup before the test run to prevent pollution
    with Session(sync_engine) as session:
        session.query(Video).filter(Video.file_path.like("%Lofi_Relaxing%")).delete(synchronize_session=False)
        session.query(Channel).filter(Channel.name == "Lofi_Relaxing").delete(synchronize_session=False)
        session.commit()

    os.makedirs(CHANNEL_DIR, exist_ok=True)
    
    # Generate a real 5-second video using ffmpeg so ffprobe/ffmpeg extraction doesn't fail
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", "color=c=black:s=640x360:d=5",
        "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono",
        "-c:v", "libx264", "-c:a", "aac",
        "-pix_fmt", "yuv420p", "-t", "5",
        VIDEO_PATH
    ]
    subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    
    yield

    
    # Clean up files and directory after tests finish
    if os.path.exists(TEST_NAS_DIR):
        shutil.rmtree(TEST_NAS_DIR)

@pytest.mark.asyncio
async def test_video_ingestion_pipeline():
    # 1. Setup Channel in DB
    async with AsyncSessionLocal() as session:
        # Check if test channel already exists (cleanup from previous crashes)
        stmt = select(Channel).where(Channel.name == CHANNEL_NAME)
        res = await session.execute(stmt)
        channel = res.scalar_one_or_none()
        
        if not channel:
            channel = Channel(
                name=CHANNEL_NAME,
                genre="lofi",
                folder_path=CHANNEL_DIR,
                is_active=True,
                thumbnail_style_name="default",
                thumbnail_style_prompt="warm fireplace lofi art style",
                preset_title_template="{mood} lofi mix for {activity}",
                preset_description_template="Enjoy this {genre} selection for {activity}."
            )
            session.add(channel)
            await session.commit()
            await session.refresh(channel)
        
        channel_id = channel.id

    # 2. Trigger the ingestion webhook endpoint
    payload = {
        "filename": VIDEO_FILENAME,
        "file_path": VIDEO_PATH,
        "file_size_bytes": os.path.getsize(VIDEO_PATH),
        "channel_name": CHANNEL_NAME
    }
    
    from httpx import AsyncClient, ASGITransport
    transport = ASGITransport(app=app)
    
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post("/api/v1/videos/detect", json=payload)

        
    assert response.status_code == 201, f"Response failed: {response.text}"
    resp_data = response.json()
    assert resp_data["filename"] == VIDEO_FILENAME
    assert resp_data["status"] == "staging"
    assert resp_data["duration_seconds"] == 5
    assert resp_data["resolution"] == "640x360"
    
    video_id = resp_data["id"]
    
    # 3. Verify Database Records
    async with AsyncSessionLocal() as db:
        # Check Video
        res_vid = await db.execute(select(Video).where(Video.id == video_id))
        video_rec = res_vid.scalar_one_or_none()
        assert video_rec is not None
        assert video_rec.status == VideoStatus.STAGING
        assert video_rec.screenshot_path is not None
        assert os.path.exists(video_rec.screenshot_path)
        
        # Check Metadata Draft
        res_meta = await db.execute(select(MetadataDraft).where(MetadataDraft.video_id == video_id))
        meta_draft = res_meta.scalars().all()
        assert len(meta_draft) == 1
        assert meta_draft[0].title == "Chill lofi mix for Study"  # derived from lofi_chill_study_03h.mp4 keywords
        
        # Check Thumbnail Drafts
        res_thumb = await db.execute(select(ThumbnailDraft).where(ThumbnailDraft.video_id == video_id))
        thumbs = res_thumb.scalars().all()
        assert len(thumbs) > 0  # Should fall back to PIL and generate at least 1 fallback thumbnail
        for thumb in thumbs:
            assert os.path.exists(thumb.image_path)
            
        # Check System Log
        res_logs = await db.execute(select(SystemLog).where(SystemLog.video_id == video_id))
        logs = res_logs.scalars().all()
        assert len(logs) >= 2  # one for detection, one for completion
        event_types = [l.event_type for l in logs]
        assert "video_detected" in event_types
        assert "video_prepared" in event_types

        # Clean up database entries for this test
        await db.delete(video_rec)  # Cascade deletes should clean up drafts and logs
        await db.delete(channel)
        await db.commit()
