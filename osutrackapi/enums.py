from enum import Enum

class GameMode(Enum):
    """游戏模式枚举"""
    OSU = 0      # osu!
    TAIKO = 1    # taiko
    CTB = 2      # catch the beat (fruits)
    MANIA = 3    # mania

class UserMode(Enum):
    """用户查询模式枚举"""
    ID = "id"
    USERNAME = "username"

class ScoreRank(Enum):
    """成绩等级枚举"""
    X = "X"    # 银SS
    XH = "XH"  # 金SS
    S = "S"      # 银S
    SH = "SH"    # 金S
    A = "A"
    B = "B"
    C = "C"
    D = "D"
    F = "F"
