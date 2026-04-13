from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class UserStatistics:
    """A summary of gameplay statistics for a User, specific to a Ruleset."""
    count_100: int = 0
    count_300: int = 0
    count_50: int = 0
    count_miss: int = 0
    country_rank: Optional[int] = None
    grade_counts_a: int = 0
    grade_counts_s: int = 0
    grade_counts_sh: int = 0
    grade_counts_ss: int = 0
    grade_counts_ssh: int = 0
    hit_accuracy: Optional[float] = None
    accuracy: Optional[float] = None
    is_ranked: bool = False
    level_current: int = 0
    level_progress: float = 0.0
    maximum_combo: int = 0
    play_count: int = 0
    play_time: Optional[int] = None
    pp: Optional[float] = None
    global_rank: Optional[int] = None
    ranked_score: int = 0
    replays_watched_by_others: int = 0
    total_hits: int = 0
    total_score: int = 0

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> UserStatistics:
        grade = data.get("grade_counts", {})
        level = data.get("level", {})
        return cls(
            count_100=data.get("count_100", 0),
            count_300=data.get("count_300", 0),
            count_50=data.get("count_50", 0),
            count_miss=data.get("count_miss", 0),
            country_rank=data.get("country_rank"),
            grade_counts_a=grade.get("a", 0),
            grade_counts_s=grade.get("s", 0),
            grade_counts_sh=grade.get("sh", 0),
            grade_counts_ss=grade.get("ss", 0),
            grade_counts_ssh=grade.get("ssh", 0),
            hit_accuracy=data.get("hit_accuracy"),
            accuracy=data.get("accuracy"),
            is_ranked=data.get("is_ranked", False),
            level_current=level.get("current", 0),
            level_progress=level.get("progress", 0.0),
            maximum_combo=data.get("maximum_combo", 0),
            play_count=data.get("play_count", 0),
            play_time=data.get("play_time"),
            pp=data.get("pp"),
            global_rank=data.get("global_rank"),
            ranked_score=data.get("ranked_score", 0),
            replays_watched_by_others=data.get("replays_watched_by_others", 0),
            total_hits=data.get("total_hits", 0),
            total_score=data.get("total_score", 0),
        )


@dataclass
class UserBadge:
    awarded_at: str = ""
    description: str = ""
    image_url: str = ""
    image_2x_url: str = ""
    url: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> UserBadge:
        return cls(
            awarded_at=data.get("awarded_at", ""),
            description=data.get("description", ""),
            image_url=data.get("image_url", ""),
            image_2x_url=data.get("image@2x_url", ""),
            url=data.get("url", ""),
        )


@dataclass
class UserGroup:
    colour: Optional[str] = None
    has_listing: bool = False
    has_playmodes: bool = False
    id: int = 0
    identifier: str = ""
    is_probationary: bool = False
    name: str = ""
    short_name: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> UserGroup:
        return cls(
            colour=data.get("colour"),
            has_listing=data.get("has_listing", False),
            has_playmodes=data.get("has_playmodes", False),
            id=data.get("id", 0),
            identifier=data.get("identifier", ""),
            is_probationary=data.get("is_probationary", False),
            name=data.get("name", ""),
            short_name=data.get("short_name", ""),
        )


@dataclass
class UserCountry:
    code: str = ""
    name: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> UserCountry:
        return cls(code=data.get("code", ""), name=data.get("name", ""))


@dataclass
class UserCover:
    custom_url: Optional[str] = None
    url: str = ""
    id: Optional[str] = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> UserCover:
        return cls(
            custom_url=data.get("custom_url"),
            url=data.get("url", ""),
            id=data.get("id"),
        )


@dataclass
class RankHighest:
    rank: int = 0
    updated_at: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RankHighest:
        return cls(rank=data.get("rank", 0), updated_at=data.get("updated_at", ""))


