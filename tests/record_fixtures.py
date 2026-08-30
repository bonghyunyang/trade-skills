#!/usr/bin/env python3
"""Record live Comtrade responses into tests/fixtures/cache/.

The skill already caches raw payloads keyed by request URL, so pointing
TRADE_STATS_CACHE_DIR at the fixture directory makes the whole test suite run
offline against real recorded data — no mock layer to drift out of sync.

    python3 tests/record_fixtures.py          # record anything missing
    python3 tests/record_fixtures.py --force  # re-record everything

Re-record when Comtrade changes its response shape; that is exactly the failure
the brief flags as the top risk, and a diff in these files is the early warning.
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path

TESTS = Path(__file__).resolve().parent
FIXTURES = TESTS / "fixtures" / "cache"
SCRIPTS = TESTS.parent / "plugins" / "trade-stats" / "skills" / "trade-stats-lookup" / "scripts"
sys.path.insert(0, str(SCRIPTS))

# (label, kwargs for ct.fetch) — every query the test suite replays.
QUERIES = [
    # Korea's export rankings, three years, used by the e2e market run.
    ("kr-rank-2023", dict(freq="A", period=2023, reporter=410, partner=None, hs="3907", flow="X")),
    ("kr-rank-2024", dict(freq="A", period=2024, reporter=410, partner=None, hs="3907", flow="X")),
    ("kr-rank-2025", dict(freq="A", period=2025, reporter=410, partner=None, hs="3907", flow="X")),
    # World rows for the latest-year probe.
    ("kr-world-2025", dict(freq="A", period=2025, reporter=410, partner=0, hs="3907", flow="X")),
    ("kr-world-2026", dict(freq="A", period=2026, reporter=410, partner=0, hs="3907", flow="X")),
    # Mirrors for the e2e targets, plus their World totals (coverage check).
    # Every year in the walk-back chain is recorded: collect_competitors steps
    # back up to three years, and a missing fixture would make the test hit the
    # network instead of failing loudly.
    *[(f"{tag}-mirror-{y}", dict(freq="A", period=y, reporter=code, partner=None, hs="3907", flow="M"))
      for tag, code in (("vn", 704), ("us", 842), ("jp", 392))
      for y in (2025, 2024, 2023)],
    # World rows drive the market-CAGR axis, and collect_market_growth reaches
    # back up to three extra years when a reporter's mirror lags the window.
    *[(f"{tag}-world-{y}", dict(freq="A", period=y, reporter=code, partner=0, hs="3907", flow="M"))
      for tag, code in (("vn", 704), ("us", 842), ("jp", 392))
      for y in (2025, 2024, 2023, 2022, 2021, 2020)],
    *[(f"ly-world-{y}", dict(freq="A", period=y, reporter=434, partner=0, hs="3907", flow="M"))
      for y in (2025, 2024, 2023, 2022, 2021, 2020)],
    # Vietnam 3304: the mode-of-transport duplication case.
    ("vn-mirror-3304-2023", dict(freq="A", period=2023, reporter=704, partner=None, hs="3304", flow="M")),
    ("vn-world-3304-2023", dict(freq="A", period=2023, reporter=704, partner=0, hs="3304", flow="M")),
    # India 3907: hits the 500-row preview cap.
    ("in-mirror-2024", dict(freq="A", period=2024, reporter=699, partner=None, hs="3907", flow="M")),
    ("in-world-2024", dict(freq="A", period=2024, reporter=699, partner=0, hs="3907", flow="M")),
    # Libya: a reporter with no mirror data for this code (unscored path).
    ("ly-mirror-2025", dict(freq="A", period=2025, reporter=434, partner=None, hs="3907", flow="M")),
    ("ly-mirror-2024", dict(freq="A", period=2024, reporter=434, partner=None, hs="3907", flow="M")),
    ("ly-mirror-2023", dict(freq="A", period=2023, reporter=434, partner=None, hs="3907", flow="M")),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="기존 픽스처를 지우고 다시 녹화")
    args = ap.parse_args()

    if args.force and FIXTURES.exists():
        shutil.rmtree(FIXTURES)
    FIXTURES.mkdir(parents=True, exist_ok=True)

    os.environ["TRADE_STATS_CACHE_DIR"] = str(FIXTURES)
    import comtrade as ct
    ct.CACHE_DIR = FIXTURES
    ct.CACHE_TTL_SECONDS = 10 ** 9

    # 4단위 안에서 6단위가 얼마나 갈리는지 보는 조회. 자식 목록을 hs.json 에서 뽑으므로
    # 위 QUERIES 처럼 하드코딩할 수 없고, ct 를 import 한 뒤에야 만들 수 있다.
    # 3907 은 갈리는 코드(1위 27%), 3304 는 안 갈리는 코드(330499 가 90%)다.
    queries = list(QUERIES)
    for head in ("3907", "3304"):
        kids = sorted(str(r["code"]) for r in ct.hs_table()
                      if len(str(r["code"])) == 6 and str(r["code"]).startswith(head))
        queries.append((f"mix-{head}-2025",
                        dict(freq="A", period=2025, reporter=410, partner=0,
                             hs=",".join(kids), flow="X")))

    for label, kwargs in queries:
        rows = ct.fetch(**kwargs)
        print(f"  {label:<24} {len(rows):>4} rows")

    n = len(list(FIXTURES.glob('*.json')))
    print(f"\n{n}개 픽스처 → {FIXTURES}")
    if n < len(QUERIES):
        print("주의: 서로 다른 쿼리가 같은 URL로 합쳐졌는지 확인하세요.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
