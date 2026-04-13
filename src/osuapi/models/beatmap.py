from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class BeatmapsetCovers:
    """Beatmapset cover images."""
    cover: str = ""
    cover_2x: str = ""
    card: str = ""
    card_2x: str = ""
    list: str = ""
    list_2x: str = ""
    slimcover: str = ""
    slimcover_2x: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BeatmapsetCovers:
        return cls(
            cover=data.get("cover", ""),
            cover_2x=data.get("cover@2x", ""),
            card=data.get("card", ""),
            card_2x=data.get("card@2x", ""),
            list=data.get("list", ""),
            list_2x=data.get("list@2x", ""),
            slimcover=data.get("slimcover", ""),
            slimcover_2x=data.get("slimcover@2x", ""),
        )


@dataclass
class Failtimes:
    """Beatmap failtimes."""
    exit: list[int] = field(default_factory=list)
    fail: list[int] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Failtimes:
        return cls(
            exit=data.get("exit", []),
            fail=data.get("fail", []),
        )


@dataclass
class Beatmap:
    """Represents an osu! beatmap (base object)."""
    beatmapset_id: int = 0
    difficulty_rating: float = 0.0
    id: int = 0
    mode: str = ""
    status: str = ""
    total_length: int = 0
    user_id: int = 0
    version: str = ""
    # Optional
    checksum: Optional[str] = None
    max_combo: Optional[int] = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Beatmap:
        return cls(
            beatmapset_id=data.get("beatmapset_id", 0),
            difficulty_rating=data.get("difficulty_rating", 0.0),
            id=data.get("id", 0),
            mode=data.get("mode", ""),
            status=data.get("status", ""),
            total_length=data.get("total_length", 0),
            user_id=data.get("user_id", 0),
            version=data.get("version", ""),
            checksum=data.get("checksum"),
            max_combo=data.get("max_combo"),
        )


@dataclass
class BeatmapExtended(Beatmap):
    """Extended beatmap with additional fields."""
    ar: Optional[float] = None
    bpm: Optional[float] = None
    cs: Optional[float] = None
    drain: Optional[float] = None
    accuracy: Optional[float] = None  # OD
    count_circles: Optional[int] = None
    count_sliders: Optional[int] = None
    count_spinners: Optional[int] = None
    hit_length: Optional[int] = None
    playcount: Optional[int] = None
    passcount: Optional[int] = None
    url: Optional[str] = None
    beatmapset: Optional[Beatmapset] = None
    failtimes: Optional[Failtimes] = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BeatmapExtended:
        beatmapset_data = data.get("beatmapset")
        failtimes_data = data.get("failtimes")
        return cls(
            # Base
            beatmapset_id=data.get("beatmapset_id", 0),
            difficulty_rating=data.get("difficulty_rating", 0.0),
            id=data.get("id", 0),
            mode=data.get("mode", ""),
            status=data.get("status", ""),
            total_length=data.get("total_length", 0),
            user_id=data.get("user_id", 0),
            version=data.get("version", ""),
            checksum=data.get("checksum"),
            max_combo=data.get("max_combo"),
            # Extended
            ar=data.get("ar"),
            bpm=data.get("bpm"),
            cs=data.get("cs"),
            drain=data.get("drain"),
            accuracy=data.get("accuracy"),
            count_circles=data.get("count_circles"),
            count_sliders=data.get("count_sliders"),
            count_spinners=data.get("count_spinners"),
            hit_length=data.get("hit_length"),
            playcount=data.get("playcount"),
            passcount=data.get("passcount"),
            url=data.get("url"),
            beatmapset=Beatmapset.from_dict(beatmapset_data) if beatmapset_data else None,
            failtimes=Failtimes.from_dict(failtimes_data) if failtimes_data else None,
        )


@dataclass
class Beatmapset:
    """Represents an osu! beatmapset (base object)."""
    artist: str = ""
    artist_unicode: str = ""
    covers: Optional[BeatmapsetCovers] = None
    creator: str = ""
    favourite_count: int = 0
    id: int = 0
    nsfw: bool = False
    offset: int = 0
    play_count: int = 0
    preview_url: str = ""
    source: str = ""
    status: str = ""
    spotlight: bool = False
    title: str = ""
    title_unicode: str = ""
    user_id: int = 0
    video: bool = False
    # Optional
    beatmaps: list[Beatmap] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Beatmapset:
        covers_data = data.get("covers")
        beatmaps_data = data.get("beatmaps", [])
        return cls(
            artist=data.get("artist", ""),
            artist_unicode=data.get("artist_unicode", ""),
            covers=BeatmapsetCovers.from_dict(covers_data) if covers_data else None,
            creator=data.get("creator", ""),
            favourite_count=data.get("favourite_count", 0),
            id=data.get("id", 0),
            nsfw=data.get("nsfw", False),
            offset=data.get("offset", 0),
            play_count=data.get("play_count", 0),
            preview_url=data.get("preview_url", ""),
            source=data.get("source", ""),
            status=data.get("status", ""),
            spotlight=data.get("spotlight", False),
            title=data.get("title", ""),
            title_unicode=data.get("title_unicode", ""),
            user_id=data.get("user_id", 0),
            video=data.get("video", False),
            beatmaps=[BeatmapExtended.from_dict(b) if "ar" in b else Beatmap.from_dict(b)
                      for b in beatmaps_data],
        )


@dataclass
class BeatmapsetExtended(Beatmapset):
    """Extended beatmapset with additional fields."""
    bpm: Optional[float] = None
    ranked_date: Optional[str] = None
    submitted_date: Optional[str] = None
    last_updated: Optional[str] = None
    tags: str = ""
    ratings: list[int] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BeatmapsetExtended:
        covers_data = data.get("covers")
        beatmaps_data = data.get("beatmaps", [])
        return cls(
            # Base
            artist=data.get("artist", ""),
            artist_unicode=data.get("artist_unicode", ""),
            covers=BeatmapsetCovers.from_dict(covers_data) if covers_data else None,
            creator=data.get("creator", ""),
            favourite_count=data.get("favourite_count", 0),
            id=data.get("id", 0),
            nsfw=data.get("nsfw", False),
            offset=data.get("offset", 0),
            play_count=data.get("play_count", 0),
            preview_url=data.get("preview_url", ""),
            source=data.get("source", ""),
            status=data.get("status", ""),
            spotlight=data.get("spotlight", False),
            title=data.get("title", ""),
            title_unicode=data.get("title_unicode", ""),
            user_id=data.get("user_id", 0),
            video=data.get("video", False),
            beatmaps=[BeatmapExtended.from_dict(b) if "ar" in b else Beatmap.from_dict(b)
                      for b in beatmaps_data],
            # Extended
            bpm=data.get("bpm"),
            ranked_date=data.get("ranked_date"),
            submitted_date=data.get("submitted_date"),
            last_updated=data.get("last_updated"),
            tags=data.get("tags", ""),
            ratings=data.get("ratings", []),
        )


@dataclass
class BeatmapsetSearchResult:
    """Result from beatmapset search endpoint."""
    beatmapsets: list[Beatmapset] = field(default_factory=list)
    cursor_string: Optional[str] = None
    total: int = 0

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BeatmapsetSearchResult:
        return cls(
            beatmapsets=[Beatmapset.from_dict(bs) for bs in data.get("beatmapsets", [])],
            cursor_string=data.get("cursor_string"),
            total=data.get("total", 0),
        )

    def __len__(self) -> int:
        return self.total
