"""Teams endpoints."""

from __future__ import annotations

from typing import Any, Optional, Union

from ..api import OsuApi


class TeamsEndpoint:
    """Wrapper for /teams endpoints."""

    def __init__(self, api: OsuApi):
        self._api = api

    async def get_team(
        self,
        team: Union[int, str],
        *,
        ruleset: Optional[str] = None,
    ) -> dict[str, Any]:
        """GET /teams/{team}/{ruleset?}

        Returns details of the specified team.
        team: ID or @-prefixed shortname.
        """
        endpoint = f"teams/{team}"
        if ruleset:
            endpoint += f"/{ruleset}"
        return await self._api.get(endpoint)
