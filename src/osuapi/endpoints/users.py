from __future__ import annotations

from typing import Any, Optional, Union

from ..api import OsuApi
from ..models.user import User, UserExtended


class UsersEndpoint:
    """Wrapper for /users endpoints."""

    def __init__(self, api: OsuApi):
        self._api = api

    async def get_user(
        self,
        user: Union[int, str],
        mode: Optional[str] = None,
    ) -> UserExtended:
        endpoint = f"users/{user}"
        if mode:
            endpoint += f"/{mode}"
        data = await self._api.get(endpoint)
        return UserExtended.from_dict(data)

    async def get_users(
        self,
        ids: list[int],
        include_variant_statistics: bool = False,
    ) -> list[UserExtended]:
        params: dict[str, Any] = {"ids[]": [str(i) for i in ids]}
        if include_variant_statistics:
            params["include_variant_statistics"] = "true"
        data = await self._api.request("GET", "users", params=params)
        return [UserExtended.from_dict(u) for u in data.get("users", [])]

    async def get_own_data(self, mode: Optional[str] = None) -> UserExtended:
        endpoint = "me"
        if mode:
            endpoint += f"/{mode}"
        data = await self._api.get(endpoint)
        return UserExtended.from_dict(data)

    async def get_friends(self) -> list[UserExtended]:
        data = await self._api.get("friends")
        if isinstance(data, list):
            return [UserExtended.from_dict(u) for u in data]
        return []

    async def get_user_kudosu(
        self,
        user_id: int,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> list[dict[str, Any]]:
        return await self._api.get(
            f"users/{user_id}/kudosu", limit=limit, offset=offset
        )

    async def get_user_scores(
        self,
        user_id: int,
        score_type: str,
        *,
        mode: Optional[str] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        include_fails: Optional[int] = None,
        legacy_only: Optional[int] = None,
    ) -> list[dict[str, Any]]:
        return await self._api.get(
            f"users/{user_id}/scores/{score_type}",
            mode=mode,
            limit=limit,
            offset=offset,
            include_fails=include_fails,
            legacy_only=legacy_only,
        )

    async def get_user_beatmaps(
        self,
        user_id: int,
        beatmap_type: str,
        *,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> list[dict[str, Any]]:
        return await self._api.get(
            f"users/{user_id}/beatmapsets/{beatmap_type}",
            limit=limit,
            offset=offset,
        )

    async def get_user_recent_activity(
        self,
        user_id: int,
        *,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> list[dict[str, Any]]:
        return await self._api.get(
            f"users/{user_id}/recent_activity",
            limit=limit,
            offset=offset,
        )

    async def get_user_beatmaps_passed(
        self,
        user_id: int,
        *,
        beatmapset_ids: Optional[list[int]] = None,
        exclude_converts: Optional[bool] = None,
        is_legacy: Optional[bool] = None,
        no_diff_reduction: Optional[bool] = None,
        ruleset_id: Optional[int] = None,
    ) -> dict[str, Any]:
        """GET /users/{user}/beatmaps-passed"""
        params: dict[str, Any] = {}
        if beatmapset_ids is not None:
            params["beatmapset_ids[]"] = [str(i) for i in beatmapset_ids]
        if exclude_converts is not None:
            params["exclude_converts"] = str(exclude_converts).lower()
        if is_legacy is not None:
            params["is_legacy"] = str(is_legacy).lower()
        if no_diff_reduction is not None:
            params["no_diff_reduction"] = str(no_diff_reduction).lower()
        if ruleset_id is not None:
            params["ruleset_id"] = ruleset_id
        return await self._api.request(
            "GET", f"users/{user_id}/beatmaps-passed", params=params or None
        )

    async def get_beatmapset_favourites(self) -> list[dict[str, Any]]:
        """GET /me/beatmapset-favourites"""
        data = await self._api.get("me/beatmapset-favourites")
        return data if isinstance(data, list) else []
