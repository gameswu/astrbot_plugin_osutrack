from .users import UsersEndpoint
from .beatmaps import BeatmapsEndpoint, BeatmapsetsEndpoint
from .rankings import RankingsEndpoint
from .scores import ScoresEndpoint
from .matches import MatchesEndpoint
from .changelog import ChangelogEndpoint
from .comments import CommentsEndpoint
from .events import EventsEndpoint
from .news import NewsEndpoint
from .wiki import WikiEndpoint
from .search import SearchEndpoint
from .multiplayer import MultiplayerEndpoint
from .teams import TeamsEndpoint
from .misc import MiscEndpoint

__all__ = [
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
]
