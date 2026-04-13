"""Comments endpoints."""

from __future__ import annotations

from typing import Any, Optional

from ..api import OsuApi


class CommentsEndpoint:
    """Wrapper for /comments endpoints."""

    def __init__(self, api: OsuApi):
        self._api = api

    async def get_comments(
        self,
        *,
        after: Optional[int] = None,
        commentable_type: Optional[str] = None,
        commentable_id: Optional[int] = None,
        cursor: Optional[str] = None,
        parent_id: Optional[int] = None,
        sort: Optional[str] = None,
    ) -> dict[str, Any]:
        """GET /comments

        Returns a list of comments and their replies up to 2 levels deep.
        """
        return await self._api.get(
            "comments",
            after=after,
            commentable_type=commentable_type,
            commentable_id=commentable_id,
            cursor=cursor,
            parent_id=parent_id,
            sort=sort,
        )

    async def get_comment(self, comment_id: int) -> dict[str, Any]:
        """GET /comments/{comment}

        Gets a comment and its replies up to 2 levels deep.
        """
        return await self._api.get(f"comments/{comment_id}")
