from typing import Optional
from pydantic import BaseModel, Field

class SystemSettingsBase(BaseModel):
    telegram_bot_token: Optional[str] = Field(None, description="Telegram Bot Token")
    supervisor_telegram_id: Optional[int] = Field(None, description="Supervisor Telegram User ID")
    cf_ai_url: Optional[str] = Field(None, description="Cloudflare AI Worker URL")
    recaptcha_site_key: Optional[str] = Field(None, description="Google reCAPTCHA v2 Site Key")
    recaptcha_secret_key: Optional[str] = Field(None, description="Google reCAPTCHA v2 Secret Key")

class SystemSettingsResponse(SystemSettingsBase):
    pass

class SystemSettingsUpdate(SystemSettingsBase):
    pass

class PublicSettingsResponse(BaseModel):
    recaptcha_site_key: Optional[str] = Field(None, description="Google reCAPTCHA Site Key (empty if disabled)")
