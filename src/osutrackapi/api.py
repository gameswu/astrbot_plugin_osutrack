"""Low-level HTTP client for the osutrack API."""

from __future__ import annotations

import logging
from typing import Any, Optional, Union

import aiohttp

from .enums import GameMode
from .models import (
    BestPlay,
    PeakData,
    RecordedScore,
    StatsUpdate,
    UpdateResponse,
)

logger = logging.getLogger(__name__)

BASE_URL = "https://osutrack-api.ameo.dev"


class OsuTrackApiError(Exception):
    def __init__(self, status: int, message: str):
        self.status = status
        self.message = message
        super().__init__(f"[{status}] {message}")


class OsuTrackApi:
    """Async client for the osutrack REST API.

    Usage::

        api = OsuTrackApi()
        resp = await api.update_user(user=2, mode=GameMode.OSU)
        history = await api.get_stats_history(user=2, mode=GameMode.OSU)
        await api.close()
    """

    def __init__(self) -> None:
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @staticmethod
    def _mode_value(mode: Union[GameMode, int]) -> int:
        return mode.value if isinstance(mode, GameMode) else int(mode)

    async def _request(
        self,
        method: str,
        endpoint: str,
        params: dict[str, Any] | None = None,
    ) -> Any:
        session = await self._get_session()
        url = f"{BASE_URL}/{endpoint.lstrip('/')}"
        async with session.request(method, url, params=params) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise OsuTrackApiError(resp.status, text)
            return await resp.json()

    # ------------------------------------------------------------------
    # Endpoints
    # ------------------------------------------------------------------

    async def update_user(
        self,
        user: Union[int, str],
        mode: Union[GameMode, int] = GameMode.OSU,
    ) -> UpdateResponse:
        """POST /update – trigger a stats update for *user*."""
        data = await self._request(
            "POST",
            "update",
            params={"user": str(user), "mode": str(self._mode_value(mode))},
        )
        return UpdateResponse.from_dict(data)

    async def get_stats_history(
        self,
        user: Union[int, str],
        mode: Union[GameMode, int] = GameMode.OSU,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
    ) -> list[StatsUpdate]:
        """GET /stats_history – historical statistics snapshots."""
        params: dict[str, str] = {
            "user": str(user),
            "mode": str(self._mode_value(mode)),
        }
        if from_date:
            params["from"] = from_date
        if to_date:
            params["to"] = to_date
        data = await self._request("GET", "stats_history", params=params)
        return [StatsUpdate.from_dict(d) for d in data] if isinstance(data, list) else []

    async def get_hiscores(
        self,
        user: Union[int, str],
        mode: Union[GameMode, int] = GameMode.OSU,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
    ) -> list[RecordedScore]:
        """GET /hiscores – user's recorded best scores."""
        params: dict[str, str] = {
            "user": str(user),
            "mode": str(self._mode_value(mode)),
        }
        if from_date:
            params["from"] = from_date
        if to_date:
            params["to"] = to_date
        data = await self._request("GET", "hiscores", params=params)
        return [RecordedScore.from_dict(d) for d in data] if isinstance(data, list) else []

    async def get_peak(
        self,
        user: Union[int, str],
        mode: Union[GameMode, int] = GameMode.OSU,
    ) -> PeakData:
        """GET /peak – peak rank & accuracy."""
        data = await self._request(
            "GET",
            "peak",
            params={"user": str(user), "mode": str(self._mode_value(mode))},
        )
        if isinstance(data, list) and data:
            return PeakData.from_dict(data[0])
        return PeakData()

    async def get_best_plays(
        self,
        mode: Union[GameMode, int] = GameMode.OSU,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> list[BestPlay]:
        """GET /bestplays – global best plays (sorted by PP desc)."""
        params: dict[str, str] = {"mode": str(self._mode_value(mode))}
        if from_date:
            params["from"] = from_date
        if to_date:
            params["to"] = to_date
        if limit is not None:
            params["limit"] = str(limit)
        data = await self._request("GET", "bestplays", params=params)
        return [BestPlay.from_dict(d) for d in data] if isinstance(data, list) else []
