"""osu! API v2 SDK.

Usage::

    from src.osuapi import OsuApi

    api = OsuApi(client_id=..., client_secret=...)
    await api.client_credentials()
    user = await api.users.get_user(2)
"""

from .api import OsuApi, OsuApiError
from .enums import (
    Ruleset,
    RankStatus,
    Scope,
    RankingType,
    BeatmapPackType,
    UserBeatmapType,
    ScoreType,
    BeatmapsetSearchCategory,
    BeatmapsetSearchGenre,
    BeatmapsetSearchLanguage,
    BeatmapsetSearchSort,
    BeatmapsetSearchExplicitContent,
)
from .models import (
    User,
    UserExtended,
    UserStatistics,
    Beatmap,
    BeatmapExtended,
    Beatmapset,
    BeatmapsetExtended,
    BeatmapsetSearchResult,
    Score,
    BeatmapScores,
    BeatmapUserScore,
)
from .endpoints import (
    UsersEndpoint,
    BeatmapsEndpoint,
    BeatmapsetsEndpoint,
    RankingsEndpoint,
    ScoresEndpoint,
    MatchesEndpoint,
    ChangelogEndpoint,
    CommentsEndpoint,
    EventsEndpoint,
    NewsEndpoint,
    WikiEndpoint,
    SearchEndpoint,
    MultiplayerEndpoint,
    TeamsEndpoint,
    MiscEndpoint,
)

__all__ = [
    "OsuApi",
    "OsuApiError",
    # Enums
    "Ruleset",
    "RankStatus",
    "Scope",
    "RankingType",
    "BeatmapPackType",
    "UserBeatmapType",
    "ScoreType",
    "BeatmapsetSearchCategory",
    "BeatmapsetSearchGenre",
    "BeatmapsetSearchLanguage",
    "BeatmapsetSearchSort",
    "BeatmapsetSearchExplicitContent",
    # Models
    "User",
    "UserExtended",
    "UserStatistics",
    "Beatmap",
    "BeatmapExtended",
    "Beatmapset",
    "BeatmapsetExtended",
    "BeatmapsetSearchResult",
    "Score",
    "BeatmapScores",
    "BeatmapUserScore",
    # Endpoints
    "UsersEndpoint",
    "BeatmapsEndpoint",
    "BeatmapsetsEndpoint",
    "RankingsEndpoint",
    "ScoresEndpoint",
    "MatchesEndpoint",
    "ChangelogEndpoint",
    "CommentsEndpoint",
    "EventsEndpoint",
    "NewsEndpoint",
    "WikiEndpoint",
    "SearchEndpoint",
    "MultiplayerEndpoint",
    "TeamsEndpoint",
    "MiscEndpoint",
    "OsuClient",
]


class OsuClient(OsuApi):
    """High-level osu! API client with endpoint accessors.

    Usage::

        client = OsuClient(client_id=..., client_secret=...)
        await client.client_credentials()

        user = await client.users.get_user(2)
        beatmap = await client.beatmaps.get_beatmap(75)
    """

    def __init__(self, client_id: int, client_secret: str, redirect_uri: str = ""):
        super().__init__(client_id, client_secret, redirect_uri)
        self.users = UsersEndpoint(self)
        self.beatmaps = BeatmapsEndpoint(self)
        self.beatmapsets = BeatmapsetsEndpoint(self)
        self.rankings = RankingsEndpoint(self)
        self.scores = ScoresEndpoint(self)
        self.matches = MatchesEndpoint(self)
        self.changelog = ChangelogEndpoint(self)
        self.comments = CommentsEndpoint(self)
        self.events = EventsEndpoint(self)
        self.news = NewsEndpoint(self)
        self.wiki = WikiEndpoint(self)
        self.search = SearchEndpoint(self)
        self.multiplayer = MultiplayerEndpoint(self)
        self.teams = TeamsEndpoint(self)
        self.misc = MiscEndpoint(self)
