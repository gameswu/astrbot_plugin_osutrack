"""Search endpoints."""

from __future__ import annotations

from typing import Any, Optional

from ..api import OsuApi


class SearchEndpoint:
    """Wrapper for /search endpoints."""

    def __init__(self, api: OsuApi):
        self._api = api

    async def search(
        self,
        *,
        mode: Optional[str] = None,
        query: Optional[str] = None,
        page: Optional[int] = None,
    ) -> dict[str, Any]:
        """GET /search

        Searches users and wiki pages.
        mode: 'all', 'user', or 'wiki_page'. Default is 'all'.
        """
        return await self._api.get(
            "search",
            mode=mode,
            query=query,
            page=page,
        )
