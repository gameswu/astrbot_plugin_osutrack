"""Scores endpoints."""

from __future__ import annotations

from typing import Any, Optional

from ..api import OsuApi
from ..models.score import Score


class ScoresEndpoint:
    """Wrapper for /scores endpoints."""

    def __init__(self, api: OsuApi):
        self._api = api

    async def get_score(self, score_id: int) -> Score:
        """GET /scores/{score}

        Returns detail of the specified score.
        """
        data = await self._api.get(f"scores/{score_id}")
        return Score.from_dict(data)

    async def get_scores(
        self,
        *,
        ruleset: Optional[str] = None,
        cursor_string: Optional[str] = None,
    ) -> dict[str, Any]:
        """GET /scores

        Returns all passed scores. Up to 1000 scores returned per request.
        """
        return await self._api.get(
            "scores",
            ruleset=ruleset,
            cursor_string=cursor_string,
        )