@dataclass
class User:
    """Represents an osu! user (base object)."""
    avatar_url: str = ""
    country_code: str = ""
    default_group: Optional[str] = None
    id: int = 0
    is_active: bool = False
    is_bot: bool = False
    is_deleted: bool = False
    is_online: bool = False
    is_supporter: bool = False
    last_visit: Optional[str] = None
    pm_friends_only: bool = False
    profile_colour: Optional[str] = None
    username: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> User:
        return cls(
            avatar_url=data.get("avatar_url", ""),
            country_code=data.get("country_code", ""),
            default_group=data.get("default_group"),
            id=data.get("id", 0),
            is_active=data.get("is_active", False),
            is_bot=data.get("is_bot", False),
            is_deleted=data.get("is_deleted", False),
            is_online=data.get("is_online", False),
            is_supporter=data.get("is_supporter", False),
            last_visit=data.get("last_visit"),
            pm_friends_only=data.get("pm_friends_only", False),
            profile_colour=data.get("profile_colour"),
            username=data.get("username", ""),
        )


@dataclass
class UserExtended(User):
    """Extended user object with additional attributes."""
    country: Optional[UserCountry] = None
    cover: Optional[UserCover] = None
    statistics: Optional[UserStatistics] = None
    groups: list[UserGroup] = field(default_factory=list)
    badges: list[UserBadge] = field(default_factory=list)
    rank_highest: Optional[RankHighest] = None
    playmode: Optional[str] = None
    support_level: Optional[int] = None
    follower_count: Optional[int] = None
    favourite_beatmapset_count: Optional[int] = None
    graveyard_beatmapset_count: Optional[int] = None
    loved_beatmapset_count: Optional[int] = None
    pending_beatmapset_count: Optional[int] = None
    ranked_beatmapset_count: Optional[int] = None
    scores_best_count: Optional[int] = None
    scores_first_count: Optional[int] = None
    scores_recent_count: Optional[int] = None
    session_verified: Optional[bool] = None
    is_restricted: Optional[bool] = None
    previous_usernames: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> UserExtended:
        country_data = data.get("country")
        cover_data = data.get("cover")
        stats_data = data.get("statistics")
        rank_highest_data = data.get("rank_highest")

        return cls(
            # Base User fields
            avatar_url=data.get("avatar_url", ""),
            country_code=data.get("country_code", ""),
            default_group=data.get("default_group"),
            id=data.get("id", 0),
            is_active=data.get("is_active", False),
            is_bot=data.get("is_bot", False),
            is_deleted=data.get("is_deleted", False),
            is_online=data.get("is_online", False),
            is_supporter=data.get("is_supporter", False),
            last_visit=data.get("last_visit"),
            pm_friends_only=data.get("pm_friends_only", False),
            profile_colour=data.get("profile_colour"),
            username=data.get("username", ""),
            # Extended fields
            country=UserCountry.from_dict(country_data) if country_data else None,
            cover=UserCover.from_dict(cover_data) if cover_data else None,
            statistics=UserStatistics.from_dict(stats_data) if stats_data else None,
            groups=[UserGroup.from_dict(g) for g in data.get("groups", [])],
            badges=[UserBadge.from_dict(b) for b in data.get("badges", [])],
            rank_highest=RankHighest.from_dict(rank_highest_data) if rank_highest_data else None,
            playmode=data.get("playmode"),
            support_level=data.get("support_level"),
            follower_count=data.get("follower_count"),
            favourite_beatmapset_count=data.get("favourite_beatmapset_count"),
            graveyard_beatmapset_count=data.get("graveyard_beatmapset_count"),
            loved_beatmapset_count=data.get("loved_beatmapset_count"),
            pending_beatmapset_count=data.get("pending_beatmapset_count"),
            ranked_beatmapset_count=data.get("ranked_beatmapset_count"),
            scores_best_count=data.get("scores_best_count"),
            scores_first_count=data.get("scores_first_count"),
            scores_recent_count=data.get("scores_recent_count"),
            session_verified=data.get("session_verified"),
            is_restricted=data.get("is_restricted"),
            previous_usernames=data.get("previous_usernames", []),
        )
