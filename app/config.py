from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All settings can be set via environment variables prefixed MEMBRIDGE_.

    Example .env file or EnvironmentFile in systemd unit:

        MEMBRIDGE_PALACE_PATH=/home/alice/.mempalace/palace
        MEMBRIDGE_MEMPALACE_BIN=/home/alice/.local/bin/mempalace
        MEMBRIDGE_TOKENS_FILE=/etc/mem-bridge/tokens
        MEMBRIDGE_BIND=127.0.0.1:8765
        MEMBRIDGE_WORKERS=1
    """

    model_config = SettingsConfigDict(
        env_prefix="MEMBRIDGE_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Path to the MemPalace palace directory
    palace_path: str = ""

    # Path to the mempalace binary
    mempalace_bin: str = "mempalace"

    # File containing bearer tokens, one per line; lines starting with # are ignored
    tokens_file: Path = Path("/etc/mem-bridge/tokens")

    # Gunicorn bind address (used in deploy docs; actual binding is gunicorn's job)
    bind: str = "127.0.0.1:8765"

    # Number of gunicorn workers (1 recommended for SQLite-backed MemPalace)
    workers: int = 1

    def palace_args(self) -> list[str]:
        """Return --palace <path> args if palace_path is set."""
        if self.palace_path:
            return ["--palace", self.palace_path]
        return []


settings = Settings()
