from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    google_api_key: str
    whatsapp_token: str
    phone_number_id: str
    verify_token: str

    data_dir: Path = Path("./data")
    graph_version: str = "v18.0"
    gemini_model: str = "models/gemini-1.5-flash"
    gemini_embedding_model: str = "models/text-embedding-004"
    edge_tts_voice: str = "es-ES-AlvaroNeural"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="allow")


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings."""

    return Settings()
