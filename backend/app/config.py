"""Application configuration using pydantic-settings."""

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Database
    DB_HOST: str = "localhost"
    DB_PORT: int = 3306
    DB_USER: str = "root"
    DB_PASSWORD: str = ""
    DB_NAME: str = "trading_platform"

    # Redis
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: str = ""
    REDIS_SSL: bool = False

    # Binance
    BINANCE_API_KEY: str = ""
    BINANCE_API_SECRET: str = ""

    # Telegram
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_CHAT_ID: str = ""
    TELEGRAM_RELAY_URL: str = "https://frontend-trade-tan.vercel.app/api/telegram" # Default relay for HF bypass

    # Email
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""

    # App
    APP_ENV: str = "development"
    APP_SECRET_KEY: str = "change-me-to-a-random-string"
    FRONTEND_URL: str = "http://localhost:3000"

    @property
    def DATABASE_URL(self) -> str:
        import os
        # Priority 1: Full DATABASE_URL from environment
        env_url = os.environ.get("DATABASE_URL")
        if env_url:
            return env_url
            
        # Priority 2: SQLite fallback for HF Spaces if no remote DB host is provided
        if os.environ.get("SPACE_ID") and (self.DB_HOST == "localhost" or self.DB_HOST == "127.0.0.1"):
            # Ensure the data directory exists for the sqlite file
            data_dir = "app/data"
            if not os.path.exists(data_dir):
                try: os.makedirs(data_dir)
                except: pass
            return "sqlite:///./app/data/trading_platform.db"

        # Priority 3: Construct MySQL URL from components
        url = (
            f"mysql+pymysql://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )
        if "tidbcloud.com" in self.DB_HOST:
            url += "?ssl_verify_cert=true&ssl_verify_identity=true"
        return url

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
