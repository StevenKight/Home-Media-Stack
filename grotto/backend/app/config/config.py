import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings

load_dotenv()


class Settings(BaseSettings):
    APP_VERSION: str = "1.0.0"
    APP_NAME: str = "FastAPI"
    APP_DESCRIPTION: str = "FastAPI"
    ENVIRONMENT: str = "development"
    DATABASE_URL: str = ""
    TEST_DATABASE_URL: str | None = "sqlite+aiosqlite:///./test_app.db"
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost:3000"]
    API_PREFIX: str = "/api"

    # Database settings
    DB_NAME: str | None = None
    DB_USER: str | None = None
    DB_PASSWORD: str | None = None
    DB_HOST: str | None = None
    DB_PORT: int | None = None
    DB_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_TIMEOUT: int = 30
    DB_ECHO: bool = False
    DB_SSL_MODE: str | None = None

    # JWT Settings
    SECRET_KEY: str | None = None
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # Sonarr Settings
    SONARR_HOST: str = "localhost"
    SONARR_PORT: int = 8989
    SONARR_API_KEY: str = ""

    # Radarr Settings
    RADARR_HOST: str = "localhost"
    RADARR_PORT: int = 7878
    RADARR_API_KEY: str = ""

    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache
def get_settings() -> Settings:
    return Settings()


BASE_DIR = Path(__file__).parent.parent

# Logging configuration
LOGGING_CONFIG = {
    "development": {
        "log_level": "DEBUG",
        "log_dir": BASE_DIR / "logs" / "dev",
    },
    "production": {
        "log_level": "INFO",
        "log_dir": BASE_DIR / "logs" / "prod",
    },
    "testing": {
        "log_level": "DEBUG",
        "log_dir": None,  # Console only
    },
}

ENVIRONMENT = os.getenv("ENVIRONMENT", "development").lower()
# Ensure environment is one of the defined keys, default to development if not
if ENVIRONMENT not in LOGGING_CONFIG:
    ENVIRONMENT = "development"
CURRENT_LOGGING_CONFIG = LOGGING_CONFIG[ENVIRONMENT]
