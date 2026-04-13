from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class Score:
    """Represents an osu! score (API v2 version >= 20220705)."""
    accuracy: float = 0.0
    beatmap_id: int = 0
    best_id: Optional[int] = None
    build_id: Optional[int] = None
    ended_at: str = ""
    has_replay: bool = False
    id: int = 0
    is_perfect_combo: bool = False
    legacy_perfect: bool = False
    legacy_score_id: Optional[int] = None
    legacy_total_score: int = 0
    max_combo: int = 0
    mods: list[dict[str, Any]] = field(default_factory=list)
    passed: bool = False
    pp: Optional[float] = None
    rank: str = ""
    ruleset_id: int = 0
    started_at: Optional[str] = None
    total_score: int = 0
    replay: bool = False
    user_id: int = 0

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Score:
        return cls(
            accuracy=data.get("accuracy", 0.0),
            beatmap_id=data.get("beatmap_id", 0),
            best_id=data.get("best_id"),
            build_id=data.get("build_id"),
            ended_at=data.get("ended_at", ""),
            has_replay=data.get("has_replay", False),
            id=data.get("id", 0),
            is_perfect_combo=data.get("is_perfect_combo", False),
            legacy_perfect=data.get("legacy_perfect", False),
            legacy_score_id=data.get("legacy_score_id"),
            legacy_total_score=data.get("legacy_total_score", 0),
            max_combo=data.get("max_combo", 0),
            mods=data.get("mods", []),
            passed=data.get("passed", False),
            pp=data.get("pp"),
            rank=data.get("rank", ""),
            ruleset_id=data.get("ruleset_id", 0),
            started_at=data.get("started_at"),
            total_score=data.get("total_score", 0),
            replay=data.get("replay", False),
            user_id=data.get("user_id", 0),
        )


@dataclass
class BeatmapUserScore:
    """A user's score on a beatmap with position."""
    position: int = 0
    score: Optional[Score] = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BeatmapUserScore:
        score_data = data.get("score")
        return cls(
            position=data.get("position", 0),
            score=Score.from_dict(score_data) if score_data else None,
        )


@dataclass
class BeatmapScores:
    """Top scores for a beatmap."""
    scores: list[Score] = field(default_factory=list)
    user_score: Optional[BeatmapUserScore] = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BeatmapScores:
        user_score_data = data.get("userScore") or data.get("user_score")
        return cls(
            scores=[Score.from_dict(s) for s in data.get("scores", [])],
            user_score=BeatmapUserScore.from_dict(user_score_data) if user_score_data else None,
        )
