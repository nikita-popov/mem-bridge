"""Persistent stdio MCP subprocess backend.

Spawns `python -m mempalace.mcp_server` once and keeps it alive.
Each public function sends one MCP JSON-RPC `tools/call` request over
stdin and reads the response from stdout — no process spawn per call.

Thread-safety: a threading.Lock serialises all stdin/stdout I/O so the
module is safe to use from multiple asyncio threads (gunicorn sync workers
or anyio thread-pool tasks).
"""
from __future__ import annotations

import json
import subprocess
import threading
import sys
from typing import Any

from app.config import settings


# ── subprocess lifecycle ──────────────────────────────────────────────────────

_lock = threading.Lock()
_proc: subprocess.Popen | None = None
_req_id = 0


def _start_proc() -> subprocess.Popen:
    cmd = [
        settings.mempalace_python,
        "-m", settings.mempalace_module,
    ]
    if settings.palace_path:
        cmd += ["--palace", settings.palace_path]
    return subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=sys.stderr,   # forward mempalace logs to our stderr
        text=True,
        bufsize=1,           # line-buffered
    )


def _get_proc() -> subprocess.Popen:
    global _proc
    if _proc is None or _proc.poll() is not None:
        _proc = _start_proc()
    return _proc


# ── JSON-RPC helpers ──────────────────────────────────────────────────────────

def _rpc(method: str, params: dict) -> dict[str, Any]:
    """Send one JSON-RPC request, return the result dict.

    Raises RuntimeError on protocol errors or non-zero exit.
    """
    global _req_id
    with _lock:
        proc = _get_proc()
        _req_id += 1
        req = json.dumps({
            "jsonrpc": "2.0",
            "id": _req_id,
            "method": method,
            "params": params,
        })
        try:
            proc.stdin.write(req + "\n")
            proc.stdin.flush()
            raw = proc.stdout.readline()
        except (BrokenPipeError, OSError):
            # Backend crashed; restart on next call
            _proc = None
            raise RuntimeError("mempalace subprocess died; restarting on next call")

    if not raw:
        raise RuntimeError("mempalace subprocess closed stdout")

    resp = json.loads(raw)
    if "error" in resp:
        raise RuntimeError(f"mempalace error: {resp['error']}")
    return resp.get("result", {})


def _call(tool: str, arguments: dict) -> dict[str, Any]:
    return _rpc("tools/call", {"name": tool, "arguments": arguments})


# ── public API (mirrors old CmdResult interface) ──────────────────────────────

class MCPResult:
    """Thin wrapper so callers can do .as_dict() like before."""
    def __init__(self, data: dict):
        self._data = data

    def as_dict(self) -> dict:
        return self._data


def status() -> MCPResult:
    return MCPResult(_call("status", {}))


def search(query: str, wing: str | None = None, room: str | None = None) -> MCPResult:
    args: dict = {"query": query}
    if wing:
        args["wing"] = wing
    if room:
        args["room"] = room
    return MCPResult(_call("search", args))


def mine(source: str, wing: str | None = None) -> MCPResult:
    args: dict = {"source": source}
    if wing:
        args["wing"] = wing
    return MCPResult(_call("mine", args))


def recall(topic: str, limit: int = 10) -> MCPResult:
    return MCPResult(_call("recall", {"topic": topic, "limit": limit}))
