"""High-level osu! API wrapper with per-user token management."""

from __future__ import annotations

from typing import Any, Optional, Union

from ..osuapi import OsuClient, UserExtended, BeatmapExtended, BeatmapsetExtended, BeatmapsetSearchResult, Score, BeatmapScores, BeatmapUserScore
from ..osuapi.enums import (
    BeatmapsetSearchCategory,
    BeatmapsetSearchExplicitContent,
    BeatmapsetSearchGenre,
    BeatmapsetSearchLanguage,
    BeatmapsetSearchSort,
    Ruleset,
)
from .oauth_client import OAuthClient


class OsuApiClient:
    """Bridges :class:`OsuClient` (SDK) with :class:`OAuthClient` (per-user tokens).

    Every public method accepts a *platform_id* to select the right token.
    """

    def __init__(self, oauth: OAuthClient) -> None:
        self._oauth = oauth
        # We keep a shared OsuClient; before each call we swap in the
        # correct access token.
        self._api = OsuClient(
            client_id=oauth.api.client_id,
            client_secret=oauth.api.client_secret,
            redirect_uri=oauth.api.redirect_uri,
        )

    async def _set_token(self, platform_id: str) -> None:
        token = await self._oauth.ensure_token(platform_id)
        if not token:
            raise ValueError(f"没有有效的访问令牌 (platform_id={platform_id})，请先使用 /osu link 进行授权。")
        self._api.set_access_token(token)

    # ------------------------------------------------------------------
    # Users
    # ------------------------------------------------------------------

    async def get_user(
        self,
        platform_id: str,
        user: Union[int, str],
        mode: Optional[str] = None,
    ) -> UserExtended:
        await self._set_token(platform_id)
        if isinstance(user, str) and not user.startswith("@") and not user.isdigit():
            user = f"@{user}"
        return await self._api.users.get_user(user, mode=mode)

    async def get_users(
        self,
        platform_id: str,
        user_ids: list[Union[int, str]],
    ) -> list:
        await self._set_token(platform_id)
        ids = [int(uid) if str(uid).isdigit() else uid for uid in user_ids]
        return await self._api.users.get_users(ids)

    async def get_own_data(
        self,
        platform_id: str,
        mode: Optional[str] = None,
    ) -> UserExtended:
        await self._set_token(platform_id)
        return await self._api.users.get_own_data(mode=mode)

    async def get_friends(self, platform_id: str) -> list:
        await self._set_token(platform_id)
        return await self._api.users.get_friends()

    async def get_user_scores(
        self,
        platform_id: str,
        user_id: int,
        score_type: str,
        *,
        mode: Optional[str] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        include_fails: Optional[int] = None,
    ) -> list[Score]:
        await self._set_token(platform_id)
        data = await self._api.users.get_user_scores(
            user_id, score_type,
            mode=mode, limit=limit, offset=offset,
            include_fails=include_fails,
        )
        return [Score.from_dict(s) for s in data]

    # ------------------------------------------------------------------
    # Beatmaps
    # ------------------------------------------------------------------

    async def get_beatmap(self, platform_id: str, beatmap_id: int) -> BeatmapExtended:
        await self._set_token(platform_id)
        return await self._api.beatmaps.get_beatmap(beatmap_id)

    async def get_beatmapset(self, platform_id: str, beatmapset_id: int) -> BeatmapsetExtended:
        await self._set_token(platform_id)
        return await self._api.beatmapsets.get_beatmapset(beatmapset_id)

    async def search_beatmapsets(
        self,
        platform_id: str,
        query: Optional[str] = None,
        **kwargs: Any,
    ) -> BeatmapsetSearchResult:
        await self._set_token(platform_id)
        return await self._api.beatmapsets.search(query=query, **kwargs)

    async def get_beatmap_scores(
        self,
        platform_id: str,
        beatmap_id: int,
        *,
        mode: Optional[str] = None,
    ) -> BeatmapScores:
        await self._set_token(platform_id)
        return await self._api.beatmaps.get_beatmap_scores(beatmap_id, mode=mode)

    async def get_user_beatmap_score(
        self,
        platform_id: str,
        beatmap_id: int,
        user_id: int,
        *,
        mode: Optional[str] = None,
    ) -> BeatmapUserScore:
        await self._set_token(platform_id)
        return await self._api.beatmaps.get_user_beatmap_score(beatmap_id, user_id, mode=mode)

    # ------------------------------------------------------------------
    # Rankings
    # ------------------------------------------------------------------

    async def get_ranking(
        self, platform_id: str, mode: str, type: str, **kwargs: Any,
    ) -> dict[str, Any]:
        await self._set_token(platform_id)
        return await self._api.rankings.get_ranking(mode, type, **kwargs)

    async def get_kudosu_ranking(
        self, platform_id: str, **kwargs: Any,
    ) -> dict[str, Any]:
        await self._set_token(platform_id)
        return await self._api.rankings.get_kudosu_ranking(**kwargs)

    async def get_spotlights(self, platform_id: str) -> dict[str, Any]:
        await self._set_token(platform_id)
        return await self._api.rankings.get_spotlights()

    # ------------------------------------------------------------------
    # Scores
    # ------------------------------------------------------------------

    async def get_score(self, platform_id: str, score_id: int) -> Score:
        await self._set_token(platform_id)
        return await self._api.scores.get_score(score_id)

    async def get_scores_stream(
        self, platform_id: str, **kwargs: Any,
    ) -> dict[str, Any]:
        await self._set_token(platform_id)
        return await self._api.scores.get_scores(**kwargs)

    # ------------------------------------------------------------------
    # Matches
    # ------------------------------------------------------------------

    async def get_matches(
        self, platform_id: str, **kwargs: Any,
    ) -> dict[str, Any]:
        await self._set_token(platform_id)
        return await self._api.matches.get_matches(**kwargs)

    async def get_match(
        self, platform_id: str, match_id: int, **kwargs: Any,
    ) -> dict[str, Any]:
        await self._set_token(platform_id)
        return await self._api.matches.get_match(match_id, **kwargs)

    # ------------------------------------------------------------------
    # Beatmap Packs
    # ------------------------------------------------------------------

    async def get_beatmap_packs(
        self, platform_id: str, **kwargs: Any,
    ) -> dict[str, Any]:
        await self._set_token(platform_id)
        return await self._api.beatmaps.get_beatmap_packs(**kwargs)

    async def get_beatmap_pack(
        self, platform_id: str, pack: str, **kwargs: Any,
    ) -> dict[str, Any]:
        await self._set_token(platform_id)
        return await self._api.beatmaps.get_beatmap_pack(pack, **kwargs)

    # ------------------------------------------------------------------
    # Changelog
    # ------------------------------------------------------------------

    async def get_changelog_build(
        self, platform_id: str, stream: str, build: str,
    ) -> dict[str, Any]:
        await self._set_token(platform_id)
        return await self._api.changelog.get_changelog_build(stream, build)

    async def get_changelog_listing(
        self, platform_id: str, **kwargs: Any,
    ) -> dict[str, Any]:
        await self._set_token(platform_id)
        return await self._api.changelog.get_changelog_listing(**kwargs)

    async def lookup_changelog_build(
        self, platform_id: str, changelog: str, **kwargs: Any,
    ) -> dict[str, Any]:
        await self._set_token(platform_id)
        return await self._api.changelog.lookup_changelog_build(changelog, **kwargs)

    # ------------------------------------------------------------------
    # Comments
    # ------------------------------------------------------------------

    async def get_comments(
        self, platform_id: str, **kwargs: Any,
    ) -> dict[str, Any]:
        await self._set_token(platform_id)
        return await self._api.comments.get_comments(**kwargs)

    async def get_comment(
        self, platform_id: str, comment_id: int,
    ) -> dict[str, Any]:
        await self._set_token(platform_id)
        return await self._api.comments.get_comment(comment_id)

    # ------------------------------------------------------------------
    # Events
    # ------------------------------------------------------------------

    async def get_events(
        self, platform_id: str, **kwargs: Any,
    ) -> dict[str, Any]:
        await self._set_token(platform_id)
        return await self._api.events.get_events(**kwargs)

    # ------------------------------------------------------------------
    # News
    # ------------------------------------------------------------------

    async def get_news_listing(
        self, platform_id: str, **kwargs: Any,
    ) -> dict[str, Any]:
        await self._set_token(platform_id)
        return await self._api.news.get_news_listing(**kwargs)

    async def get_news_post(
        self, platform_id: str, news: Union[int, str], **kwargs: Any,
    ) -> dict[str, Any]:
        await self._set_token(platform_id)
        return await self._api.news.get_news_post(news, **kwargs)

    # ------------------------------------------------------------------
    # Wiki
    # ------------------------------------------------------------------

    async def get_wiki_page(
        self, platform_id: str, locale: str, path: str,
    ) -> dict[str, Any]:
        await self._set_token(platform_id)
        return await self._api.wiki.get_wiki_page(locale, path)

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    async def search_site(
        self, platform_id: str, **kwargs: Any,
    ) -> dict[str, Any]:
        await self._set_token(platform_id)
        return await self._api.search.search(**kwargs)

    # ------------------------------------------------------------------
    # Multiplayer
    # ------------------------------------------------------------------

    async def get_rooms(
        self, platform_id: str, **kwargs: Any,
    ) -> Any:
        await self._set_token(platform_id)
        return await self._api.multiplayer.get_rooms(**kwargs)

    async def get_room(
        self, platform_id: str, room_id: int,
    ) -> dict[str, Any]:
        await self._set_token(platform_id)
        return await self._api.multiplayer.get_room(room_id)

    async def get_playlist_scores(
        self, platform_id: str, room_id: int, playlist_id: int, **kwargs: Any,
    ) -> dict[str, Any]:
        await self._set_token(platform_id)
        return await self._api.multiplayer.get_playlist_scores(
            room_id, playlist_id, **kwargs
        )

    async def get_room_leaderboard(
        self, platform_id: str, room_id: int,
    ) -> dict[str, Any]:
        await self._set_token(platform_id)
        return await self._api.multiplayer.get_room_leaderboard(room_id)

    # ------------------------------------------------------------------
    # Teams
    # ------------------------------------------------------------------

    async def get_team(
        self, platform_id: str, team: Union[int, str], **kwargs: Any,
    ) -> dict[str, Any]:
        await self._set_token(platform_id)
        return await self._api.teams.get_team(team, **kwargs)

    # ------------------------------------------------------------------
    # Users (additional)
    # ------------------------------------------------------------------

    async def get_user_beatmaps_passed(
        self, platform_id: str, user_id: int, **kwargs: Any,
    ) -> dict[str, Any]:
        await self._set_token(platform_id)
        return await self._api.users.get_user_beatmaps_passed(user_id, **kwargs)

    async def get_beatmapset_favourites(
        self, platform_id: str,
    ) -> list[dict[str, Any]]:
        await self._set_token(platform_id)
        return await self._api.users.get_beatmapset_favourites()

    # ------------------------------------------------------------------
    # Misc
    # ------------------------------------------------------------------

    async def get_seasonal_backgrounds(
        self, platform_id: str,
    ) -> dict[str, Any]:
        await self._set_token(platform_id)
        return await self._api.misc.get_seasonal_backgrounds()

    async def get_tags(self, platform_id: str) -> list[dict[str, Any]]:
        await self._set_token(platform_id)
        return await self._api.misc.get_tags()

    # ------------------------------------------------------------------
    # Token helpers (delegated)
    # ------------------------------------------------------------------

    def has_valid_token(self, platform_id: str) -> bool:
        return self._oauth.has_valid_token(platform_id)

    def has_scope(self, platform_id: str, scope: str) -> bool:
        return self._oauth.has_scope(platform_id, scope)

    async def close(self) -> None:
        await self._api.close()
