from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="MEMBRIDGE_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    palace_path: str = "/opt/chatd/.mempalace/palace"
    mempalace_bin: str = "/opt/chatd/venv/bin/mempalace"
    tokens_file: Path = Path("/opt/chatd/etc/mempalace.tokens")
    host: str = "127.0.0.1"
    port: int = 8765


settings = Settings()
