"""Validated local profiles, serialized calls, and the official MCP transport."""
from __future__ import annotations

import asyncio
import base64
from contextlib import asynccontextmanager, contextmanager
import json
import math
import os
from pathlib import Path
import re
import shutil
import uuid

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

SECRET_KEY = re.compile(r"secret|token|password|credential|api_?key", re.I)


class BridgeError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def load_profiles(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        raise BridgeError("config_invalid", "Cannot read valid profile configuration.") from None
    if not isinstance(data, dict) or set(data) != {"profiles"} or not isinstance(data["profiles"], dict):
        raise BridgeError("config_invalid", "Expected a profiles object only.")
    for name, profile in data["profiles"].items():
        if not re.fullmatch(r"[a-zA-Z0-9_-]{1,64}", name) or not isinstance(profile, dict):
            raise BridgeError("config_invalid", "Invalid profile name or definition.")
        if set(profile) - {"command", "args", "env"} or not isinstance(profile.get("command"), str) or not profile["command"].strip():
            raise BridgeError("config_invalid", "Profile requires a command and only command, args, env fields.")
        args, env = profile.get("args", []), profile.get("env", {})
        if not isinstance(args, list) or any(not isinstance(x, str) or "\0" in x for x in args):
            raise BridgeError("config_invalid", "Profile args must be strings without NUL characters.")
        if "\0" in profile["command"] or not isinstance(env, dict):
            raise BridgeError("config_invalid", "Invalid command or environment.")
        for key, value in env.items():
            if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key) or not isinstance(value, str) or "\0" in value or SECRET_KEY.search(key):
                raise BridgeError("config_invalid", "Environment overrides must be non-secret strings; inherit credentials from the process environment.")
    return data["profiles"]


def default_lock_path() -> Path:
    return Path(os.environ.get("LOCALAPPDATA", str(Path.home() / ".local" / "state"))) / "sissad-blender-bridge" / "writer.lock"


@contextmanager
def writer_lock(path: Path):
    """OS lock survives stale lock files and is released after a process crash."""
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = path.open("a+b")
    try:
        if handle.seek(0, 2) == 0:
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            raise BridgeError("busy", "Another bridge call is in progress. No call was sent.") from None
        try:
            yield
        finally:
            handle.seek(0)
            if os.name == "nt":
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    finally:
        handle.close()


def redact(value):
    """Remove secret fields and exact known credential values from server output."""
    if isinstance(value, dict):
        return {k: "[REDACTED]" if SECRET_KEY.search(k) else redact(v) for k, v in value.items()}
    if isinstance(value, list):
        return [redact(v) for v in value]
    if isinstance(value, str):
        for key, secret in os.environ.items():
            if SECRET_KEY.search(key) and len(secret) >= 4:
                value = value.replace(secret, "[REDACTED]")
    return value


def serialize_result(result, output_dir: Path | None = None) -> dict:
    data = result.model_dump(mode="json", by_alias=True, exclude_none=True)
    for block in data.get("content", []):
        if block.get("type") == "image":
            raw = block.pop("data", "")
            block["saved"] = False
            if output_dir is not None:
                ext = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp"}.get(block.get("mimeType"))
                if ext is None:
                    raise BridgeError("image_invalid", "Unsupported image type; no image saved.")
                try:
                    payload = base64.b64decode(raw, validate=True)
                except ValueError:
                    raise BridgeError("image_invalid", "Invalid image content; no image saved.") from None
                destination = output_dir / ("blender-" + uuid.uuid4().hex + ext)
                with destination.open("xb") as stream:
                    stream.write(payload)
                block.update(saved=True, path=str(destination))
    return redact(data)


