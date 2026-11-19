"""Read-only OxiDNS management API client."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from urllib.parse import quote

import aiohttp
import yaml
from yarl import URL


class OxiDNSError(Exception):
    """API error; messages never include credentials or response bodies."""


class AuthenticationError(OxiDNSError):
    """Credentials rejected."""


class PermissionDenied(OxiDNSError):
    """Access denied."""


class NotFound(OxiDNSError):
    """Optional endpoint is absent."""


class ServiceUnavailable(OxiDNSError):
    """Endpoint explicitly reports service not ready."""


class OxiDNSClient:
    """Only GET operations; session is owned by Home Assistant."""

    def __init__(
        self, session: aiohttp.ClientSession, host: str, port: int, scheme: str, username: str = "", password: str = ""
    ) -> None:
        self.session = session
        self.base = URL.build(scheme=scheme, host=host, port=port, path="/api/")
        self.auth = aiohttp.BasicAuth(username, password) if username or password else None

    async def get(self, path: str, params: dict | None = None, *, json_response: bool = True):
        """Fetch a resource with a bounded timeout and explicit error mapping."""
        try:
            async with self.session.get(
                self.base.join(URL(path)),
                params=params,
                auth=self.auth,
                timeout=aiohttp.ClientTimeout(total=10),
                allow_redirects=False,
            ) as resp:
                self._check(resp.status)
                if json_response:
                    try:
                        return await resp.json(content_type=None)
                    except (ValueError, aiohttp.ContentTypeError) as err:
                        raise OxiDNSError("Invalid JSON response") from err
                return await resp.text()
        except (aiohttp.ClientError, TimeoutError) as err:
            raise OxiDNSError("Connection failed") from err

    @staticmethod
    def _check(status: int) -> None:
        if status == 401:
            raise AuthenticationError("Authentication failed")
        if status == 403:
            raise PermissionDenied("Permission denied")
        if status == 404:
            raise NotFound("Endpoint not found")
        if status == 503:
            raise ServiceUnavailable("Service unavailable")
        if status >= 400 or status < 200 or status >= 300:
            raise OxiDNSError(f"HTTP {status}")

    async def discover(self) -> dict:
        """Inspect capabilities and configured tags; never persist raw config."""
        if await self.get("healthz", json_response=False) != "ok":
            raise OxiDNSError("Unexpected health response")
        build = await self.get("build")
        tags = {"query_recorder": [], "metrics_collector": []}
        try:
            config = await self.get("config")
            parsed = await asyncio.to_thread(yaml.safe_load, config.get("content", "")) or {}
            for plugin in parsed.get("plugins", []):
                if isinstance(plugin, dict) and plugin.get("type") in tags and isinstance(plugin.get("tag"), str):
                    tags[plugin["type"]].append(plugin["tag"])
        except (OxiDNSError, yaml.YAMLError, AttributeError, TypeError):
            pass
        return {"build": build.get("build", {}), "tags": tags}

    @staticmethod
    def recorder_path(tag: str, endpoint: str) -> str:
        return f"plugins/{quote(tag, safe='')}/{endpoint}"

    async def stream(self, tag: str, tail: int = 50) -> AsyncIterator[tuple[str, str]]:
        """Yield SSE frames; read timeout doubles as heartbeat timeout."""
        timeout = aiohttp.ClientTimeout(total=None, sock_connect=10, sock_read=45)
        event, data, buffer = "message", [], b""
        try:
            async with self.session.get(
                self.base.join(URL(self.recorder_path(tag, "stream"))),
                params={"tail": tail},
                auth=self.auth,
                headers={"Accept": "text/event-stream"},
                timeout=timeout,
                allow_redirects=False,
            ) as resp:
                self._check(resp.status)
                if resp.content_type != "text/event-stream":
                    raise OxiDNSError("Unexpected stream content type")
                yield "__connected__", ""
                async for chunk in resp.content.iter_any():
                    buffer += chunk
                    while b"\n" in buffer:
                        raw, buffer = buffer.split(b"\n", 1)
                        line = raw.decode("utf-8", errors="replace").rstrip("\r")
                        if not line:
                            if data:
                                yield event, "\n".join(data)
                            event, data = "message", []
                        elif line.startswith(":"):
                            continue
                        elif line.startswith("event:"):
                            event = line[6:].lstrip(" ")
                        elif line.startswith("data:"):
                            data.append(line[5:].removeprefix(" "))
                        if len(buffer) + sum(map(len, data)) > 1048576:
                            raise OxiDNSError("Stream frame too large")
                    if len(buffer) + sum(map(len, data)) > 1048576:
                        raise OxiDNSError("Stream frame too large")
        except (TimeoutError, aiohttp.ClientError) as err:
            raise OxiDNSError("Stream connection failed") from err
