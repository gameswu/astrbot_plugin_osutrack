"""Multiplayer endpoints."""

from __future__ import annotations

from typing import Any, Optional

from ..api import OsuApi


class MultiplayerEndpoint:
    """Wrapper for /rooms (multiplayer) endpoints."""

    def __init__(self, api: OsuApi):
        self._api = api

    async def get_rooms(
        self,
        *,
        limit: Optional[int] = None,
        mode: Optional[str] = None,
        season_id: Optional[int] = None,
        sort: Optional[str] = None,
        type_group: Optional[str] = None,
    ) -> Any:
        """GET /rooms

        Returns a list of multiplayer rooms.
        mode: 'active' (default), 'all', 'ended', 'participated', 'owned'.
        type_group: 'playlists' (default) or 'realtime'.
        """
        return await self._api.get(
            "rooms",
            limit=limit,
            mode=mode,
            season_id=season_id,
            sort=sort,
            type_group=type_group,
        )

    async def get_room(self, room_id: int) -> dict[str, Any]:
        """GET /rooms/{room}"""
        return await self._api.get(f"rooms/{room_id}")

    async def get_playlist_scores(
        self,
        room_id: int,
        playlist_id: int,
        *,
        limit: Optional[int] = None,
        sort: Optional[str] = None,
        cursor_string: Optional[str] = None,
    ) -> dict[str, Any]:
        """GET /rooms/{room}/playlist/{playlist}/scores

        Returns a list of scores for the specified playlist item.
        """
        return await self._api.get(
            f"rooms/{room_id}/playlist/{playlist_id}/scores",
            limit=limit,
            sort=sort,
            cursor_string=cursor_string,
        )

    async def get_room_leaderboard(self, room_id: int) -> dict[str, Any]:
        """GET /rooms/{room}/leaderboard"""
        return await self._api.get(f"rooms/{room_id}/leaderboard")
