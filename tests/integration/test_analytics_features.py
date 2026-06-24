import pytest
import asyncio
from unittest.mock import patch, MagicMock
from sqlalchemy import select, delete
from httpx import AsyncClient, ASGITransport
from datetime import datetime, timedelta
from decimal import Decimal

from app.main import app
from app.core.database import AsyncSessionLocal, engine
from app.core.security import hash_password
from app.models.user import User, UserRole
from app.models.channel import Channel
from app.models.video import Video, VideoStatus
from app.models.analytics_record import AnalyticsRecord
from app.models.performance_insight import PerformanceInsight
from app.tasks.analytics import sync_youtube_analytics

@pytest.fixture(scope="module", autouse=True)
def event_loop():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    loop.close()

@pytest.fixture(scope="module", autouse=True)
async def dispose_engine():
    yield
    await engine.dispose()

@pytest.fixture(scope="function", autouse=True)
async def cleanup_db():
    async with AsyncSessionLocal() as db:
        # Delete test records
        await db.execute(delete(PerformanceInsight))
        await db.execute(delete(AnalyticsRecord))
        
        stmt_vid = select(Video).where(Video.filename.like("test_analytics_file%"))
        vid_res = await db.execute(stmt_vid)
        for v in vid_res.scalars().all():
            await db.delete(v)
            
        stmt_ch = select(Channel).where(Channel.name.like("Test_Ch_Analytics%"))
        ch_res = await db.execute(stmt_ch)
        for c in ch_res.scalars().all():
            await db.delete(c)
            
        stmt_usr = select(User).where(User.username.like("test_analytics_user%"))
        usr_res = await db.execute(stmt_usr)
        for u in usr_res.scalars().all():
            await db.delete(u)
            
        await db.commit()

    yield

    async with AsyncSessionLocal() as db:
        await db.execute(delete(PerformanceInsight))
        await db.execute(delete(AnalyticsRecord))
        
        stmt_vid = select(Video).where(Video.filename.like("test_analytics_file%"))
        vid_res = await db.execute(stmt_vid)
        for v in vid_res.scalars().all():
            await db.delete(v)
            
        stmt_ch = select(Channel).where(Channel.name.like("Test_Ch_Analytics%"))
        ch_res = await db.execute(stmt_ch)
        for c in ch_res.scalars().all():
            await db.delete(c)
            
        stmt_usr = select(User).where(User.username.like("test_analytics_user%"))
        usr_res = await db.execute(stmt_usr)
        for u in usr_res.scalars().all():
            await db.delete(u)
            
        await db.commit()

@pytest.mark.asyncio
async def test_analytics_api_endpoints():
    # Setup test objects
    async with AsyncSessionLocal() as db:
        user = User(
            telegram_id=888777666,
            username="test_analytics_user_api",
            full_name="Analytics tester",
            role=UserRole.SUPERVISOR,
            hashed_password=hash_password("pass1234"),
            is_active=True
        )
        channel = Channel(
            name="Test_Ch_Analytics_API",
            genre="education",
            folder_path="/mnt/nas/Test_Ch_Analytics_API",
            is_active=True
        )
        db.add_all([user, channel])
        await db.commit()
        await db.refresh(channel)
        
        video = Video(
            channel_id=channel.id,
            filename="test_analytics_file.mp4",
            file_path="/mnt/nas/Test_Ch_Analytics_API/test_analytics_file.mp4",
            file_size_bytes=1024,
            youtube_video_id="TEST_YT_ID_123",
            status=VideoStatus.UPLOADED,
            uploaded_at=datetime.utcnow() - timedelta(days=1),
            current_title="Testing Analytics APIs"
        )
        db.add(video)
        await db.commit()
        await db.refresh(video)

        # Pre-seed an AnalyticsRecord and PerformanceInsight to test GET endpoints
        record = AnalyticsRecord(
            video_id=video.id,
            channel_id=channel.id,
            youtube_video_id="TEST_YT_ID_123",
            recorded_at=datetime.utcnow(),
            hours_since_publish=24,
            views=150,
            likes=10,
            ctr=Decimal("2.5"),
            avd_seconds=120,
            avd_percentage=Decimal("40.0")
        )
        insight = PerformanceInsight(
            channel_id=channel.id,
            video_id=video.id,
            insight_type="suggestion",
            title="CTR is low",
            message="Improve thumbnail design",
            severity="warning",
            suggested_action="Change color palette",
            is_read=False
        )
        db.add_all([record, insight])
        await db.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Login
        login_res = await ac.post("/api/v1/auth/login", json={
            "username": "test_analytics_user_api",
            "password": "pass1234"
        })
        assert login_res.status_code == 200
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 1. Get video analytics
        res_v = await ac.get(f"/api/v1/channels/{channel.id}/videos/analytics", headers=headers)
        assert res_v.status_code == 200
        data_v = res_v.json()
        assert len(data_v["videos"]) == 1
        assert data_v["videos"][0]["views"] == 150
        assert data_v["videos"][0]["youtube_video_id"] == "TEST_YT_ID_123"

        # 2. Get performance insights
        res_i = await ac.get(f"/api/v1/channels/{channel.id}/insights", headers=headers)
        assert res_i.status_code == 200
        data_i = res_i.json()
        assert len(data_i["insights"]) == 1
        assert data_i["insights"][0]["title"] == "CTR is low"
        assert data_i["insights"][0]["severity"] == "warning"

        # 3. Test manual sync endpoint (delay-mocked)
        with patch("app.tasks.analytics.sync_youtube_analytics.delay") as mock_delay:
            res_sync = await ac.post(f"/api/v1/channels/{channel.id}/analytics/sync", headers=headers)
            assert res_sync.status_code == 200
            assert "triggered successfully" in res_sync.json()["detail"]
            mock_delay.assert_called_once()
