import pytest
import asyncio
from unittest.mock import patch, MagicMock
from sqlalchemy import select, delete
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.core.database import AsyncSessionLocal, engine
from app.core.security import hash_password
from app.models.user import User, UserRole
from app.models.system_setting import SystemSetting
from app.core.redis_client import redis_client

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

@pytest.fixture(scope="module", autouse=True)
async def cleanup_redis():
    yield
    try:
        await redis_client.connection_pool.disconnect()
    except Exception:
        pass

@pytest.fixture(scope="function")
async def db_session():
    async with AsyncSessionLocal() as session:
        yield session

@pytest.fixture(scope="function", autouse=True)
async def cleanup_db():
    yield
    async with AsyncSessionLocal() as db:
        # Delete test users
        stmt_usr = select(User).where(User.username.like("test_%"))
        usr_res = await db.execute(stmt_usr)
        for usr in usr_res.scalars().all():
            await db.delete(usr)
            
        # Delete settings
        await db.execute(delete(SystemSetting))
        await db.commit()

@pytest.mark.asyncio
async def test_settings_workflow(db_session):
    # 1. Create a test user
    password = "super_secret_password"
    user = User(
        telegram_id=987654321,
        username="test_user_settings",
        full_name="Test User Settings",
        role=UserRole.SUPERVISOR,
        hashed_password=hash_password(password),
        is_active=True
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Get public settings (should be empty initially)
        res_pub = await ac.get("/api/v1/settings/public")
        assert res_pub.status_code == 200
        assert res_pub.json() == {"recaptcha_site_key": None}

        # Try setting retrieval unauthorized
        res_unauth = await ac.get("/api/v1/settings/")
        assert res_unauth.status_code == 401

        # Login
        login_res = await ac.post("/api/v1/auth/login", json={
            "username": "test_user_settings",
            "password": password
        })
        assert login_res.status_code == 200
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Update settings
        update_payload = {
            "telegram_bot_token": "my_new_telegram_token_12345",
            "supervisor_telegram_id": 12345678,
            "cf_ai_url": "https://cloudflare.ai/v1",
            "recaptcha_site_key": "my_site_key",
            "recaptcha_secret_key": "my_secret_key"
        }
        res_update = await ac.post("/api/v1/settings/", json=update_payload, headers=headers)
        assert res_update.status_code == 200
        settings_data = res_update.json()
        assert settings_data["telegram_bot_token"] == "*********************12345"
        assert settings_data["supervisor_telegram_id"] == 12345678
        assert settings_data["cf_ai_url"] == "https://cloudflare.ai/v1"
        assert settings_data["recaptcha_site_key"] == "my_site_key"
        assert settings_data["recaptcha_secret_key"] == "********"

        # Check public settings now returns site key
        res_pub_updated = await ac.get("/api/v1/settings/public")
        assert res_pub_updated.status_code == 200
        assert res_pub_updated.json() == {"recaptcha_site_key": "my_site_key"}

@pytest.mark.asyncio
async def test_recaptcha_login_validation(db_session):
    # 1. Create a test user
    password = "super_secret_password"
    user = User(
        telegram_id=987654321,
        username="test_user_recaptcha",
        full_name="Test User reCAPTCHA",
        role=UserRole.SUPERVISOR,
        hashed_password=hash_password(password),
        is_active=True
    )
    db_session.add(user)
    
    # 2. Configure reCAPTCHA secrets in the DB
    db_session.add(SystemSetting(key="recaptcha_site_key", value="my_site_key"))
    db_session.add(SystemSetting(key="recaptcha_secret_key", value="my_secret_key"))
    await db_session.commit()
    await db_session.refresh(user)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # A. Login should fail with 400 since reCAPTCHA token is missing
        res_no_token = await ac.post("/api/v1/auth/login", json={
            "username": "test_user_recaptcha",
            "password": password
        })
        assert res_no_token.status_code == 400
        assert "reCAPTCHA verification required" in res_no_token.text

        # B. Mock reCAPTCHA validation failing (success=False)
        mock_response_fail = MagicMock()
        mock_response_fail.status_code = 200
        mock_response_fail.json.return_value = {"success": False, "error-codes": ["invalid-input-response"]}

        with patch("httpx.AsyncClient.post", return_value=mock_response_fail):
            res_fail = await ac.post("/api/v1/auth/login", json={
                "username": "test_user_recaptcha",
                "password": password,
                "recaptcha_token": "some_invalid_token"
            })
            assert res_fail.status_code == 400
            assert "reCAPTCHA verification failed" in res_fail.text

        # C. Mock reCAPTCHA validation succeeding (success=True)
        mock_response_success = MagicMock()
        mock_response_success.status_code = 200
        mock_response_success.json.return_value = {"success": True}

        with patch("httpx.AsyncClient.post", return_value=mock_response_success):
            res_success = await ac.post("/api/v1/auth/login", json={
                "username": "test_user_recaptcha",
                "password": password,
                "recaptcha_token": "some_valid_token"
            })
            assert res_success.status_code == 200
            assert "access_token" in res_success.json()
