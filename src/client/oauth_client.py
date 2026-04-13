"""OAuth flow orchestration – manages per-user tokens via the osu! API SDK."""

from __future__ import annotations

import time
import urllib.parse
from typing import Any, Optional

from ..osuapi import OsuApi
from .token_manager import TokenData, TokenManager


class OAuthClient:
    """Wraps the raw :class:`OsuApi` with per-platform-user token lifecycle."""

    def __init__(
        self,
        client_id: int,
        client_secret: str,
        redirect_uri: str,
        token_manager: TokenManager,
    ) -> None:
        self.api = OsuApi(client_id, client_secret, redirect_uri)
        self.token_manager = token_manager

    # ------------------------------------------------------------------
    # Authorization
    # ------------------------------------------------------------------

    def get_authorization_url(
        self,
        state: str = "",
        scopes: list[str] | None = None,
    ) -> str:
        return self.api.get_authorization_url(state, scopes)

    async def exchange_code(self, code: str, platform_id: str, scopes: list[str] | None = None) -> TokenData:
        """Exchange *code* for tokens and persist under *platform_id*."""
        data = await self.api.exchange_code(code)
        granted_scope = data.get("scope", "")
        if not granted_scope and scopes:
            granted_scope = " ".join(scopes)
        if not granted_scope:
            granted_scope = "public identify"
        token = TokenData(
            access_token=data["access_token"],
            refresh_token=data["refresh_token"],
            expires_at=time.time() + data.get("expires_in", 86400),
            token_type=data.get("token_type", "Bearer"),
            scope=granted_scope,
        )
        self.token_manager.save(platform_id, token)
        return token

    # ------------------------------------------------------------------
    # Token lifecycle
    # ------------------------------------------------------------------

    async def ensure_token(self, platform_id: str) -> Optional[str]:
        """Return a valid access token, refreshing if needed.

        Returns ``None`` when no usable token exists.
        """
        if self.token_manager.is_expired(platform_id):
            refreshed = await self._refresh(platform_id)
            if not refreshed:
                return None
        td = self.token_manager.get(platform_id)
        return td.access_token if td else None

    async def _refresh(self, platform_id: str) -> bool:
        td = self.token_manager.get(platform_id)
        if not td or not td.refresh_token:
            return False
        try:
            data = await self.api.refresh_access_token(td.refresh_token)
            new_td = TokenData(
                access_token=data["access_token"],
                refresh_token=data.get("refresh_token", td.refresh_token),
                expires_at=time.time() + data.get("expires_in", 86400),
                token_type=data.get("token_type", "Bearer"),
                scope=data.get("scope", td.scope),
            )
            self.token_manager.save(platform_id, new_td)
            return True
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def has_scope(self, platform_id: str, scope: str) -> bool:
        td = self.token_manager.get(platform_id)
        if not td:
            return False
        return scope in (td.scope or "").split()

    def has_valid_token(self, platform_id: str) -> bool:
        return not self.token_manager.is_expired(platform_id)

    def remove_token(self, platform_id: str) -> None:
        self.token_manager.remove(platform_id)

    async def get_user_info(self, platform_id: str) -> Optional[dict[str, Any]]:
        """Fetch /me for *platform_id*."""
        token = await self.ensure_token(platform_id)
        if not token:
            return None
        self.api.set_access_token(token)
        return await self.api.get("me")

    async def close(self) -> None:
        await self.api.close()
