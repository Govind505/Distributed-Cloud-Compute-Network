import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache

# Find .env in current directory or parent directory
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT_DIR = os.path.dirname(BASE_DIR)
env_files = [os.path.join(ROOT_DIR, ".env"), os.path.join(BASE_DIR, ".env"), ".env"]
env_file = next((f for f in env_files if os.path.exists(f)), ".env")


from pydantic import field_validator

DEFAULT_DB_FILE = os.path.join(BASE_DIR, "dccn.db").replace("\\", "/")


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = f"sqlite+aiosqlite:///{DEFAULT_DB_FILE}"
    DATABASE_URL_SYNC: str = f"sqlite:///{DEFAULT_DB_FILE}"

    @field_validator("DATABASE_URL", mode="after")
    @classmethod
    def resolve_db_url(cls, v: str) -> str:
        if v.startswith("sqlite+aiosqlite:///."):
            return f"sqlite+aiosqlite:///{DEFAULT_DB_FILE}"
        return v

    @field_validator("DATABASE_URL_SYNC", mode="after")
    @classmethod
    def resolve_sync_db_url(cls, v: str) -> str:
        if v.startswith("sqlite:///."):
            return f"sqlite:///{DEFAULT_DB_FILE}"
        return v

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Auth
    SECRET_KEY: str = "change-me-to-a-random-secret-key-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    ALGORITHM: str = "HS256"

    # Server
    SERVER_HOST: str = "0.0.0.0"
    SERVER_PORT: int = 8000
    DEBUG: bool = True
    
    # Project
    PROJECT_NAME: str = "Distributed Cloud Compute Network"
    API_V1_PREFIX: str = "/api/v1"

    model_config = SettingsConfigDict(env_file=env_file, extra="ignore")


@lru_cache()
def get_settings() -> Settings:
    return Settings()
