from __future__ import annotations

from typing import Any, Optional, Union

from ..api import OsuApi
from ..models.beatmap import (
    Beatmap,
    BeatmapExtended,
    Beatmapset,
    BeatmapsetExtended,
    BeatmapsetSearchResult,
)
from ..models.score import BeatmapScores, BeatmapUserScore
from ..enums import (
    BeatmapsetSearchCategory,
    BeatmapsetSearchExplicitContent,
    BeatmapsetSearchGenre,
    BeatmapsetSearchLanguage,
    BeatmapsetSearchSort,
    Ruleset,
)


class BeatmapsEndpoint:
    """Wrapper for /beatmaps endpoints."""

    def __init__(self, api: OsuApi):
        self._api = api

    async def lookup(
        self,
        *,
        checksum: Optional[str] = None,
        filename: Optional[str] = None,
        id: Optional[int] = None,
    ) -> BeatmapExtended:
        data = await self._api.get(
            "beatmaps/lookup", checksum=checksum, filename=filename, id=id
        )
        return BeatmapExtended.from_dict(data)

    async def get_beatmap(self, beatmap_id: int) -> BeatmapExtended:
        data = await self._api.get(f"beatmaps/{beatmap_id}")
        return BeatmapExtended.from_dict(data)

    async def get_beatmaps(self, ids: list[int]) -> list[BeatmapExtended]:
        params: dict[str, Any] = {"ids[]": [str(i) for i in ids]}
        data = await self._api.request("GET", "beatmaps", params=params)
        return [BeatmapExtended.from_dict(b) for b in data.get("beatmaps", [])]

    async def get_beatmap_scores(
        self,
        beatmap_id: int,
        *,
        mode: Optional[str] = None,
        mods: Optional[str] = None,
        type: Optional[str] = None,
        legacy_only: Optional[int] = None,
    ) -> BeatmapScores:
        data = await self._api.get(
            f"beatmaps/{beatmap_id}/scores",
            mode=mode,
            mods=mods,
            type=type,
            legacy_only=legacy_only,
        )
        return BeatmapScores.from_dict(data)

    async def get_user_beatmap_score(
        self,
        beatmap_id: int,
        user_id: int,
        *,
        mode: Optional[str] = None,
        mods: Optional[str] = None,
        legacy_only: Optional[int] = None,
    ) -> BeatmapUserScore:
        data = await self._api.get(
            f"beatmaps/{beatmap_id}/scores/users/{user_id}",
            mode=mode,
            mods=mods,
            legacy_only=legacy_only,
        )
        return BeatmapUserScore.from_dict(data)

    async def get_user_beatmap_scores(
        self,
        beatmap_id: int,
        user_id: int,
        *,
        ruleset: Optional[str] = None,
        legacy_only: Optional[int] = None,
    ) -> list[dict[str, Any]]:
        data = await self._api.get(
            f"beatmaps/{beatmap_id}/scores/users/{user_id}/all",
            ruleset=ruleset,
            legacy_only=legacy_only,
        )
        return data.get("scores", [])

    async def get_beatmap_attributes(
        self,
        beatmap_id: int,
        *,
        mods: Optional[Any] = None,
        ruleset: Optional[str] = None,
        ruleset_id: Optional[int] = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {}
        if mods is not None:
            body["mods"] = mods
        if ruleset is not None:
            body["ruleset"] = ruleset
        if ruleset_id is not None:
            body["ruleset_id"] = ruleset_id
        data = await self._api.post(
            f"beatmaps/{beatmap_id}/attributes", json_body=body
        )
        return data.get("attributes", {})

    async def get_beatmap_packs(
        self,
        *,
        type: Optional[str] = None,
        cursor_string: Optional[str] = None,
    ) -> dict[str, Any]:
        """GET /beatmaps/packs"""
        return await self._api.get(
            "beatmaps/packs",
            type=type,
            cursor_string=cursor_string,
        )

    async def get_beatmap_pack(
        self,
        pack: str,
        *,
        legacy_only: Optional[int] = None,
    ) -> dict[str, Any]:
        """GET /beatmaps/packs/{pack}"""
        return await self._api.get(
            f"beatmaps/packs/{pack}",
            legacy_only=legacy_only,
        )


class BeatmapsetsEndpoint:
    """Wrapper for /beatmapsets endpoints."""

    def __init__(self, api: OsuApi):
        self._api = api

    async def get_beatmapset(self, beatmapset_id: int) -> BeatmapsetExtended:
        data = await self._api.get(f"beatmapsets/{beatmapset_id}")
        return BeatmapsetExtended.from_dict(data)

    async def lookup(
        self,
        *,
        checksum: Optional[str] = None,
        filename: Optional[str] = None,
    ) -> BeatmapsetExtended:
        data = await self._api.get(
            "beatmapsets/lookup", checksum=checksum, filename=filename
        )
        return BeatmapsetExtended.from_dict(data)

    async def search(
        self,
        *,
        query: Optional[str] = None,
        mode: Optional[Union[Ruleset, int]] = None,
        category: Optional[Union[BeatmapsetSearchCategory, str]] = None,
        explicit_content: Optional[Union[BeatmapsetSearchExplicitContent, str]] = None,
        genre: Optional[Union[BeatmapsetSearchGenre, int]] = None,
        language: Optional[Union[BeatmapsetSearchLanguage, int]] = None,
        sort: Optional[Union[BeatmapsetSearchSort, str]] = None,
        cursor_string: Optional[str] = None,
        extra: Optional[list[str]] = None,
    ) -> BeatmapsetSearchResult:
        params: dict[str, Any] = {}
        if query:
            params["q"] = query
        if mode is not None:
            params["m"] = mode.value if isinstance(mode, Ruleset) else str(mode)
        if category is not None:
            params["s"] = category.value if isinstance(category, BeatmapsetSearchCategory) else str(category)
        if explicit_content is not None:
            params["nsfw"] = explicit_content.value if isinstance(explicit_content, BeatmapsetSearchExplicitContent) else str(explicit_content)
        if genre is not None:
            params["g"] = genre.value if isinstance(genre, BeatmapsetSearchGenre) else int(genre)
        if language is not None:
            params["l"] = language.value if isinstance(language, BeatmapsetSearchLanguage) else int(language)
        if sort is not None:
            params["sort"] = sort.value if isinstance(sort, BeatmapsetSearchSort) else str(sort)
        if cursor_string:
            params["cursor_string"] = cursor_string
        if extra:
            params["e"] = ".".join(extra)

        data = await self._api.request("GET", "beatmapsets/search", params=params or None)
        return BeatmapsetSearchResult.from_dict(data)
