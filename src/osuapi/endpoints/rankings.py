"""Rankings endpoints."""

from __future__ import annotations

from typing import Any, Optional

from ..api import OsuApi


class RankingsEndpoint:
    """Wrapper for /rankings and /spotlights endpoints."""

    def __init__(self, api: OsuApi):
        self._api = api

    async def get_ranking(
        self,
        mode: str,
        type: str,
        *,
        country: Optional[str] = None,
        cursor_string: Optional[str] = None,
        filter: Optional[str] = None,
        spotlight: Optional[int] = None,
        variant: Optional[str] = None,
    ) -> dict[str, Any]:
        """GET /rankings/{mode}/{type}

        Gets the current ranking for the specified type and game mode.
        """
        return await self._api.get(
            f"rankings/{mode}/{type}",
            country=country,
            cursor_string=cursor_string,
            filter=filter,
            spotlight=spotlight,
            variant=variant,
        )

    async def get_kudosu_ranking(
        self,
        *,
        page: Optional[int] = None,
    ) -> dict[str, Any]:
        """GET /rankings/kudosu"""
        return await self._api.get("rankings/kudosu", page=page)

    async def get_spotlights(self) -> dict[str, Any]:
        """GET /spotlights"""
        return await self._api.get("spotlights")
