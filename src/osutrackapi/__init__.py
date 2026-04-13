"""osutrack API SDK.

Usage::

    from src.osutrackapi import OsuTrackApi, GameMode

    api = OsuTrackApi()
    resp = await api.update_user(user=2, mode=GameMode.OSU)
"""

from .api import OsuTrackApi, OsuTrackApiError
from .enums import GameMode, ScoreRank
from .models import (
    BestPlay,
    HiScore,
    PeakData,
    RecordedScore,
    StatsUpdate,
    UpdateResponse,
)

__all__ = [
    "OsuTrackApi",
    "OsuTrackApiError",
    "GameMode",
    "ScoreRank",
    "BestPlay",
    "HiScore",
    "PeakData",
    "RecordedScore",
    "StatsUpdate",
    "UpdateResponse",
]
