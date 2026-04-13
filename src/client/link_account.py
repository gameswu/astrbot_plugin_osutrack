"""Platform <-> osu! account linking (JSON persistence)."""

from __future__ import annotations

import json
import os
from typing import Optional, Union


class LinkAccountManager:
    """Bidirectional mapping between osu! IDs and platform user IDs."""

    def __init__(self, data_dir: str) -> None:
        self._path = os.path.join(data_dir, "osuaccount.json")
        self._ensure_file()

    # ------------------------------------------------------------------

    def _ensure_file(self) -> None:
        if not os.path.exists(self._path):
            os.makedirs(os.path.dirname(self._path), exist_ok=True)
            self._write({"osu_to_platforms": {}, "platform_to_osu": {}})

    def _read(self) -> dict:
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                data = json.load(f)
            data.setdefault("osu_to_platforms", {})
            data.setdefault("platform_to_osu", {})
            return data
        except (json.JSONDecodeError, FileNotFoundError):
            self._ensure_file()
            return {"osu_to_platforms": {}, "platform_to_osu": {}}

    def _write(self, data: dict) -> None:
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    # ------------------------------------------------------------------

    def link(self, osu_id: Union[str, int], platform_id: Union[str, int]) -> bool:
        osu_id, platform_id = str(osu_id), str(platform_id)
        data = self._read()

        existing = data["platform_to_osu"].get(platform_id)
        if existing and existing != osu_id:
            return False

        platforms = data["osu_to_platforms"].setdefault(osu_id, [])
        if platform_id not in platforms:
            platforms.append(platform_id)
        data["platform_to_osu"][platform_id] = osu_id

        self._write(data)
        return True

    def unlink(self, platform_id: Union[str, int]) -> bool:
        platform_id = str(platform_id)
        data = self._read()

        osu_id = data["platform_to_osu"].pop(platform_id, None)
        if osu_id is None:
            return False

        plist = data["osu_to_platforms"].get(osu_id, [])
        if platform_id in plist:
            plist.remove(platform_id)
        if not plist:
            data["osu_to_platforms"].pop(osu_id, None)

        self._write(data)
        return True

    def get_osu_id(self, platform_id: Union[str, int]) -> Optional[str]:
        return self._read()["platform_to_osu"].get(str(platform_id))

    def get_platform_ids(self, osu_id: Union[str, int]) -> list[str]:
        return self._read()["osu_to_platforms"].get(str(osu_id), [])

    def is_linked(self, platform_id: Union[str, int]) -> bool:
        return self.get_osu_id(platform_id) is not None
