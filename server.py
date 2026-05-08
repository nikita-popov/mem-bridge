"""Minimal MCP Streamable HTTP bridge for a local MemPalace (or any MCP stdio server).

Startup:
    uvicorn server:app

All settings via env vars (or .env file), prefix MEMBRIDGE_:

    MEMBRIDGE_MEMPALACE_CMD  shell command to run MemPalace MCP stdio server
                             default: python -m mempalace.mcp_server
    MEMBRIDGE_TOKENS_FILE    path to bearer tokens file (one per line, # = comment)
                             default: /etc/mem-bridge/tokens
                             if file is missing: auth disabled (dev mode)
    MEMBRIDGE_ALLOWED_HOSTS  comma-separated external hostnames for DNS-rebinding guard
                             default: localhost only
                             use "*" to disable check entirely

All tools exposed by the upstream MCP server are forwarded automatically—
no hardcoded tool list.
"""
import asyncio
import contextlib
import inspect
import json
import logging
import os
import shlex
import signal
import subprocess
import threading
from contextlib import AsyncExitStack
from pathlib import Path
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.server.fastmcp import FastMCP
from mcp.server.streamable_http import TransportSecuritySettings
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from mcp.types import Tool as MCPTool
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route
from starlette.types import Receive, Scope, Send

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("mem-bridge")


# ── dotenv (no external deps) ─────────────────────────────────────────────────

_env_file = Path(".env")
if _env_file.exists():
    for _line in _env_file.read_text().splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _, _v = _line.partition("=")
            os.environ.setdefault(_k.strip(), _v.strip())


# ── config ────────────────────────────────────────────────────────────────────

MEMPALACE_CMD: list[str] = shlex.split(
    os.environ.get("MEMBRIDGE_MEMPALACE_CMD", "python -m mempalace.mcp_server")
)


def _load_tokens() -> frozenset[str]:
    path = os.environ.get("MEMBRIDGE_TOKENS_FILE", "/etc/mem-bridge/tokens")
    try:
        with open(path) as f:
            tokens = frozenset(
                line.strip() for line in f
                if line.strip() and not line.startswith("#")
            )
        log.info("[auth] loaded %d token(s) from %s", len(tokens), path)
        return tokens
    except FileNotFoundError:
        log.warning("[auth] tokens file %s not found — auth DISABLED (dev mode)", path)
        return frozenset()


TOKENS: frozenset[str] = _load_tokens()

_extra_hosts = [
    h.strip()
    for h in os.environ.get("MEMBRIDGE_ALLOWED_HOSTS", "").split(",")
    if h.strip()
]

if "*" in _extra_hosts:
    _security = TransportSecuritySettings(enable_dns_rebinding_protection=False)
else:
    _security = TransportSecuritySettings(
        enable_dns_rebinding_protection=bool(_extra_hosts),
        allowed_hosts=["127.0.0.1:*", "localhost:*", "[::1]:*"] + _extra_hosts,
        allowed_origins=(
            ["http://127.0.0.1:*", "http://localhost:*", "http://[::1]:*"]
            + [f"https://{h}" for h in _extra_hosts]
            + [f"http://{h}" for h in _extra_hosts]
        ),
    )


# ── MCPClient (from chatd/mcp_client.py, adapted) ─────────────────────────────
#
# Runs its own asyncio event loop in a dedicated daemon thread so it never
# conflicts with the uvicorn event loop.

MCP_LIST_TOOLS_TIMEOUT: float = float(os.environ.get("MEMBRIDGE_LIST_TOOLS_TIMEOUT", "30"))
MCP_CALL_TOOL_TIMEOUT: float = float(os.environ.get("MEMBRIDGE_CALL_TOOL_TIMEOUT", "60"))


