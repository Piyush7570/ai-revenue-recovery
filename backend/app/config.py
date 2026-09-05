import os
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "sqlite:///./revenue_recovery.db"
    
    # Razorpay Secrets
    RAZORPAY_KEY_ID: str = ""
    RAZORPAY_KEY_SECRET: str = ""
    RAZORPAY_WEBHOOK_SECRET: str = ""
    
    # LLM Settings
    LLM_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-1.5-flash"
    
    # Policy Rules
    MAX_RETRIES: int = 3
    MIN_HOURS_BETWEEN_NOTIFICATIONS: int = 12
    MAX_NOTIFICATIONS_PER_CASE: int = 3
    
    # Server configuration
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
