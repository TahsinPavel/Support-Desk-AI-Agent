# config.py
from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str

    # OpenAI
    OPENAI_API_KEY: Optional[str] = Field(None, env="OPENAI_API_KEY")

    # Frontend url
    FRONTEND_URL: Optional[str] = Field(None, env="FRONTEND_URL")

    # Gemini
    GEMINI_API_KEY: Optional[str] = Field(None, env="GEMINI_API_KEY")

    # Twilio (for outgoing actions if needed)
    TWILIO_ACCOUNT_SID: Optional[str] = Field(None, env="TWILIO_ACCOUNT_SID")
    TWILIO_AUTH_TOKEN: Optional[str] = Field(None, env="TWILIO_AUTH_TOKEN")
    TWILIO_PHONE_NUMBER: Optional[str] = Field(None, env="TWILIO_PHONE_NUMBER")
    
    # Paddle
    PADDLE_WEBHOOK_SECRET: Optional[str] = Field(None, env="PADDLE_WEBHOOK_SECRET")
    PADDLE_API_KEY: Optional[str] = Field(None, env="PADDLE_API_KEY")
    PADDLE_ENVIRONMENT: Optional[str] = Field("sandbox", env="PADDLE_ENVIRONMENT")

    # Paddle price ids (Billing)
    PADDLE_STARTER_PRICE_ID: Optional[str] = Field(None, env="PADDLE_STARTER_PRICE_ID")
    PADDLE_GROWTH_PRICE_ID: Optional[str] = Field(None, env="PADDLE_GROWTH_PRICE_ID")
    PADDLE_ENTERPRISE_PRICE_ID: Optional[str] = Field(None, env="PADDLE_ENTERPRISE_PRICE_ID")

    # Development-only payments
    # Set `ALLOW_DEV_PAYMENT_CONFIRMATION=true` in development to allow a simulated
    # "payment confirmed" API call from the frontend when Paddle is not configured.
    ALLOW_DEV_PAYMENT_CONFIRMATION: bool = Field(False, env="ALLOW_DEV_PAYMENT_CONFIRMATION")

    # Resend (email service for outgoing emails)
    RESEND_API_KEY: Optional[str] = Field(None, env="RESEND_API_KEY")

    # Host config
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    ENVIRONMENT: str = "development"

    # AI settings
    DEFAULT_AI_PROVIDER: str = "gemini"  # fallback
    MAX_CONVERSATION_TOKENS: int = 4000

    # Security
    REQUIRE_TWILIO_VALIDATION: bool = True

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()