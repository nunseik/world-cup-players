"""Per-tier rate-limit budgets (requests per minute).

Sourced from settings so they can be tuned via env without code changes. The
limiter (api/rate_limit.py) looks up the authenticated client's tier here.
"""

from __future__ import annotations

from ..config import settings

# A request rate exceeding the tier budget within a one-minute window is rejected
# with HTTP 429. Unknown tiers fall back to the free budget.
TIER_LIMITS: dict[str, int] = {
    "free": settings.api_rate_free,
    "premium": settings.api_rate_premium,
}


def limit_for_tier(tier: str) -> int:
    """Per-minute request budget for a tier (free budget if the tier is unknown)."""
    return TIER_LIMITS.get(tier, settings.api_rate_free)


def effective_rate_limit(tier: str, is_verified: bool) -> int:
    """Per-minute budget after applying the unverified cap.

    Unverified clients are held to the (low) unverified rate even if their tier
    would allow more — until email verification exists, signups can't be trusted.
    """
    base = limit_for_tier(tier)
    return base if is_verified else min(base, settings.api_rate_unverified)


def max_page_size(is_verified: bool) -> int:
    """Largest page (rows per call) a client may request, per verification status."""
    return settings.api_max_page if is_verified else settings.api_max_page_unverified
