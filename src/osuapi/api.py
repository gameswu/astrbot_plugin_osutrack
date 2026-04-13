from __future__ import annotations

import json
import logging
import urllib.parse
from typing import Any, Optional

import aiohttp

logger = logging.getLogger(__name__)

BASE_URL = "https://osu.ppy.sh/api/v2"
TOKEN_URL = "https://osu.ppy.sh/oauth/token"
AUTHORIZE_URL = "https://osu.ppy.sh/oauth/authorize"


class OsuApiError(Exception):
    """Base exception for osu! API errors."""

    def __init__(self, status: int, message: str):
        self.status = status
        self.message = message
        super().__init__(f"[{status}] {message}")


class OsuApi:
    """Low-level HTTP client for the osu! API v2.

    Handles authentication (Client Credentials & Authorization Code),
    token refresh, and raw request execution.
    """

    def __init__(
        self,
        client_id: int,
        client_secret: str,
        redirect_uri: str = "",
    ):
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self._access_token: Optional[str] = None
        self._refresh_token: Optional[str] = None
        self._token_type: str = "Bearer"
        self._scope: str = ""
        self._session: Optional[aiohttp.ClientSession] = None

    # ------------------------------------------------------------------
    # Session management
    # ------------------------------------------------------------------

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    # ------------------------------------------------------------------
    # OAuth helpers
    # ------------------------------------------------------------------

    def get_authorization_url(self, state: str = "", scopes: list[str] | None = None) -> str:
        """Build the user authorization URL."""
        scope_str = " ".join(scopes) if scopes else "public identify"
        params = {
            "client_id": str(self.client_id),
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": scope_str,
            "state": state,
        }
        return f"{AUTHORIZE_URL}?{urllib.parse.urlencode(params)}"

    async def exchange_code(self, code: str) -> dict[str, Any]:
        """Exchange an authorization code for tokens."""
        session = await self._get_session()
        payload = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": self.redirect_uri,
        }
        async with session.post(
            TOKEN_URL,
            data=payload,
            headers={"Accept": "application/json"},
        ) as resp:
            data = await resp.json()
            if resp.status != 200:
                raise OsuApiError(resp.status, str(data))
            self._apply_token(data)
            return data

    async def client_credentials(self, scopes: list[str] | None = None) -> dict[str, Any]:
        """Obtain a Client Credentials token."""
        session = await self._get_session()
        payload = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "grant_type": "client_credentials",
            "scope": " ".join(scopes) if scopes else "public",
        }
        async with session.post(
            TOKEN_URL,
            data=payload,
            headers={"Accept": "application/json"},
        ) as resp:
            data = await resp.json()
            if resp.status != 200:
                raise OsuApiError(resp.status, str(data))
            self._apply_token(data)
            return data

    async def refresh_access_token(self, refresh_token: str | None = None) -> dict[str, Any]:
        """Refresh an access token."""
        token = refresh_token or self._refresh_token
        if not token:
            raise OsuApiError(0, "No refresh token available")
        session = await self._get_session()
        payload = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "grant_type": "refresh_token",
            "refresh_token": token,
        }
        async with session.post(
            TOKEN_URL,
            data=payload,
            headers={"Accept": "application/json"},
        ) as resp:
            data = await resp.json()
            if resp.status != 200:
                raise OsuApiError(resp.status, str(data))
            self._apply_token(data)
            return data

    def set_access_token(self, token: str) -> None:
        """Manually set the Bearer token."""
        self._access_token = token

    def _apply_token(self, data: dict[str, Any]) -> None:
        self._access_token = data.get("access_token")
        self._refresh_token = data.get("refresh_token")
        self._token_type = data.get("token_type", "Bearer")
        self._scope = data.get("scope", "")

    # ------------------------------------------------------------------
    # Request helpers
    # ------------------------------------------------------------------

    async def request(
        self,
        method: str,
        endpoint: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> Any:
        """Execute an authenticated API request.

        Returns the parsed JSON response.
        """
        if not self._access_token:
            raise OsuApiError(0, "No access token set. Authenticate first.")

        session = await self._get_session()
        url = f"{BASE_URL}/{endpoint.lstrip('/')}"
        headers = {
            "Authorization": f"{self._token_type} {self._access_token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

        # Flatten list params (e.g. ids[])
        real_params: list[tuple[str, str]] | None = None
        if params:
            real_params = []
            for key, value in params.items():
                if isinstance(value, list):
                    for item in value:
                        real_params.append((key, str(item)))
                elif value is not None:
                    real_params.append((key, str(value)))

        data_str = json.dumps(json_body) if json_body else None

        async with session.request(
            method,
            url,
            headers=headers,
            params=real_params,
            data=data_str,
        ) as resp:
            if resp.status == 204:
                return None
            body = await resp.json()
            if resp.status >= 400:
                raise OsuApiError(resp.status, str(body))
            return body

    async def get(self, endpoint: str, **params: Any) -> Any:
        cleaned = {k: v for k, v in params.items() if v is not None}
        return await self.request("GET", endpoint, params=cleaned or None)

    async def post(self, endpoint: str, *, params: dict | None = None, json_body: dict | None = None) -> Any:
        return await self.request("POST", endpoint, params=params, json_body=json_body)

    async def put(self, endpoint: str, *, params: dict | None = None, json_body: dict | None = None) -> Any:
        return await self.request("PUT", endpoint, params=params, json_body=json_body)

    async def delete(self, endpoint: str, **params: Any) -> Any:
        cleaned = {k: v for k, v in params.items() if v is not None}
        return await self.request("DELETE", endpoint, params=cleaned or None)
