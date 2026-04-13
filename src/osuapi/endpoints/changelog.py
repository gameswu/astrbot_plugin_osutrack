"""Changelog endpoints."""

from __future__ import annotations

from typing import Any, Optional

from ..api import OsuApi


class ChangelogEndpoint:
    """Wrapper for /changelog endpoints."""

    def __init__(self, api: OsuApi):
        self._api = api

    async def get_changelog_build(
        self,
        stream: str,
        build: str,
    ) -> dict[str, Any]:
        """GET /changelog/{stream}/{build}

        Returns details of the specified build.
        """
        return await self._api.get(f"changelog/{stream}/{build}")

    async def get_changelog_listing(
        self,
        *,
        from_version: Optional[str] = None,
        max_id: Optional[int] = None,
        stream: Optional[str] = None,
        to: Optional[str] = None,
        message_formats: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        """GET /changelog

        Returns a listing of update streams, builds, and changelog entries.
        """
        params: dict[str, Any] = {}
        if from_version is not None:
            params["from"] = from_version
        if max_id is not None:
            params["max_id"] = max_id
        if stream is not None:
            params["stream"] = stream
        if to is not None:
            params["to"] = to
        if message_formats is not None:
            params["message_formats[]"] = message_formats
        return await self._api.request("GET", "changelog", params=params or None)

    async def lookup_changelog_build(
        self,
        changelog: str,
        *,
        key: Optional[str] = None,
        message_formats: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        """GET /changelog/{changelog}

        Returns details of the specified build (lookup by version, stream, or ID).
        """
        params: dict[str, Any] = {}
        if key is not None:
            params["key"] = key
        if message_formats is not None:
            params["message_formats[]"] = message_formats
        return await self._api.request(
            "GET", f"changelog/{changelog}", params=params or None
        )
