import os
import json
import pytest
from unittest.mock import patch, MagicMock
from sqlalchemy import select

from app.core.database import AsyncSessionLocal, SessionLocal
from app.models import (
    Channel,
    Video,
    VideoStatus,
    GCPProject,
    GCPProjectStatus,
    ChannelCredentials,
    SystemLog,
    LogLevel
)
from app.utils.credential_crypto import encrypt_token, decrypt_token
from app.services.upload_service_sync import UploadServiceSync
from app.tasks.upload import upload_video_task

from googleapiclient.errors import HttpError
from httpx import Response
import asyncio
from app.core.database import engine

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

CHANNEL_NAME = "Upload_Test_Channel"
CLIENT_SECRET_DUMMY_PATH = "secrets_dummy.json"

@pytest.fixture(scope="module", autouse=True)
def setup_dummy_secrets():
    """Create a dummy client secret JSON and video file, and clean database before running tests."""
    with SessionLocal() as db:
        db.query(Video).filter(Video.file_path.in_(["/dummy/video.mp4", "dummy_video.mp4"])).delete()
        db.query(ChannelCredentials).filter(ChannelCredentials.gcp_project_id.in_(["gcp-proj-one", "gcp-proj-two"])).delete()
        db.query(GCPProject).filter(GCPProject.project_id.in_(["gcp-proj-one", "gcp-proj-two"])).delete()
        db.query(Channel).filter(Channel.name == CHANNEL_NAME).delete()
        db.commit()

    data = {
        "installed": {
            "client_id": "dummy_client_id_123",
            "client_secret": "dummy_client_secret_abc",
            "token_uri": "https://oauth2.googleapis.com/token"
        }
    }
    with open(CLIENT_SECRET_DUMMY_PATH, "w") as f:
        json.dump(data, f)
        
    with open("dummy_video.mp4", "w") as f:
        f.write("dummy video data")
        
    yield
    
    if os.path.exists(CLIENT_SECRET_DUMMY_PATH):
        os.remove(CLIENT_SECRET_DUMMY_PATH)
    if os.path.exists("dummy_video.mp4"):
        os.remove("dummy_video.mp4")

def test_credential_encryption_decryption():
    """Test that per-channel encryption and decryption matches original strings."""
    channel_id = 999
    token = "test-oauth-refresh-token-xyz-123456"
    
    # Encrypt
    encrypted = encrypt_token(channel_id, token)
    assert encrypted != token
    assert len(encrypted) > 0
    
    # Decrypt
    decrypted = decrypt_token(channel_id, encrypted)
    assert decrypted == token

    # Decrypting with wrong channel ID should fail
    with pytest.raises(Exception):
        decrypt_token(888, encrypted)

@pytest.mark.asyncio
async def test_resumable_upload_with_quota_rotation():
    """Test that upload pipeline handles quota limits by rotating GCP projects."""
    
    # 1. Setup Channel, 2 Projects, and Channel Credentials in local DB
    async with AsyncSessionLocal() as session:
        # Cleanup
        await session.execute(
            select(Video).where(Video.file_path == "dummy_video.mp4")
        )
        
        channel = Channel(
            name=CHANNEL_NAME,
            genre="jazz",
            folder_path="/dummy/jazz",
            is_active=True,
            made_for_kids=False
        )
        session.add(channel)
        await session.commit()
        await session.refresh(channel)
        
        project1 = GCPProject(
            channel_id=channel.id,
            project_name="Project One",
            project_id="gcp-proj-one",
            client_secret_path=CLIENT_SECRET_DUMMY_PATH,
            status=GCPProjectStatus.ACTIVE
        )
        project2 = GCPProject(
            channel_id=channel.id,
            project_name="Project Two",
            project_id="gcp-proj-two",
            client_secret_path=CLIENT_SECRET_DUMMY_PATH,
            status=GCPProjectStatus.ACTIVE
        )
        session.add(project1)
        session.add(project2)
        await session.commit()
        
        channel.gcp_project_id = "gcp-proj-one"
        session.add(channel)
        
        # Add credentials entries for both projects
        creds1 = ChannelCredentials(
            channel_id=channel.id,
            gcp_project_id="gcp-proj-one",
            oauth_refresh_token_encrypted=encrypt_token(channel.id, "refresh-token-1"),
            oauth_credentials_encrypted=encrypt_token(channel.id, "access-token-1"),
            is_active=True
        )
        creds2 = ChannelCredentials(
            channel_id=channel.id,
            gcp_project_id="gcp-proj-two",
            oauth_refresh_token_encrypted=encrypt_token(channel.id, "refresh-token-2"),
            oauth_credentials_encrypted=encrypt_token(channel.id, "access-token-2"),
            is_active=True
        )
        session.add(creds1)
        session.add(creds2)
        
        video = Video(
            channel_id=channel.id,
            filename="video.mp4",
            file_path="dummy_video.mp4",
            file_size_bytes=1000,
            status=VideoStatus.APPROVED,
            current_title="Jazz Evening Mix",
            current_description="Beautiful jazz music."
        )
        session.add(video)
        await session.commit()
        
        channel_id = channel.id
        video_id = video.id

    # 2. Mock Google API calls to simulate quota exceeded on Project One
    mock_response_http = MagicMock()
    mock_response_http.status = 403
    mock_headers = {"content-type": "application/json"}
    
    # Construct an HttpError payload representing quota exceeded
    error_content = json.dumps({
        "error": {
            "errors": [
                {
                    "domain": "usageLimits",
                    "reason": "quotaExceeded",
                    "message": "The request cannot be completed because you have exceeded your quota."
                }
            ],
            "code": 403,
            "message": "The request cannot be completed because you have exceeded your quota."
        }
    }).encode("utf-8")
    
    quota_error = HttpError(resp=mock_response_http, content=error_content)

    mock_youtube = MagicMock()
    # Mock insert request next_chunk to raise HttpError for project 1, and succeed for project 2
    mock_insert_request = MagicMock()
    
    call_count = 0
    def side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            # First project throws quota limit
            raise quota_error
        else:
            # Second project succeeds
            return None, {"id": "youtube-test-id-999"}

    mock_insert_request.next_chunk.side_effect = side_effect
    mock_youtube.videos().insert.return_value = mock_insert_request

    # Patch build client function and refresh credentials call
    with patch("app.services.upload_service_sync.build", return_value=mock_youtube), \
         patch("google.oauth2.credentials.Credentials.refresh", return_value=None):
         
         # Execute task synchronously
         task_result = upload_video_task(video_id)
         
    # 3. Assert results
    assert task_result == "youtube-test-id-999"

    # Check DB changes
    with SessionLocal() as db:
        # Video is marked as UPLOADED and stores the video ID
        vid_rec = db.query(Video).filter(Video.id == video_id).first()
        assert vid_rec.status == VideoStatus.UPLOADED
        assert vid_rec.youtube_video_id == "youtube-test-id-999"
        
        # Project 1 is marked as quota exceeded
        proj1 = db.query(GCPProject).filter(GCPProject.project_id == "gcp-proj-one").first()
        assert proj1.status == GCPProjectStatus.QUOTA_EXCEEDED
        
        # Active GCP Project on Channel is rotated to Project Two
        chan = db.query(Channel).filter(Channel.id == channel_id).first()
        assert chan.gcp_project_id == "gcp-proj-two"
        
        # Cleanup
        db.delete(vid_rec)
        db.delete(creds1)
        db.delete(creds2)
        db.delete(proj1)
        db.delete(db.query(GCPProject).filter(GCPProject.project_id == "gcp-proj-two").first())
        db.delete(chan)
        db.commit()
