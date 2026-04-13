"""Miscellaneous endpoints."""

from __future__ import annotations

from typing import Any

from ..api import OsuApi


class MiscEndpoint:
    """Wrapper for miscellaneous endpoints (seasonal backgrounds, tags, etc.)."""

    def __init__(self, api: OsuApi):
        self._api = api

    async def get_seasonal_backgrounds(self) -> dict[str, Any]:
        """GET /seasonal-backgrounds

        Returns current seasonal backgrounds.
        """
        return await self._api.get("seasonal-backgrounds")

    async def get_tags(self) -> list[dict[str, Any]]:
        """GET /tags

        Returns all available beatmap tags.
        """
        data = await self._api.get("tags")
        return data if isinstance(data, list) else data.get("tags", [])
