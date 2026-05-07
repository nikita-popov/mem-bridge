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
        MEMBRIDGE_ALLOWED_HOSTS=chat.example.com,example.com
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

    # Gunicorn bind address
    bind: str = "127.0.0.1:8765"

    # Number of gunicorn workers (1 recommended for SQLite-backed MemPalace)
    workers: int = 1

    # Comma-separated list of external hostnames that are allowed to connect.
    # FastMCP blocks non-localhost hosts by default (DNS rebinding protection).
    # Set to the public hostname of your reverse proxy, e.g. "chat.example.com".
    # Set to "*" to disable the check entirely (not recommended on public servers).
    allowed_hosts: str = ""

    def palace_args(self) -> list[str]:
        """Return --palace <path> args if palace_path is set."""
        if self.palace_path:
            return ["--palace", self.palace_path]
        return []

    def extra_allowed_hosts(self) -> list[str]:
        if not self.allowed_hosts:
            return []
        return [h.strip() for h in self.allowed_hosts.split(",") if h.strip()]


settings = Settings()
