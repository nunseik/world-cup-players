"""Shared pagination dependency that clamps page size to the caller's allowance.

Verified clients may request up to api_max_page rows; unverified clients are
capped at api_max_page_unverified. Centralized here so every list endpoint gets
the cap without repeating the logic.
"""

from __future__ import annotations

from fastapi import Depends, Query

from .auth import AuthContext, get_api_client
from .limits import max_page_size


class PageParams:
    def __init__(self, limit: int, offset: int) -> None:
        self.limit = limit
        self.offset = offset


def page_params(
    limit: int = Query(50, ge=1, le=200, description="Rows per page (capped lower for unverified accounts)"),
    offset: int = Query(0, ge=0),
    auth: AuthContext = Depends(get_api_client),
) -> PageParams:
    return PageParams(limit=min(limit, max_page_size(auth.is_verified)), offset=offset)