class BridgeClient:
    def __init__(self, config_path: str | Path = "config.local.json", *, lock_path: Path | None = None):
        self.config_path = Path(config_path).expanduser().resolve()
        self.profiles = load_profiles(self.config_path)
        self.lock_path = lock_path or default_lock_path()

    def profile(self, name: str) -> dict:
        if name not in self.profiles:
            raise BridgeError("profile_missing", "Unknown profile.")
        return self.profiles[name]

    def _stdio_parameters(self, item: dict) -> StdioServerParameters:
        command, args = item["command"], item.get("args", [])
        environment = {**os.environ, **item.get("env", {})}
        # Own launch adapter; preserve the pinned upstream and all privacy/safe-mode flags.
        executable = Path(command)
        if executable.name.casefold() in {"mcp-for-blender.exe", "mcp-for-blender"}:
            interpreter = executable.with_name("python.exe" if executable.suffix.casefold() == ".exe" else "python")
            if not interpreter.is_file():
                raise BridgeError("config_invalid", "Community profile requires its sibling Python interpreter.")
            command = str(interpreter)
            args = [str(Path(__file__).with_name("community_bootstrap.py")), *args]
        return StdioServerParameters(command=command, args=args, env=environment, cwd=str(self.config_path.parent))

    @asynccontextmanager
    async def persistent(self, profile: str, *, timeout: float = 300):
        """Keep one upstream process/session alive for a downstream connection.

        State such as viewport snapshots and picking caches belongs to that
        process. A reconnect is explicit; calls are never retried.
        """
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or timeout <= 0:
            raise BridgeError("timeout_invalid", "Timeout must be a finite positive number.")
        item = self.profile(profile)
        parameters = self._stdio_parameters(item)
        try:
            with open(os.devnull, "w") as error_stream:
                async with stdio_client(parameters, errlog=error_stream) as (read, write):
                    async with ClientSession(read, write) as session:
                        async with asyncio.timeout(timeout):
                            await session.initialize()
                        yield PersistentBridgeClient(self, profile, session)
        except BridgeError:
            raise
        except Exception:
            raise BridgeError("transport_error", "Persistent MCP connection ended or failed; no automatic reconnect was attempted.") from None

    async def _request(self, profile: str, method: str, *, tool=None, arguments=None, timeout=300):
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or timeout <= 0:
            raise BridgeError("timeout_invalid", "Timeout must be a finite positive number.")
        item = self.profile(profile)
        parameters = self._stdio_parameters(item)
        try:
            async with asyncio.timeout(timeout):
                with open(os.devnull, "w") as error_stream:
                    async with stdio_client(parameters, errlog=error_stream) as (read, write):
                        async with ClientSession(read, write) as session:
                            await session.initialize()
                            if method == "resources":
                                return await session.list_resources(cursor=arguments)
                            if method == "read_resource":
                                return await session.read_resource(tool)
                            if method == "tools":
                                items, cursor = [], None
                                while True:
                                    page = await session.list_tools(cursor=cursor)
                                    items.extend(t.model_dump(mode="json", by_alias=True, exclude_none=True) for t in page.tools)
                                    cursor = page.nextCursor
                                    if not cursor:
                                        return redact({"tools": items})
                            return await session.call_tool(tool, arguments=arguments)
        except TimeoutError:
            raise BridgeError("timeout", "Operation timed out. A dispatched Blender call may still be running; inspect Blender before retrying.") from None
        except BridgeError:
            raise
        except Exception:
            raise BridgeError("transport_error", "MCP transport failed. Check the profile command and local Blender service; no automatic retry was attempted.") from None

    async def list_tools(self, profile: str, *, timeout: float = 300) -> dict:
        return await self._request(profile, "tools", timeout=timeout)

    async def call_tool(self, profile: str, name: str, arguments: dict, *, output_dir: str | Path | None = None, timeout: float = 300) -> dict:
        if not isinstance(name, str) or not name.strip() or not isinstance(arguments, dict):
            raise BridgeError("arguments_invalid", "Tool name must be nonempty and arguments must be a JSON object.")
        destination = None
        if output_dir is not None:
            destination = Path(output_dir).expanduser().resolve()
            if not destination.is_dir():
                raise BridgeError("output_invalid", "Output directory must already exist and be a directory.")
        result = await self.call_tool_raw(profile, name, arguments, timeout=timeout)
        return serialize_result(result, destination)

    async def call_tool_raw(self, profile: str, name: str, arguments: dict, *, timeout: float = 300):
        """Preserve MCP images and metadata for protocol clients."""
        from mcp.types import CallToolResult
        if not isinstance(name, str) or not name.strip() or not isinstance(arguments, dict):
            raise BridgeError("arguments_invalid", "Tool name must be nonempty and arguments must be a JSON object.")
        with writer_lock(self.lock_path):
            result = await self._request(profile, "call", tool=name, arguments=arguments, timeout=timeout)
            return CallToolResult.model_validate(redact(result.model_dump(mode="json", by_alias=True, exclude_none=True)))

    def doctor(self) -> dict:
        return {"profiles": {name: {"command_found": shutil.which(p["command"]) is not None} for name, p in self.profiles.items()}, "checks": "Configuration and executable availability only; use tools and a read-only call to test the live connection."}


class PersistentBridgeClient(BridgeClient):
    """A borrowed session; valid only inside BridgeClient.persistent()."""
    def __init__(self, owner: BridgeClient, profile: str, session: ClientSession):
        self.config_path, self.profiles, self.lock_path = owner.config_path, owner.profiles, owner.lock_path
        self._profile, self._session = profile, session

    async def _request(self, profile: str, method: str, *, tool=None, arguments=None, timeout=300):
        if profile != self._profile:
            raise BridgeError("profile_mismatch", "Persistent connection belongs to a different profile.")
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or timeout <= 0:
            raise BridgeError("timeout_invalid", "Timeout must be a finite positive number.")
        try:
            async with asyncio.timeout(timeout):
                if method == "resources":
                    return await self._session.list_resources(cursor=arguments)
                if method == "read_resource":
                    return await self._session.read_resource(tool)
                if method == "tools":
                    items, cursor = [], None
                    while True:
                        page = await self._session.list_tools(cursor=cursor)
                        items.extend(t.model_dump(mode="json", by_alias=True, exclude_none=True) for t in page.tools)
                        cursor = page.nextCursor
                        if not cursor:
                            return redact({"tools": items})
                return await self._session.call_tool(tool, arguments=arguments)
        except TimeoutError:
            raise BridgeError("timeout", "Operation timed out. A dispatched Blender call may still be running; inspect Blender before retrying.") from None
        except BridgeError:
            raise
        except Exception:
            raise BridgeError("transport_error", "Persistent MCP request failed; no automatic retry or reconnect was attempted.") from None
