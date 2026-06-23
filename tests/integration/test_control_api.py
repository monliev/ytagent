import pytest
import asyncio
from sqlalchemy import select
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.core.database import AsyncSessionLocal, engine
from app.core.security import hash_password, verify_password
from app.models.user import User, UserRole
from app.models.channel import Channel
from app.models.video import Video, VideoStatus, YoutubePrivacy
from app.models.metadata_draft import MetadataDraft, MetadataGenerationType
from app.models.thumbnail_draft import ThumbnailDraft
from app.models.system_log import SystemLog
from app.core.redis_client import redis_client

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

@pytest.fixture(scope="module", autouse=True)
async def cleanup_redis():
    """Disconnect the Redis client connection pool after all module tests complete."""
    yield
    try:
        await redis_client.connection_pool.disconnect()
    except Exception:
        pass




@pytest.fixture(scope="function")
async def db_session():
    """Provides a transactional database session for each test function."""
    async with AsyncSessionLocal() as session:
        yield session

@pytest.fixture(scope="function", autouse=True)
async def cleanup_db():
    """Cleans up test records from database tables to keep tests clean and isolated."""
    async with AsyncSessionLocal() as db:
        # Delete test channels and cascaded records
        stmt_ch = select(Channel).where(Channel.name.like("Test_Ch_%"))
        ch_res = await db.execute(stmt_ch)
        for ch in ch_res.scalars().all():
            await db.delete(ch)
            
        # Delete test users
        stmt_usr = select(User).where(User.username.like("test_%"))
        usr_res = await db.execute(stmt_usr)
        for usr in usr_res.scalars().all():
            await db.delete(usr)
            
        await db.commit()

    yield

    async with AsyncSessionLocal() as db:
        # Delete test channels and cascaded records
        stmt_ch = select(Channel).where(Channel.name.like("Test_Ch_%"))
        ch_res = await db.execute(stmt_ch)
        for ch in ch_res.scalars().all():
            await db.delete(ch)
            
        # Delete test users
        stmt_usr = select(User).where(User.username.like("test_%"))
        usr_res = await db.execute(stmt_usr)
        for usr in usr_res.scalars().all():
            await db.delete(usr)
            
        await db.commit()

