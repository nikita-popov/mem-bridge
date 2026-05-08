from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All settings can be set via environment variables prefixed MEMBRIDGE_.

    Example .env file or EnvironmentFile in systemd unit:

        MEMBRIDGE_PALACE_PATH=/home/alice/.mempalace/palace
        MEMBRIDGE_MEMPALACE_PYTHON=/home/alice/.venv/bin/python
        MEMBRIDGE_MEMPALACE_MODULE=mempalace.mcp_server
        MEMBRIDGE_TOKENS_FILE=/etc/mem-bridge/tokens
        MEMBRIDGE_BIND=127.0.0.1:8765
        MEMBRIDGE_WORKERS=1
        MEMBRIDGE_ALLOWED_HOSTS=chat.example.com
    """

    model_config = SettingsConfigDict(
        env_prefix="MEMBRIDGE_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Path to the MemPalace palace directory
    palace_path: str = ""

    # Python interpreter that has mempalace installed
    mempalace_python: str = "python"

    # Module to run as the stdio MCP backend
    mempalace_module: str = "mempalace.mcp_server"

    # File containing bearer tokens, one per line; lines starting with # are ignored
    tokens_file: Path = Path("/etc/mem-bridge/tokens")

    # Uvicorn / gunicorn bind address
    bind: str = "127.0.0.1:8765"

    # Number of workers (keep 1: the stdio subprocess is per-process)
    workers: int = 1

    # Comma-separated external hostnames allowed to connect.
    # FastMCP blocks non-localhost hosts by default (DNS rebinding protection).
    # Set to the public hostname of your reverse proxy, e.g. "chat.example.com".
    # Set to "*" to disable the check entirely (not recommended).
    allowed_hosts: str = ""

    def extra_allowed_hosts(self) -> list[str]:
        if not self.allowed_hosts:
            return []
        return [h.strip() for h in self.allowed_hosts.split(",") if h.strip()]


settings = Settings()
