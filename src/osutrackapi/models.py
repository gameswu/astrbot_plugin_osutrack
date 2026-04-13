"""osutrack API data models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class HiScore:
    """A new high-score entry returned by the update endpoint."""
    beatmap_id: str = ""
    score_id: str = ""
    score: str = ""
    maxcombo: str = ""
    count50: str = ""
    count100: str = ""
    count300: str = ""
    countmiss: str = ""
    countkatu: str = ""
    countgeki: str = ""
    perfect: str = ""
    enabled_mods: str = ""
    user_id: str = ""
    date: str = ""
    rank: str = ""
    pp: str = ""
    replay_available: str = ""
    ranking: int = 0

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> HiScore:
        return cls(
            beatmap_id=str(data.get("beatmap_id", "")),
            score_id=str(data.get("score_id", "")),
            score=str(data.get("score", "")),
            maxcombo=str(data.get("maxcombo", "")),
            count50=str(data.get("count50", "")),
            count100=str(data.get("count100", "")),
            count300=str(data.get("count300", "")),
            countmiss=str(data.get("countmiss", "")),
            countkatu=str(data.get("countkatu", "")),
            countgeki=str(data.get("countgeki", "")),
            perfect=str(data.get("perfect", "")),
            enabled_mods=str(data.get("enabled_mods", "")),
            user_id=str(data.get("user_id", "")),
            date=str(data.get("date", "")),
            rank=str(data.get("rank", "")),
            pp=str(data.get("pp", "")),
            replay_available=str(data.get("replay_available", "")),
            ranking=int(data.get("ranking", 0)),
        )


@dataclass
class UpdateResponse:
    """Response from POST /update."""
    username: str = ""
    mode: int = 0
    playcount: int = 0
    pp_rank: int = 0
    pp_raw: float = 0.0
    accuracy: float = 0.0
    total_score: int = 0
    ranked_score: int = 0
    count300: int = 0
    count50: int = 0
    count100: int = 0
    level: float = 0.0
    count_rank_a: int = 0
    count_rank_s: int = 0
    count_rank_ss: int = 0
    levelup: bool = False
    first: bool = False
    exists: bool = True
    newhs: list[HiScore] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> UpdateResponse:
        newhs = [
            HiScore.from_dict(h)
            for h in data.get("newhs", [])
            if isinstance(h, dict)
        ]
        return cls(
            username=str(data.get("username", "")),
            mode=int(data.get("mode", 0)),
            playcount=int(data.get("playcount", 0)),
            pp_rank=int(data.get("pp_rank", 0)),
            pp_raw=float(data.get("pp_raw", 0.0)),
            accuracy=float(data.get("accuracy", 0.0)),
            total_score=int(data.get("total_score", 0)),
            ranked_score=int(data.get("ranked_score", 0)),
            count300=int(data.get("count300", 0)),
            count50=int(data.get("count50", 0)),
            count100=int(data.get("count100", 0)),
            level=float(data.get("level", 0.0)),
            count_rank_a=int(data.get("count_rank_a", 0)),
            count_rank_s=int(data.get("count_rank_s", 0)),
            count_rank_ss=int(data.get("count_rank_ss", 0)),
            levelup=bool(data.get("levelup", False)),
            first=bool(data.get("first", False)),
            exists=bool(data.get("exists", True)),
            newhs=newhs,
        )


@dataclass
class StatsUpdate:
    """A single stats-history record."""
    count300: int = 0
    count100: int = 0
    count50: int = 0
    playcount: int = 0
    ranked_score: str = "0"
    total_score: str = "0"
    pp_rank: int = 0
    level: float = 0.0
    pp_raw: float = 0.0
    accuracy: float = 0.0
    count_rank_ss: int = 0
    count_rank_s: int = 0
    count_rank_a: int = 0
    timestamp: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StatsUpdate:
        return cls(
            count300=int(data.get("count300", 0)),
            count100=int(data.get("count100", 0)),
            count50=int(data.get("count50", 0)),
            playcount=int(data.get("playcount", 0)),
            ranked_score=str(data.get("ranked_score", "0")),
            total_score=str(data.get("total_score", "0")),
            pp_rank=int(data.get("pp_rank", 0)),
            level=float(data.get("level", 0.0)),
            pp_raw=float(data.get("pp_raw", 0.0)),
            accuracy=float(data.get("accuracy", 0.0)),
            count_rank_ss=int(data.get("count_rank_ss", 0)),
            count_rank_s=int(data.get("count_rank_s", 0)),
            count_rank_a=int(data.get("count_rank_a", 0)),
            timestamp=str(data.get("timestamp", "")),
        )


@dataclass
class RecordedScore:
    """A recorded best-score entry from hiscores endpoint."""
    beatmap_id: int = 0
    score: int = 0
    pp: float = 0.0
    mods: int = 0
    rank: str = ""
    score_time: str = ""
    update_time: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RecordedScore:
        return cls(
            beatmap_id=int(data.get("beatmap_id", 0)),
            score=int(data.get("score", 0)),
            pp=float(data.get("pp", 0.0)),
            mods=int(data.get("mods", 0)),
            rank=str(data.get("rank", "")),
            score_time=str(data.get("score_time", "")),
            update_time=str(data.get("update_time", "")),
        )


@dataclass
class PeakData:
    """Peak rank / accuracy data."""
    best_global_rank: Optional[int] = None
    best_rank_timestamp: Optional[str] = None
    best_accuracy: Optional[float] = None
    best_acc_timestamp: Optional[str] = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PeakData:
        return cls(
            best_global_rank=data.get("best_global_rank"),
            best_rank_timestamp=data.get("best_rank_timestamp"),
            best_accuracy=data.get("best_accuracy"),
            best_acc_timestamp=data.get("best_acc_timestamp"),
        )


@dataclass
class BestPlay:
    """A best-play entry from the global bestplays endpoint."""
    user: int = 0
    beatmap_id: int = 0
    score: int = 0
    pp: float = 0.0
    mods: int = 0
    rank: str = ""
    score_time: str = ""
    update_time: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BestPlay:
        return cls(
            user=int(data.get("user", 0)),
            beatmap_id=int(data.get("beatmap_id", 0)),
            score=int(data.get("score", 0)),
            pp=float(data.get("pp", 0.0)),
            mods=int(data.get("mods", 0)),
            rank=str(data.get("rank", "")),
            score_time=str(data.get("score_time", "")),
            update_time=str(data.get("update_time", "")),
        )