@pytest.mark.asyncio
async def test_auth_login_and_me(db_session):
    # 1. Create a test user with a hashed password
    password = "super_secret_password"
    user = User(
        telegram_id=987654321,
        username="test_user_auth",
        full_name="Authenticated Supervisor",
        role=UserRole.SUPERVISOR,
        hashed_password=hash_password(password),
        is_active=True
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 2. Test successful login
        login_res = await ac.post("/api/v1/auth/login", json={
            "username": "test_user_auth",
            "password": password
        })
        assert login_res.status_code == 200, f"Login failed: {login_res.text}"
        token_data = login_res.json()
        assert "access_token" in token_data
        token = token_data["access_token"]
        
        # 3. Test me endpoint
        headers = {"Authorization": f"Bearer {token}"}
        me_res = await ac.get("/api/v1/auth/me", headers=headers)
        assert me_res.status_code == 200
        user_data = me_res.json()
        assert user_data["username"] == "test_user_auth"
        assert user_data["role"] == "supervisor"

@pytest.mark.asyncio
async def test_channels_crud(db_session):
    # Seed user for authentication
    user = User(
        telegram_id=987654321,
        username="test_ch_user",
        full_name="Channel Operator",
        role=UserRole.SUPERVISOR,
        hashed_password=hash_password("pass123"),
        is_active=True
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    # Login to get token
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        login_res = await ac.post("/api/v1/auth/login", json={
            "username": "test_ch_user",
            "password": "pass123"
        })
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        # Create Channel
        payload = {
            "name": "Test_Ch_Main",
            "genre": "ambient",
            "folder_path": "/var/test_nas/Test_Ch_Main",
            "preferred_time": "12:00:00",
            "is_active": True,
            "auto_approve": False
        }
        create_res = await ac.post("/api/v1/channels/", json=payload, headers=headers)
        assert create_res.status_code == 201, f"Failed to create channel: {create_res.text}"
        channel_id = create_res.json()["id"]
        
        # List Channels
        list_res = await ac.get("/api/v1/channels/", headers=headers)
        assert list_res.status_code == 200
        assert any(c["id"] == channel_id for c in list_res.json())
        
        # Retrieve specific Channel
        get_res = await ac.get(f"/api/v1/channels/{channel_id}", headers=headers)
        assert get_res.status_code == 200
        assert get_res.json()["name"] == "Test_Ch_Main"
        
        # Update Channel
        update_payload = {"genre": "chill_out"}
        update_res = await ac.put(f"/api/v1/channels/{channel_id}", json=update_payload, headers=headers)
        assert update_res.status_code == 200
        assert update_res.json()["genre"] == "chill_out"
        
        # Delete Channel
        del_res = await ac.delete(f"/api/v1/channels/{channel_id}", headers=headers)
        assert del_res.status_code == 204

@pytest.mark.asyncio
async def test_video_control_endpoints(db_session):
    # 1. Seed user and channel
    user = User(
        telegram_id=987654321,
        username="test_video_user",
        full_name="Video Operator",
        role=UserRole.SUPERVISOR,
        hashed_password=hash_password("pass123"),
        is_active=True
    )
    channel = Channel(
        name="Test_Ch_Video",
        genre="study",
        folder_path="/mnt/nas/Test_Ch_Video",
        preferred_time="15:00:00",
        is_active=True
    )
    db_session.add_all([user, channel])
    await db_session.commit()
    await db_session.refresh(user)
    await db_session.refresh(channel)
    
    # 2. Seed Video in STAGING status with metadata draft and thumbnail draft options
    video = Video(
        channel_id=channel.id,
        filename="test_video_file.mp4",
        file_path="/mnt/nas/Test_Ch_Video/test_video_file.mp4",
        file_size_bytes=1000000,
        status=VideoStatus.STAGING,
        youtube_privacy=YoutubePrivacy.PRIVATE,
        retry_count=0
    )
    db_session.add(video)
    await db_session.commit()
    await db_session.refresh(video)
    
    meta_draft = MetadataDraft(
        video_id=video.id,
        version_number=1,
        generation_type=MetadataGenerationType.AUTO,
        title="Initial Draft Title",
        description="Initial description draft",
        tags=["lofi", "study"],
        confidence_score=90.0,
        is_approved=False
    )
    thumb_draft = ThumbnailDraft(
        video_id=video.id,
        image_path="/mnt/nas/Test_Ch_Video/thumbnails/thumb_1.jpg",
        style_name="study_default",
        prompt_used="visual warm room prompt",
        confidence_score=85.0,
        is_selected=False
    )
    db_session.add_all([meta_draft, thumb_draft])
    await db_session.commit()
    await db_session.refresh(meta_draft)
    await db_session.refresh(thumb_draft)
    
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Login to get authorization
        login_res = await ac.post("/api/v1/auth/login", json={
            "username": "test_video_user",
            "password": "pass123"
        })
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        # Test 1: Get Staging Videos
        staging_res = await ac.get("/api/v1/videos/staging", headers=headers)
        assert staging_res.status_code == 200
        assert any(v["id"] == video.id for v in staging_res.json())
        
        # Test 2: Edit Metadata Draft
        meta_payload = {
            "title": "Stunning Custom Title",
            "description": "Custom detailed description.",
            "tags": ["ambient", "work", "focus"]
        }
        edit_res = await ac.put(f"/api/v1/videos/{video.id}/metadata", json=meta_payload, headers=headers)
        assert edit_res.status_code == 200
        assert edit_res.json()["current_title"] == "Stunning Custom Title"
        
        # Test 3: Get Thumbnail drafts
        thumbs_res = await ac.get(f"/api/v1/videos/{video.id}/thumbnails", headers=headers)
        assert thumbs_res.status_code == 200
        assert len(thumbs_res.json()) == 1
        assert thumbs_res.json()[0]["id"] == thumb_draft.id
        
        # Test 4: Select Thumbnail
        select_res = await ac.post(f"/api/v1/videos/{video.id}/thumbnail", json={"thumbnail_id": thumb_draft.id}, headers=headers)
        assert select_res.status_code == 200
        
        # Verify draft is selected in DB
        async with AsyncSessionLocal() as db_check:
            stmt_td = select(ThumbnailDraft).where(ThumbnailDraft.id == thumb_draft.id)
            td_res = await db_check.execute(stmt_td)
            td = td_res.scalar_one()
            assert td.is_selected is True
            
        # Test 5: Approve Video
        approve_res = await ac.post(f"/api/v1/videos/{video.id}/approve", headers=headers)
        assert approve_res.status_code == 200
        assert approve_res.json()["status"] == "approved"
        assert approve_res.json()["scheduled_time"] is not None
        
        # Clean up created entries
        async with AsyncSessionLocal() as db_clean:
            # Reload video
            v_stmt = select(Video).where(Video.id == video.id)
            v_res = await db_clean.execute(v_stmt)
            v_rec = v_res.scalar_one()
            await db_clean.delete(v_rec)
            
            c_stmt = select(Channel).where(Channel.id == channel.id)
            c_res = await db_clean.execute(c_stmt)
            c_rec = c_res.scalar_one()
            await db_clean.delete(c_rec)
            
            await db_clean.commit()

@pytest.mark.asyncio
async def test_telegram_webhook_callback(db_session):
    # 1. Seed user, channel, and staging video
    # Clean up duplicate supervisor if exists
    stmt_existing = select(User).where(User.telegram_id == 123456789)
    res_existing = await db_session.execute(stmt_existing)
    existing_user = res_existing.scalar_one_or_none()
    if existing_user:
        await db_session.delete(existing_user)
        await db_session.commit()

    user = User(
        telegram_id=123456789, # matches SUPERVISOR_TELEGRAM_ID
        username="test_supervisor_tg",
        full_name="Telegram Supervisor",
        role=UserRole.SUPERVISOR,
        hashed_password=hash_password("pass123"),
        is_active=True
    )
    channel = Channel(
        name="Test_Ch_TG",
        genre="relax",
        folder_path="/mnt/nas/Test_Ch_TG",
        preferred_time="09:00:00",
        is_active=True
    )
    db_session.add_all([user, channel])
    await db_session.commit()
    await db_session.refresh(user)
    await db_session.refresh(channel)
    
    video = Video(
        channel_id=channel.id,
        filename="test_tg_video.mp4",
        file_path="/mnt/nas/Test_Ch_TG/test_tg_video.mp4",
        file_size_bytes=500000,
        status=VideoStatus.STAGING,
        youtube_privacy=YoutubePrivacy.PRIVATE
    )
    db_session.add(video)
    await db_session.commit()
    await db_session.refresh(video)
    
    # 2. Trigger telegram webhook to approve video
    payload = {
        "update_id": 999999,
        "callback_query": {
            "id": "query_123",
            "from": {
                "id": 123456789,
                "is_bot": False,
                "first_name": "Supervisor",
                "username": "test_supervisor_tg"
            },
            "message": {
                "message_id": 8888,
                "chat": {
                    "id": 123456789,
                    "type": "private"
                },
                "text": "🎵 NEW VIDEO DETECTED"
            },
            "data": f"approve:{video.id}"
        }
    }
    
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post("/api/v1/telegram/webhook", json=payload)
        assert response.status_code == 200
        assert response.json()["status"] == "approved"
        
    # Verify the video state in database transitioned to APPROVED
    async with AsyncSessionLocal() as db_check:
        stmt = select(Video).where(Video.id == video.id)
        res = await db_check.execute(stmt)
        updated_video = res.scalar_one()
        assert updated_video.status == VideoStatus.APPROVED
        assert updated_video.scheduled_time is not None
        
        # Clean up database records
        await db_check.delete(updated_video)
        
        stmt_ch = select(Channel).where(Channel.id == channel.id)
        ch_res = await db_check.execute(stmt_ch)
        await db_check.delete(ch_res.scalar_one())
        
        await db_check.commit()


@pytest.mark.asyncio
async def test_video_retry_endpoint(db_session):
    # 1. Seed user, channel, and a FAILED video
    user = User(
        telegram_id=987654321,
        username="test_retry_usr",
        full_name="Retry Supervisor",
        role=UserRole.SUPERVISOR,
        hashed_password=hash_password("pass123"),
        is_active=True
    )
    channel = Channel(
        name="Test_Ch_Retry",
        genre="relax",
        folder_path="/mnt/nas/Test_Ch_Retry",
        preferred_time="09:00:00",
        is_active=True
    )
    db_session.add_all([user, channel])
    await db_session.commit()
    await db_session.refresh(user)
    await db_session.refresh(channel)
    
    video = Video(
        channel_id=channel.id,
        filename="test_failed_video.mp4",
        file_path="/mnt/nas/Test_Ch_Retry/test_failed_video.mp4",
        file_size_bytes=500000,
        status=VideoStatus.FAILED,
        retry_count=3,
        last_error="YouTube upload quota exceeded",
        youtube_privacy=YoutubePrivacy.PRIVATE
    )
    db_session.add(video)
    await db_session.commit()
    await db_session.refresh(video)
    
    # Login to get auth token
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        login_res = await ac.post("/api/v1/auth/login", json={
            "username": "test_retry_usr",
            "password": "pass123"
        })
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        # 2. Trigger retry
        response = await ac.post(f"/api/v1/videos/{video.id}/retry", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "approved"
        assert data["retry_count"] == 0
        assert data["last_error"] is None
        
    # Verify the video state in database
    async with AsyncSessionLocal() as db_check:
        stmt = select(Video).where(Video.id == video.id)
        res = await db_check.execute(stmt)
        updated_video = res.scalar_one()
        assert updated_video.status == VideoStatus.APPROVED
        assert updated_video.retry_count == 0
        assert updated_video.last_error is None
        
        # Clean up database records
        await db_check.delete(updated_video)
        
        stmt_ch = select(Channel).where(Channel.id == channel.id)
        ch_res = await db_check.execute(stmt_ch)
        await db_check.delete(ch_res.scalar_one())
        
        await db_check.commit()


@pytest.mark.asyncio
async def test_system_health_endpoint(db_session):
    # Seed user for authentication
    user = User(
        telegram_id=987654321,
        username="test_health_usr",
        full_name="Health Supervisor",
        role=UserRole.SUPERVISOR,
        hashed_password=hash_password("pass123"),
        is_active=True
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        login_res = await ac.post("/api/v1/auth/login", json={
            "username": "test_health_usr",
            "password": "pass123"
        })
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        response = await ac.get("/api/v1/system/health", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert "cpu_percent" in data
        assert "memory" in data
        assert "nas" in data
        assert "celery_online" in data


@pytest.mark.asyncio
async def test_bulk_video_actions(db_session):
    # Seed user and channel
    user = User(
        telegram_id=987654321,
        username="test_bulk_usr",
        full_name="Bulk Supervisor",
        role=UserRole.SUPERVISOR,
        hashed_password=hash_password("pass123"),
        is_active=True
    )
    channel = Channel(
        name="Test_Ch_Bulk",
        genre="ambient",
        folder_path="/mnt/nas/Test_Ch_Bulk",
        preferred_time="10:00:00",
        is_active=True
    )
    db_session.add_all([user, channel])
    await db_session.commit()
    await db_session.refresh(user)
    await db_session.refresh(channel)

    video1 = Video(
        channel_id=channel.id,
        filename="video1.mp4",
        file_path="/mnt/nas/Test_Ch_Bulk/video1.mp4",
        file_size_bytes=1000000,
        status=VideoStatus.STAGING,
        youtube_privacy=YoutubePrivacy.PRIVATE
    )
    video2 = Video(
        channel_id=channel.id,
        filename="video2.mp4",
        file_path="/mnt/nas/Test_Ch_Bulk/video2.mp4",
        file_size_bytes=2000000,
        status=VideoStatus.STAGING,
        youtube_privacy=YoutubePrivacy.PRIVATE
    )
    db_session.add_all([video1, video2])
    await db_session.commit()
    await db_session.refresh(video1)
    await db_session.refresh(video2)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        login_res = await ac.post("/api/v1/auth/login", json={
            "username": "test_bulk_usr",
            "password": "pass123"
        })
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        # Test bulk approve
        response = await ac.post("/api/v1/videos/bulk-approve", json={"video_ids": [video1.id, video2.id]}, headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert video1.id in data["success"]
        assert video2.id in data["success"]

    # Verify state in db
    async with AsyncSessionLocal() as db_check:
        v1 = await db_check.get(Video, video1.id)
        v2 = await db_check.get(Video, video2.id)
        assert v1.status == VideoStatus.APPROVED
        assert v2.status == VideoStatus.APPROVED
        
        # Clean up
        await db_check.delete(v1)
        await db_check.delete(v2)
        
        stmt_ch = select(Channel).where(Channel.id == channel.id)
        ch_res = await db_check.execute(stmt_ch)
        await db_check.delete(ch_res.scalar_one())
        
        await db_check.commit()


@pytest.mark.asyncio
async def test_channel_analytics_endpoint(db_session):
    user = User(
        telegram_id=987654321,
        username="test_analytics_usr",
        full_name="Analytics Supervisor",
        role=UserRole.SUPERVISOR,
        hashed_password=hash_password("pass123"),
        is_active=True
    )
    channel = Channel(
        name="Test_Ch_Analytics",
        genre="relax",
        folder_path="/mnt/nas/Test_Ch_Analytics",
        preferred_time="09:00:00",
        is_active=True
    )
    db_session.add_all([user, channel])
    await db_session.commit()
    await db_session.refresh(user)
    await db_session.refresh(channel)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        login_res = await ac.post("/api/v1/auth/login", json={
            "username": "test_analytics_usr",
            "password": "pass123"
        })
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        response = await ac.get(f"/api/v1/channels/{channel.id}/analytics", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert "total_views" in data
        assert "daily_stats" in data
        assert len(data["daily_stats"]) == 30
        
    async with AsyncSessionLocal() as db_check:
        stmt_ch = select(Channel).where(Channel.id == channel.id)
        ch_res = await db_check.execute(stmt_ch)
        await db_check.delete(ch_res.scalar_one())
        await db_check.commit()


@pytest.mark.asyncio
async def test_channel_oauth_status_and_disconnect(db_session):
    from app.models import GCPProject, ChannelCredentials
    from app.utils.credential_crypto import encrypt_token

    # 1. Seed user, channel, gcp project, credentials
    user = User(
        telegram_id=987654321,
        username="test_oauth_usr",
        full_name="OAuth Admin",
        role=UserRole.SUPERVISOR,
        hashed_password=hash_password("pass123"),
        is_active=True
    )
    channel = Channel(
        name="Test_Ch_OAuth",
        genre="relax",
        folder_path="/mnt/nas/Test_Ch_OAuth",
        preferred_time="09:00:00",
        is_active=True,
        gcp_project_id="test-proj-123"
    )
    db_session.add_all([user, channel])
    await db_session.commit()
    await db_session.refresh(user)
    await db_session.refresh(channel)

    gcp_proj = GCPProject(
        channel_id=channel.id,
        project_name="Test Project",
        project_id="test-proj-123",
        client_secret_json=encrypt_token(channel.id, '{"web":{"client_id":"cid","client_secret":"cs"}}'),
        client_secret_path="",
        quota_limit=10000,
        status="active"
    )
    creds = ChannelCredentials(
        channel_id=channel.id,
        gcp_project_id="test-proj-123",
        oauth_credentials_encrypted=encrypt_token(channel.id, "fake_access"),
        oauth_refresh_token_encrypted=encrypt_token(channel.id, "fake_refresh"),
        is_active=True
    )
    db_session.add_all([gcp_proj, creds])
    await db_session.commit()

    # 2. Test status endpoint when connected
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        login_res = await ac.post("/api/v1/auth/login", json={
            "username": "test_oauth_usr",
            "password": "pass123"
        })
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        status_res = await ac.get(f"/api/v1/channels/{channel.id}/oauth-status", headers=headers)
        assert status_res.status_code == 200
        status_data = status_res.json()
        assert status_data["connected"] is True
        assert status_data["gcp_project_id"] == "test-proj-123"

        # 3. Test disconnect endpoint
        disc_res = await ac.post(f"/api/v1/channels/{channel.id}/disconnect", headers=headers)
        assert disc_res.status_code == 200
        assert disc_res.json()["detail"] == "Channel disconnected successfully"

        # 4. Verify disconnected status
        status_res = await ac.get(f"/api/v1/channels/{channel.id}/oauth-status", headers=headers)
        assert status_res.status_code == 200
        status_data = status_res.json()
        assert status_data["connected"] is False

    # 5. Clean up db
    async with AsyncSessionLocal() as db_check:
        stmt_ch = select(Channel).where(Channel.id == channel.id)
        ch_res = await db_check.execute(stmt_ch)
        await db_check.delete(ch_res.scalar_one())
        
        stmt_usr = select(User).where(User.id == user.id)
        usr_res = await db_check.execute(stmt_usr)
        await db_check.delete(usr_res.scalar_one())
        
        await db_check.commit()



