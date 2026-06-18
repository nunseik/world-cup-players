"""Pure tests for the rate-limit decision and window math (no DB)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from world_cup.api.limits import limit_for_tier
from world_cup.api.rate_limit import (
    decide,
    seconds_until_hour_reset,
    seconds_until_window_reset,
)


def test_decide_allows_up_to_limit():
    assert decide(60, 60) is True
    assert decide(61, 60) is False


def test_tier_limits():
    assert limit_for_tier("free") == 60
    assert limit_for_tier("premium") == 600
    assert limit_for_tier("nonsense") == 60  # unknown -> free budget


@pytest.mark.parametrize("second,expected", [(0, 60), (1, 59), (59, 1)])
def test_seconds_until_window_reset(second, expected):
    now = datetime(2026, 6, 18, 12, 30, second, tzinfo=timezone.utc)
    assert seconds_until_window_reset(now) == expected


def test_seconds_until_hour_reset():
    now = datetime(2026, 6, 18, 12, 30, 0, tzinfo=timezone.utc)
    assert seconds_until_hour_reset(now) == 1800
