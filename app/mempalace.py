"""Thin synchronous wrapper around the mempalace CLI."""
import subprocess
from dataclasses import dataclass
from app.config import settings


@dataclass
class CmdResult:
    returncode: int
    stdout: str
    stderr: str

    def as_dict(self) -> dict:
        return {
            "returncode": self.returncode,
            "stdout": self.stdout,
            "stderr": self.stderr,
        }


def _run(*args: str, timeout: int = 120) -> CmdResult:
    cmd = [settings.mempalace_bin, *settings.palace_args(), *args]
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    return CmdResult(proc.returncode, proc.stdout, proc.stderr)


def status() -> CmdResult:
    return _run("status", timeout=30)


def search(query: str, wing: str | None = None, room: str | None = None) -> CmdResult:
    extra: list[str] = []
    if wing:
        extra += ["--wing", wing]
    if room:
        extra += ["--room", room]
    return _run("search", query, *extra)


def mine(source: str, wing: str | None = None) -> CmdResult:
    extra: list[str] = []
    if wing:
        extra += ["--wing", wing]
    return _run("mine", source, *extra)


def recall(topic: str, limit: int = 10) -> CmdResult:
    return _run("recall", topic, "--limit", str(limit))