def _kill_process(cmd: list[str]) -> None:
    try:
        result = subprocess.run(["pgrep", "-f", " ".join(cmd)], capture_output=True, text=True)
        for pid_str in result.stdout.splitlines():
            try:
                pid = int(pid_str.strip())
                os.kill(pid, signal.SIGKILL)
                log.warning("[mcp] killed hung process pid=%d cmd=%s", pid, cmd[0])
            except (ValueError, ProcessLookupError, PermissionError) as e:
                log.debug("[mcp] kill pid=%s failed: %s", pid_str.strip(), e)
    except FileNotFoundError:
        log.debug("[mcp] pgrep not available")


class MCPClient:
    """Long-lived stdio MCP client with its own event loop in a daemon thread."""

    def __init__(self, cmd: list[str]):
        self.cmd = cmd
        self._session: ClientSession | None = None
        self._stack: AsyncExitStack | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._ready = threading.Event()
        self._start_exc: BaseException | None = None
        self._lock = threading.Lock()

    async def _run_loop(self) -> None:
        try:
            self._stack = AsyncExitStack()
            read, write = await self._stack.enter_async_context(
                stdio_client(StdioServerParameters(
                    command=self.cmd[0], args=self.cmd[1:], env=os.environ.copy(),
                ))
            )
            self._session = await self._stack.enter_async_context(
                ClientSession(read, write)
            )
            await self._session.initialize()
            log.info("[mcp] started: %s", self.cmd)
            self._ready.set()
            await asyncio.get_running_loop().create_future()  # park until cancelled
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            self._start_exc = exc
            self._ready.set()
        finally:
            if self._stack:
                try:
                    await self._stack.aclose()
                except Exception as e:
                    log.debug("[mcp] aclose error: %s", e)
            self._session = None
            self._stack = None

    def _thread_main(self) -> None:
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._main_task = self._loop.create_task(self._run_loop())
        try:
            self._loop.run_forever()
        finally:
            self._loop.close()
            self._loop = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self._thread_main, daemon=True, name="mcp-client")
        self._thread.start()
        self._ready.wait(timeout=MCP_LIST_TOOLS_TIMEOUT)
        if self._start_exc:
            raise self._start_exc
        if not self._session:
            raise RuntimeError(f"MCPClient failed to start: {self.cmd}")

    def stop(self) -> None:
        if self._loop and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._main_task.cancel)
            self._loop.call_soon_threadsafe(self._loop.stop)
        if self._thread:
            self._thread.join(timeout=5)
        self._thread = None
        log.info("[mcp] stopped: %s", self.cmd)

    def _run(self, coro, timeout: float) -> Any:
        if self._loop is None or self._session is None:
            raise RuntimeError(f"MCPClient not started: {self.cmd}")
        with self._lock:
            future = asyncio.run_coroutine_threadsafe(
                asyncio.wait_for(coro, timeout=timeout),
                self._loop,
            )
            return future.result(timeout=timeout + 2)

    def list_tools(self) -> list[MCPTool]:
        try:
            return self._run(self._session.list_tools(), MCP_LIST_TOOLS_TIMEOUT).tools
        except (asyncio.TimeoutError, TimeoutError):
            _kill_process(self.cmd)
            raise RuntimeError(f"list_tools timeout ({MCP_LIST_TOOLS_TIMEOUT:.0f}s)")

    def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        try:
            result = self._run(
                self._session.call_tool(name, arguments=arguments),
                MCP_CALL_TOOL_TIMEOUT,
            )
        except (asyncio.TimeoutError, TimeoutError):
            _kill_process(self.cmd)
            raise RuntimeError(f"call_tool timeout ({MCP_CALL_TOOL_TIMEOUT:.0f}s): {name}")

        contents = getattr(result, "content", None) or []
        if not contents:
            return None
        first = contents[0]
        text = getattr(first, "text", None)
        if text is None and isinstance(first, dict):
            text = first.get("text")
        if text is None:
            return str(first)
        try:
            return json.loads(text)
        except Exception:
            return text


# ── upstream client (singleton) ───────────────────────────────────────────────

_upstream = MCPClient(MEMPALACE_CMD)


