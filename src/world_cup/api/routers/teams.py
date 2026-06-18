"""Team endpoints (auth + rate-limited)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from .. import queries
from ..db import get_conn
from ..pagination import PageParams, page_params
from ..rate_limit import rate_limit
from ..schemas import Page, TeamOut

router = APIRouter(prefix="/v1/teams", tags=["teams"], dependencies=[Depends(rate_limit)])


@router.get("", response_model=Page[TeamOut])
def list_teams(
    confederation: str | None = None,
    page: PageParams = Depends(page_params),
    conn: Any = Depends(get_conn),
) -> Page[TeamOut]:
    return queries.list_teams(conn, confederation=confederation, limit=page.limit, offset=page.offset)
