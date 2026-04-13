"""News endpoints."""

from __future__ import annotations

from typing import Any, Optional, Union

from ..api import OsuApi


class NewsEndpoint:
    """Wrapper for /news endpoints."""

    def __init__(self, api: OsuApi):
        self._api = api

    async def get_news_listing(
        self,
        *,
        limit: Optional[int] = None,
        year: Optional[int] = None,
        cursor_string: Optional[str] = None,
    ) -> dict[str, Any]:
        """GET /news

        Returns a list of news posts and related metadata.
        """
        return await self._api.get(
            "news",
            limit=limit,
            year=year,
            cursor_string=cursor_string,
        )

    async def get_news_post(
        self,
        news: Union[int, str],
        *,
        key: Optional[str] = None,
    ) -> dict[str, Any]:
        """GET /news/{news}

        Returns details of the specified news post.
        Pass key='id' when looking up by numeric ID.
        """
        return await self._api.get(f"news/{news}", key=key)
