import os
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # MySQL Configuration
    MYSQL_USER: str = "ytagent"
    MYSQL_PASSWORD: str = "ytagent_db_pass_2026"
    MYSQL_HOST: str = "127.0.0.1"
    MYSQL_PORT: int = 3306
    MYSQL_DATABASE: str = "ytagent"

    DATABASE_URL: str | None = None
    SYNC_DATABASE_URL: str | None = None

    @property
    def database_url(self) -> str:
        """Async database connection URL for SQLAlchemy asyncmy driver."""
        if self.DATABASE_URL:
            return self.DATABASE_URL
        return f"mysql+asyncmy://{self.MYSQL_USER}:{self.MYSQL_PASSWORD}@{self.MYSQL_HOST}:{self.MYSQL_PORT}/{self.MYSQL_DATABASE}"

    @property
    def sync_database_url(self) -> str:
        """Sync database connection URL for SQLAlchemy pymysql driver (Celery workers)."""
        if self.SYNC_DATABASE_URL:
            return self.SYNC_DATABASE_URL
        return f"mysql+pymysql://{self.MYSQL_USER}:{self.MYSQL_PASSWORD}@{self.MYSQL_HOST}:{self.MYSQL_PORT}/{self.MYSQL_DATABASE}"

    # Redis URL
    REDIS_URL: str = "redis://localhost:6379/0"

    # FastAPI settings
    SECRET_KEY: str = "9eed56a039c4bd37eed1c5f5bff5ff502b6bad0ea77315846359c4a7fe7569f1"
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    DEBUG: bool = True

    # Telegram (with placeholder defaults)
    TELEGRAM_BOT_TOKEN: str = "123456789:PlaceholderTelegramToken"
    SUPERVISOR_TELEGRAM_ID: int = 123456789

    # Cloudflare AI
    CF_AI_URL: str = "https://dummy-ai-worker.workers.dev/"
    CF_AI_TOKEN: str = ""
    CF_AI_MODEL: str = "hermes"

    # Encryption (Base64 Fernet Key)
    TOKEN_ENCRYPTION_KEY: str = "mDp_K2tZh0qB3DFvdzhZvJgHJB5_KZAmlt4bIBRIScc="

    # OMV NAS mount path
    OMV_MOUNT_PATH: str = "/mnt/omv"

    # Timezone
    TZ: str = "Asia/Jakarta"

settings = Settings()
