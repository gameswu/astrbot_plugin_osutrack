"""Matches endpoints."""

from __future__ import annotations

from typing import Any, Optional

from ..api import OsuApi


class MatchesEndpoint:
    """Wrapper for /matches endpoints."""

    def __init__(self, api: OsuApi):
        self._api = api

    async def get_matches(
        self,
        *,
        limit: Optional[int] = None,
        sort: Optional[str] = None,
        active: Optional[bool] = None,
        cursor_string: Optional[str] = None,
    ) -> dict[str, Any]:
        """GET /matches

        Returns a list of matches.
        """
        params: dict[str, Any] = {}
        if limit is not None:
            params["limit"] = limit
        if sort is not None:
            params["sort"] = sort
        if active is not None:
            params["active"] = str(active).lower()
        if cursor_string is not None:
            params["cursor_string"] = cursor_string
        return await self._api.request("GET", "matches", params=params or None)

    async def get_match(
        self,
        match_id: int,
        *,
        before: Optional[int] = None,
        after: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> dict[str, Any]:
        """GET /matches/{match}

        Returns details of the specified match.
        """
        return await self._api.get(
            f"matches/{match_id}",
            before=before,
            after=after,
            limit=limit,
        )
