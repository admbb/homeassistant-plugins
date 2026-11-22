"""Read-only client for the NetFlow Plus HTTP API."""

from __future__ import annotations

from http.cookies import SimpleCookie

import aiohttp
from yarl import URL


class NetFlowError(Exception):
    """Safe API error that does not include credentials or response bodies."""


class AuthenticationError(NetFlowError):
    """The configured password was rejected."""


class PermissionDenied(NetFlowError):
    """The account cannot access the API."""


class NetFlowClient:
    """Client for NetFlow Plus. Data endpoints are GET-only."""

    def __init__(self, session: aiohttp.ClientSession, data: dict) -> None:
        self.session = session
        base = URL(data["url"])
        self.base = base.with_path(base.path.rstrip("/") + "/")
        self.password = data.get("password", "")
        self._cookie = ""

    async def authenticate(self) -> None:
        """Create an API session using the NetFlow Plus password."""
        try:
            async with self.session.post(
                self.base.join(URL("api/v1/login")),
                json={"password": self.password},
                timeout=aiohttp.ClientTimeout(total=12),
                allow_redirects=False,
            ) as response:
                if response.status == 401:
                    raise AuthenticationError("Authentication failed")
                if response.status == 403:
                    raise PermissionDenied("Permission denied")
                if response.status < 200 or response.status >= 300:
                    raise NetFlowError(f"HTTP {response.status}")
                cookies = response.cookies
                if cookies:
                    self._cookie = "; ".join(
                        f"{name}={cookie.value}" for name, cookie in cookies.items()
                    )
                else:
                    parsed = SimpleCookie()
                    for value in response.headers.getall("Set-Cookie", []):
                        parsed.load(value)
                    self._cookie = "; ".join(
                        f"{name}={cookie.value}" for name, cookie in parsed.items()
                    )
        except (aiohttp.ClientError, TimeoutError) as err:
            raise NetFlowError("Connection failed") from err

    async def get(self, path: str) -> dict:
        """GET one JSON API resource, refreshing the session once if needed."""
        for attempt in range(2):
            try:
                headers = {"Cookie": self._cookie} if self._cookie else None
                async with self.session.get(
                    self.base.join(URL(path)),
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=12),
                    allow_redirects=False,
                ) as response:
                    if response.status == 401 and attempt == 0:
                        await self.authenticate()
                        continue
                    if response.status == 401:
                        raise AuthenticationError("Authentication failed")
                    if response.status == 403:
                        raise PermissionDenied("Permission denied")
                    if response.status < 200 or response.status >= 300:
                        raise NetFlowError(f"HTTP {response.status}")
                    try:
                        payload = await response.json(content_type=None)
                    except (ValueError, aiohttp.ContentTypeError) as err:
                        raise NetFlowError("Invalid JSON response") from err
                    if not isinstance(payload, dict):
                        raise NetFlowError("Unexpected JSON response")
                    return payload
            except (aiohttp.ClientError, TimeoutError) as err:
                raise NetFlowError("Connection failed") from err
        raise NetFlowError("Authentication failed")

    async def status(self) -> dict:
        """Return NetFlow Plus engine status."""
        return await self.get("api/v1/status")

    async def app_ranking(self) -> dict:
        """Return the service's application ranking."""
        return await self.get("api/v1/domains/app-ranking")
