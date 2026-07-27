"""Shared test setup: put the skill's scripts on sys.path and pin every
network call to the recorded fixture cache.

Importing this module must happen before ``comtrade``/``analyze``, because the
cache directory is read at import time.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

TESTS = Path(__file__).resolve().parent
REPO = TESTS.parent
SKILL = REPO / "plugins" / "trade-stats" / "skills" / "trade-stats-lookup"
SCRIPTS = SKILL / "scripts"
FIXTURES = TESTS / "fixtures" / "cache"

os.environ["TRADE_STATS_CACHE_DIR"] = str(FIXTURES)
os.environ["TRADE_STATS_CACHE_TTL"] = "1000000000"
# Fixtures answer instantly; no reason to hold the live 2s pacing in tests.
os.environ["TRADE_STATS_MIN_INTERVAL"] = "0"

sys.path.insert(0, str(SCRIPTS))

import comtrade as ct  # noqa: E402
import analyze  # noqa: E402

ct.CACHE_DIR = FIXTURES
ct.CACHE_TTL_SECONDS = 10 ** 9
ct.MIN_INTERVAL = 0.0


class NetworkAccessError(AssertionError):
    """Raised when a test reaches for the network instead of a fixture."""


def block_network() -> None:
    """Make any un-fixtured request a loud test failure.

    Without this a missing fixture silently turns into a live call: the suite
    still passes, but slowly and non-deterministically, and it would pass even
    if the fixture were deleted.
    """
    def _refuse(url, *a, **kw):
        raise NetworkAccessError(
            f"픽스처에 없는 요청입니다. tests/record_fixtures.py 에 추가하세요:\n  {url}")

    ct.urllib.request.urlopen = _refuse


def quiet_log(*_args, **_kwargs) -> None:
    """A no-op logger for functions that take one."""
