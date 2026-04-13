"""Per-user token persistence (JSON file)."""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Optional


@dataclass
class TokenData:
    access_token: str
    refresh_token: str
    expires_at: float
    token_type: str = "Bearer"
    scope: str = "public identify"


class TokenManager:
    """Read / write per-platform-user OAuth tokens to a JSON file."""

    def __init__(self, data_dir: str) -> None:
        self._path = os.path.join(data_dir, "osu_tokens.json")
        self._ensure_file()

    # ------------------------------------------------------------------

    def _ensure_file(self) -> None:
        if not os.path.exists(self._path):
            os.makedirs(os.path.dirname(self._path), exist_ok=True)
            self._write({})

    def _read(self) -> dict:
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            self._ensure_file()
            return {}

    def _write(self, data: dict) -> None:
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    # ------------------------------------------------------------------

    def save(self, platform_id: str, token: TokenData) -> None:
        tokens = self._read()
        tokens[platform_id] = {
            "access_token": token.access_token,
            "refresh_token": token.refresh_token,
            "expires_at": token.expires_at,
            "token_type": token.token_type,
            "scope": token.scope,
        }
        self._write(tokens)

    def get(self, platform_id: str) -> Optional[TokenData]:
        entry = self._read().get(platform_id)
        if not entry:
            return None
        return TokenData(
            access_token=entry["access_token"],
            refresh_token=entry["refresh_token"],
            expires_at=entry["expires_at"],
            token_type=entry.get("token_type", "Bearer"),
            scope=entry.get("scope", "public identify"),
        )

    def is_expired(self, platform_id: str) -> bool:
        token = self.get(platform_id)
        if not token:
            return True
        return time.time() >= (token.expires_at - 300)

    def remove(self, platform_id: str) -> None:
        tokens = self._read()
        tokens.pop(platform_id, None)
        self._write(tokens)
