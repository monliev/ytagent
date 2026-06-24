from typing import Optional
from pydantic import BaseModel, Field

class SystemSettingsBase(BaseModel):
    telegram_bot_token: Optional[str] = Field(None, description="Telegram Bot Token")
    supervisor_telegram_id: Optional[int] = Field(None, description="Supervisor Telegram User ID")
    cf_ai_url: Optional[str] = Field(None, description="Cloudflare AI Worker URL")
    cf_ai_token: Optional[str] = Field(None, description="Cloudflare AI Token or API Key")
    cf_ai_model: Optional[str] = Field(None, description="AI Model Name (e.g. hermes)")
    recaptcha_site_key: Optional[str] = Field(None, description="Google reCAPTCHA v2 Site Key")
    recaptcha_secret_key: Optional[str] = Field(None, description="Google reCAPTCHA v2 Secret Key")
    # SFTP / NAS settings
    sftp_host: Optional[str] = Field(None, description="SFTP / NAS Host IP or Hostname")
    sftp_port: Optional[int] = Field(None, description="SFTP Port (default 22)")
    sftp_user: Optional[str] = Field(None, description="SFTP Username")
    sftp_password: Optional[str] = Field(None, description="SFTP Password")
    sftp_base_path: Optional[str] = Field(None, description="Base path on SFTP server to list watch folders")

class SystemSettingsResponse(SystemSettingsBase):
    pass

class SystemSettingsUpdate(SystemSettingsBase):
    pass

class PublicSettingsResponse(BaseModel):
    recaptcha_site_key: Optional[str] = Field(None, description="Google reCAPTCHA Site Key (empty if disabled)")
