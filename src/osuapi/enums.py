from enum import Enum


class Ruleset(str, Enum):
    """osu! game rulesets (modes)."""
    OSU = "osu"
    TAIKO = "taiko"
    FRUITS = "fruits"
    MANIA = "mania"


class RankStatus(int, Enum):
    """Beatmap rank status."""
    GRAVEYARD = -2
    WIP = -1
    PENDING = 0
    RANKED = 1
    APPROVED = 2
    QUALIFIED = 3
    LOVED = 4


class Scope(str, Enum):
    """OAuth2 scopes."""
    CHAT_READ = "chat.read"
    CHAT_WRITE = "chat.write"
    CHAT_WRITE_MANAGE = "chat.write_manage"
    DELEGATE = "delegate"
    FORUM_WRITE = "forum.write"
    FORUM_WRITE_MANAGE = "forum.write_manage"
    FRIENDS_READ = "friends.read"
    IDENTIFY = "identify"
    PUBLIC = "public"


class RankingType(str, Enum):
    """Available ranking types."""
    CHARTS = "charts"
    COUNTRY = "country"
    PERFORMANCE = "performance"
    SCORE = "score"


class BeatmapPackType(str, Enum):
    """Available beatmap pack types."""
    STANDARD = "standard"
    FEATURED = "featured"
    TOURNAMENT = "tournament"
    LOVED = "loved"
    CHART = "chart"
    THEME = "theme"
    ARTIST = "artist"


class UserBeatmapType(str, Enum):
    """User beatmap types."""
    FAVOURITE = "favourite"
    GRAVEYARD = "graveyard"
    GUEST = "guest"
    LOVED = "loved"
    MOST_PLAYED = "most_played"
    NOMINATED = "nominated"
    PENDING = "pending"
    RANKED = "ranked"


class ScoreType(str, Enum):
    """Score types for user scores."""
    BEST = "best"
    FIRSTS = "firsts"
    RECENT = "recent"


class BeatmapsetSearchCategory(str, Enum):
    """Beatmapset search category filter."""
    ANY = ""
    HAS_LEADERBOARD = "leaderboard"
    RANKED = "ranked"
    QUALIFIED = "qualified"
    LOVED = "loved"
    FAVOURITES = "favourites"
    PENDING = "pending"
    WIP = "wip"
    GRAVEYARD = "graveyard"
    MINE = "mine"


class BeatmapsetSearchGenre(int, Enum):
    """Beatmapset search genre filter."""
    ANY = 0
    UNSPECIFIED = 1
    VIDEO_GAME = 2
    ANIME = 3
    ROCK = 4
    POP = 5
    OTHER = 6
    NOVELTY = 7
    HIP_HOP = 9
    ELECTRONIC = 10
    METAL = 11
    CLASSICAL = 12
    FOLK = 13
    JAZZ = 14


class BeatmapsetSearchLanguage(int, Enum):
    """Beatmapset search language filter."""
    ANY = 0
    UNSPECIFIED = 1
    ENGLISH = 2
    JAPANESE = 3
    CHINESE = 4
    INSTRUMENTAL = 5
    KOREAN = 6
    FRENCH = 7
    GERMAN = 8
    SWEDISH = 9
    SPANISH = 10
    ITALIAN = 11
    RUSSIAN = 12
    POLISH = 13
    OTHER = 14


class BeatmapsetSearchSort(str, Enum):
    """Beatmapset search sort options."""
    TITLE_DESC = "title_desc"
    TITLE_ASC = "title_asc"
    ARTIST_DESC = "artist_desc"
    ARTIST_ASC = "artist_asc"
    DIFFICULTY_DESC = "difficulty_desc"
    DIFFICULTY_ASC = "difficulty_asc"
    RANKED_DESC = "ranked_desc"
    RANKED_ASC = "ranked_asc"
    UPDATED_DESC = "updated_desc"
    UPDATED_ASC = "updated_asc"
    RATING_DESC = "rating_desc"
    RATING_ASC = "rating_asc"
    PLAYS_DESC = "plays_desc"
    PLAYS_ASC = "plays_asc"
    FAVOURITES_DESC = "favourites_desc"
    FAVOURITES_ASC = "favourites_asc"
    RELEVANCE_DESC = "relevance_desc"
    RELEVANCE_ASC = "relevance_asc"


class BeatmapsetSearchExplicitContent(str, Enum):
    """Beatmapset search explicit content filter."""
    HIDE = ""
    SHOW = "true"
