"""Shared utilities for the osu! plugin."""

from __future__ import annotations

import os
from typing import Any

import yaml

from .osutrackapi import GameMode

_help_cache: dict | None = None
_info_cache: dict | None = None

_PLUGIN_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_help_data() -> dict:
    global _help_cache
    if _help_cache is not None:
        return _help_cache
    path = os.path.join(_PLUGIN_DIR, "help.yaml")
    try:
        with open(path, "r", encoding="utf-8") as f:
            _help_cache = yaml.safe_load(f) or {}
    except Exception:
        _help_cache = {}
    return _help_cache


def load_info_data() -> dict:
    global _info_cache
    if _info_cache is not None:
        return _info_cache
    path = os.path.join(_PLUGIN_DIR, "info.yaml")
    try:
        with open(path, "r", encoding="utf-8") as f:
            _info_cache = yaml.safe_load(f) or {}
    except Exception:
        _info_cache = {}
    return _info_cache


def get_info(path: str, **kwargs: Any) -> str:
    """Lookup a dot-separated key in info.yaml and format with *kwargs*."""
    data: Any = load_info_data()
    for key in path.split("."):
        if isinstance(data, dict):
            data = data.get(key)
        else:
            return ""
    if data is None:
        return ""
    text = str(data)
    try:
        return text.format(**kwargs)
    except (KeyError, IndexError):
        return text


# ------------------------------------------------------------------
# Mode conversion helpers
# ------------------------------------------------------------------

_OSU_TO_TRACK: dict[str, GameMode] = {
    "osu": GameMode.OSU,
    "taiko": GameMode.TAIKO,
    "fruits": GameMode.CTB,
    "mania": GameMode.MANIA,
}

VALID_MODES = list(_OSU_TO_TRACK.keys())


def validate_osu_mode(mode: str | None) -> str:
    if not mode:
        return "osu"
    mode = mode.lower()
    if mode not in _OSU_TO_TRACK:
        raise ValueError(f"不支持的游戏模式: {mode}，支持的模式: {', '.join(VALID_MODES)}")
    return mode


def to_track_mode(osu_mode: str) -> GameMode:
    return _OSU_TO_TRACK[validate_osu_mode(osu_mode)]
