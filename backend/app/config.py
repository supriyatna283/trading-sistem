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
    # Vercel proxy URL to bypass HuggingFace outbound block
    TELEGRAM_PROXY_URL: str = ""
    TELEGRAM_PROXY_SECRET: str = "trading-v6-secret"

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
        """Build MySQL/TiDB connection URL with automatic SSL for TiDB Cloud."""
        url = (
            f"mysql+pymysql://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )
        # TiDB Cloud requires SSL
        if "tidbcloud.com" in self.DB_HOST:
            url += "?ssl_verify_cert=true&ssl_verify_identity=true"
        return url

    @property
    def REDIS_URL(self) -> str:
        """Build Redis connection URL."""
        scheme = "rediss" if self.REDIS_SSL else "redis"
        if self.REDIS_PASSWORD:
            return f"{scheme}://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/0"
        return f"{scheme}://{self.REDIS_HOST}:{self.REDIS_PORT}/0"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
