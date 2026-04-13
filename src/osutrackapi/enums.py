"""osutrack API enumerations."""

from enum import IntEnum, Enum


class GameMode(IntEnum):
    """osu! game modes used by osutrack."""
    OSU = 0
    TAIKO = 1
    CTB = 2
    MANIA = 3


class ScoreRank(str, Enum):
    """Score rank grades."""
    XH = "XH"   # Silver SS
    X = "X"     # Gold SS
    SH = "SH"   # Silver S
    S = "S"     # Gold S
    A = "A"
    B = "B"
    C = "C"
    D = "D"
    F = "F"
