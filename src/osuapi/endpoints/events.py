"""Events endpoints."""

from __future__ import annotations

from typing import Any, Optional

from ..api import OsuApi


class EventsEndpoint:
    """Wrapper for /events endpoints."""

    def __init__(self, api: OsuApi):
        self._api = api

    async def get_events(
        self,
        *,
        sort: Optional[str] = None,
        cursor_string: Optional[str] = None,
    ) -> dict[str, Any]:
        """GET /events

        Returns a collection of Events in order of creation time.
        """
        return await self._api.get(
            "events",
            sort=sort,
            cursor_string=cursor_string,
        )
