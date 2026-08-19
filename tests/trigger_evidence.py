#!/usr/bin/env python3
"""트리거 테스트 판정 도구 — 무엇이 실제로 돌았는지 캐시로 읽는다.

에이전트에게 "무슨 도구 썼냐"고 물어 받는 답은 신뢰도가 낮다. 캐시 항목은 스킬을
실제로 실행해야만 생기고 위조되지 않는다.

명령이 셋으로 늘면서 "트리거됐다"만으로는 부족해졌다. market 을 돌려야 할 질문에
discover 가 돌면 6~10분을 태우고, 반대면 이미 아는 답만 나온다. 어느 쪽이 돌았는지까지
가려야 한다.

    python3 tests/trigger_evidence.py "2026-08-19 14:00"
    python3 tests/trigger_evidence.py --since-minutes 30
"""

from __future__ import annotations

import argparse
import collections
import json
import os
import subprocess
import sys
import time
from pathlib import Path

CACHE = Path(os.environ.get("TRADE_STATS_CACHE_DIR",
                            Path.home() / ".cache" / "trade-stats-lookup"))
KOREA = 410
WORLD = 0


def classify(payload: dict) -> str | None:
    """캐시 한 건이 어느 명령에서 나온 호출인지 되짚는다.

    호출 모양이 명령마다 다르다.
      discover : reporter 를 콤마로 묶어 여러 나라를 한 번에 부른다. 이 모양은 다른
                 명령이 절대 만들지 않아서 유일하게 확정적인 증거다.
      market   : 한국을 reporter 로 두고 상대국 전체를 부르거나(랭킹),
                 상대국 하나를 reporter 로 두고 공급국을 부른다(미러).
      products : 한국 reporter 에 cmdCode 가 AG2/AG4 집계다.

    미러 한 건(상대국 reporter + partner 에 World·한국)은 두 명령이 똑같이 만든다.
    이걸 discover 로 세면 market 실행이 discover 로 오염된다 — 실측에서 market 만
    돈 케이스에 'discover 2건' 이 찍혀 판정을 흐렸다. 그래서 공용으로 표기하고,
    가르는 건 규모에 맡긴다: discover 는 수십 건이 한꺼번에 쌓이고 market 은 몇 건이다.
    """
    rows = [r for r in (payload.get("data") or []) if isinstance(r, dict)]
    if not rows:
        return "빈 응답"

    reporters = {r.get("reporterCode") for r in rows}
    partners = {r.get("partnerCode") for r in rows}
    codes = {str(r.get("cmdCode") or "") for r in rows}

    if len(reporters) > 1:
        return "discover(다중 reporter)"
    if reporters == {KOREA}:
        if any(c.startswith("AG") for c in codes):
            return "products"
        return "market(한국 수출 랭킹)"
    if partners >= {WORLD, KOREA}:
        return "미러(market·discover 공용)"
    return "market(상대국 미러)"


def scan(since: float) -> tuple[collections.Counter, set, list]:
    kinds = collections.Counter()
    hs_codes: set[str] = set()
    for path in CACHE.glob("*.json"):
        try:
            if path.stat().st_mtime < since:
                continue
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        kinds[classify(payload)] += 1
        for r in (payload.get("data") or []):
            if isinstance(r, dict) and r.get("cmdCode"):
                hs_codes.add(str(r["cmdCode"]))

    customs = []
    cdir = CACHE / "customs"
    if cdir.exists():
        customs = [p for p in cdir.glob("*.json") if p.stat().st_mtime >= since]
    return kinds, hs_codes, customs


def reports(since: float) -> list[str]:
    """생성된 리포트 파일. 조회가 끝까지 갔다는 증거다.

    find(1) 에 맡기지 않는다. macOS 의 BSD find 는 `-newermt @<epoch>` 를 파싱하지
    못하고("Can't parse date/time"), /tmp 가 /private/tmp 심볼릭 링크라 따라가지도
    않는다. 둘 다 조용히 0건으로 돌아와 '스킬이 안 돌았다'로 오판하게 만든다.
    """
    roots = [Path.home() / "trade-stats-out", Path("/tmp"), Path("/private/tmp"),
             Path.cwd(), Path.home() / "Downloads", Path.home() / "Desktop"]
    seen, out = set(), []
    for root in roots:
        try:
            resolved = root.resolve()
        except OSError:
            continue
        if resolved in seen or not resolved.is_dir():
            continue
        seen.add(resolved)
        for path in resolved.rglob("hs*_report.md"):
            # 깊이 제한이 없으면 홈 디렉토리 전체를 훑다가 멈추지 않는다.
            if len(path.relative_to(resolved).parts) > 4:
                continue
            try:
                if path.stat().st_mtime >= since:
                    out.append(str(path))
            except OSError:
                continue
    return sorted(set(out))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("stamp", nargs="?", help='시작 시각 "YYYY-MM-DD HH:MM"')
    ap.add_argument("--since-minutes", type=float, help="몇 분 전부터")
    a = ap.parse_args()

    if a.since_minutes is not None:
        since = time.time() - a.since_minutes * 60
    elif a.stamp:
        since = time.mktime(time.strptime(a.stamp, "%Y-%m-%d %H:%M"))
    else:
        ap.error("시작 시각이나 --since-minutes 중 하나가 필요합니다")

    label = time.strftime("%Y-%m-%d %H:%M", time.localtime(since))
    print(f"기준 시각 이후: {label}\n")

    kinds, hs_codes, customs = scan(since)
    if not kinds and not customs:
        print("  새 캐시 없음 — 스킬이 안 돌았거나, 되묻기만 하고 끝났거나,")
        print("  이전 조회가 캐시에 남아 있어 네트워크를 안 탔습니다.")
        print("  (마지막 경우를 배제하려면 TRADE_STATS_CACHE_DIR 를 빈 폴더로 두고 돌리세요)")
    for kind, n in kinds.most_common():
        print(f"  {n:>4}건  {kind}")
    if customs:
        print(f"  {len(customs):>4}건  domestic(관세청) — 인증키가 설정돼 있었다는 뜻입니다")

    if hs_codes:
        short = sorted(c for c in hs_codes if len(c) <= 6)
        print(f"\n조회된 HS코드: {', '.join(short[:12])}"
              + (f" 외 {len(short) - 12}개" if len(short) > 12 else ""))

    found = reports(since)
    print(f"\n생성된 리포트: {len(found)}건")
    for f in found[:10]:
        print(f"  {f}")

    print("\n판정 기준")
    print("  '어느 나라부터' 계열  → market 이 돌아야 합니다")
    print("  '새로 뚫을 데' 계열   → discover 가 돌아야 합니다")
    print("  무관한 질문           → 아무것도 안 돌아야 합니다")
    print("  관세청은 사용자가 직접 요구하지 않았다면 돌면 안 됩니다")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
