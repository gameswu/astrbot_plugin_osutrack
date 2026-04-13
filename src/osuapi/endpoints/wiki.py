"""Wiki endpoints."""

from __future__ import annotations

from typing import Any

from ..api import OsuApi


class WikiEndpoint:
    """Wrapper for /wiki endpoints."""

    def __init__(self, api: OsuApi):
        self._api = api

    async def get_wiki_page(self, locale: str, path: str) -> dict[str, Any]:
        """GET /wiki/{locale}/{path}

        Returns the wiki article or image data.
        """
        return await self._api.get(f"wiki/{locale}/{path}")
