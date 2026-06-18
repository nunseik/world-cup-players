"""Public self-serve signup: issues a free, time-limited API key.

Unauthenticated (the caller has no key yet), so it is guarded by a per-IP
hourly limit instead. Known weak spot: no email verification yet — a later
phase. Re-signing up with an existing email re-issues a fresh free key and
resets the tier to free (deliberate phase-1 simplicity).
"""

from __future__ import annotations

import re
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator

from ..db import get_writable
from ..keys import issue_key
from ..rate_limit import signup_rate_limit
from ..schemas import SignupOut

router = APIRouter(prefix="/v1", tags=["signup"])

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class SignupIn(BaseModel):
    email: str
    name: str | None = None

    @field_validator("email")
    @classmethod
    def _valid_email(cls, v: str) -> str:
        v = v.strip().lower()
        if not _EMAIL_RE.match(v):
            raise ValueError("invalid email address")
        return v


@router.post("/signup", response_model=SignupOut, dependencies=[Depends(signup_rate_limit)])
def signup(body: SignupIn, conn: Any = Depends(get_writable)) -> SignupOut:
    try:
        token, expires_at = issue_key(conn, body.email, tier="free", name=body.name)
    except Exception as exc:  # noqa: BLE001 - surface a clean 400 instead of a 500
        raise HTTPException(status_code=400, detail="Could not create API key.") from exc
    return SignupOut(api_key=token, tier="free", expires_at=expires_at)
