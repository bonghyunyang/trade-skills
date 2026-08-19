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
import customs as kcs  # noqa: E402
import analyze  # noqa: E402

ct.CACHE_DIR = FIXTURES
ct.CACHE_TTL_SECONDS = 10 ** 9
ct.MIN_INTERVAL = 0.0

# 관세청 캐시는 별도 디렉토리를 쓴다. 인증키는 테스트에서 절대 필요하지 않아야 한다 —
# 키가 있어야만 도는 오프라인 테스트는 CI 에서 조용히 건너뛰어진다.
# 오프라인 테스트는 _get 을 대체하므로 키가 쓰이지 않는다. 다만 URL 조립 단계에서
# 키를 요구하기 때문에 자리표시자가 필요하다 — 개발자의 진짜 키가 환경에 있든 없든
# 테스트가 똑같이 돌아야 한다.
os.environ["TRADE_STATS_CUSTOMS_KEY"] = "TEST-KEY-NOT-A-REAL-CREDENTIAL"

kcs.CACHE_DIR = FIXTURES / "customs"
kcs.CACHE_TTL_SECONDS = 10 ** 9
kcs.MIN_INTERVAL = 0.0


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
    kcs.urllib.request.urlopen = _refuse


def quiet_log(*_args, **_kwargs) -> None:
    """A no-op logger for functions that take one."""