# ── dynamic tool registration ─────────────────────────────────────────────────
#
# FastMCP derives the JSON schema from the Python function signature.
# We rebuild the signature from the upstream tool's inputSchema so that
# the correct schema is advertised to clients (Perplexity, Claude, etc.).
#
# JSON-schema type  →  Python annotation
#   string          →  str
#   integer         →  int
#   number          →  float
#   boolean         →  bool
#   array           →  list
#   object          →  dict
#   (anything else) →  Any

_JSON_TYPE_MAP: dict[str, Any] = {
    "string": str,
    "integer": int,
    "number": float,
    "boolean": bool,
    "array": list,
    "object": dict,
}


def _build_signature(tool: MCPTool) -> inspect.Signature:
    """Return an inspect.Signature matching the tool's inputSchema."""
    schema: dict = tool.inputSchema if isinstance(tool.inputSchema, dict) else {}
    properties: dict = schema.get("properties") or {}
    required: set[str] = set(schema.get("required") or [])

    params: list[inspect.Parameter] = []
    for param_name, param_schema in properties.items():
        annotation = _JSON_TYPE_MAP.get(
            param_schema.get("type", "") if isinstance(param_schema, dict) else "",
            Any,
        )
        if param_name in required:
            default = inspect.Parameter.empty
        else:
            default = param_schema.get("default", None) if isinstance(param_schema, dict) else None
        params.append(
            inspect.Parameter(
                name=param_name,
                kind=inspect.Parameter.KEYWORD_ONLY,
                default=default,
                annotation=annotation,
            )
        )
    return inspect.Signature(params)


mcp = FastMCP("mem-bridge", transport_security=_security)


def _register_tools() -> None:
    tools = _upstream.list_tools()
    log.info("[mcp] registering %d tool(s): %s", len(tools), [t.name for t in tools])
    for tool in tools:
        _make_tool(tool)


def _make_tool(tool: MCPTool) -> None:
    """Build a passthrough handler with a proper signature and register it."""
    name = tool.name
    sig = _build_signature(tool)

    def _handler(**kwargs: Any) -> Any:
        return _upstream.call_tool(name, kwargs)

    _handler.__name__ = name
    _handler.__doc__ = tool.description or ""
    _handler.__signature__ = sig  # FastMCP reads this to build the JSON schema
    mcp.tool()(_handler)


# ── session manager ───────────────────────────────────────────────────────────

session_manager = StreamableHTTPSessionManager(
    app=mcp._mcp_server,
    event_store=None,
    json_response=False,
    stateless=True,
)


# ── auth middleware + MCP handler ─────────────────────────────────────────────

async def _deny(send: Send, code: int, msg: bytes) -> None:
    await send({"type": "http.response.start", "status": code,
                "headers": [[b"content-type", b"text/plain"],
                             [b"content-length", str(len(msg)).encode()]]})
    await send({"type": "http.response.body", "body": msg, "more_body": False})


async def mcp_handler(scope: Scope, receive: Receive, send: Send) -> None:
    if scope["type"] == "http" and TOKENS:
        headers = dict(scope.get("headers", []))
        auth = headers.get(b"authorization", b"").decode()
        if not auth.startswith("Bearer "):
            await _deny(send, 401, b"missing bearer token")
            return
        if auth[7:].strip() not in TOKENS:
            await _deny(send, 403, b"invalid token")
            return
    await session_manager.handle_request(scope, receive, send)


# ── Starlette app + lifespan ──────────────────────────────────────────────────

@contextlib.asynccontextmanager
async def lifespan(_app: Starlette):
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, _upstream.start)
    _register_tools()
    async with session_manager.run():
        log.info("[mem-bridge] ready")
        yield
    await loop.run_in_executor(None, _upstream.stop)


app = Starlette(
    lifespan=lifespan,
    routes=[
        Route("/healthz", lambda r: JSONResponse({"ok": True}), methods=["GET"]),
        Mount("/", app=mcp_handler),
    ],
)
