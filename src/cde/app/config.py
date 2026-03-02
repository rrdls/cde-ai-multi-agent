"""Application settings."""

from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """CDE PoC configuration."""

    APP_NAME: str = "CDE PoC API"
    DATABASE_URL: str = "postgresql+asyncpg://cde:cde@localhost:5432/cde"
    UPLOAD_DIR: Path = Path("uploads")

    class Config:
        env_file = ".env"


settings = Settings()
