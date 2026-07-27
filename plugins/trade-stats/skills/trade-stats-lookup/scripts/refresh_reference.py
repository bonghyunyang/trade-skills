#!/usr/bin/env python3
"""Regenerate the bundled reference snapshots from UN Comtrade.

  python3 refresh_reference.py partners   # 한국 교역 상위국 순위
  python3 refresh_reference.py codes      # 국가/HS 코드 테이블
  python3 refresh_reference.py all

Reference data drifts slowly — running this once a year is plenty. Committing
the output is what keeps the skill usable offline-ish and fast.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request
from datetime import date
from pathlib import Path

import comtrade as ct

REF = ct.REF_DIR
FILES_BASE = "https://comtradeapi.un.org/files/v1/app/reference"


def refresh_codes() -> None:
    def grab(name: str):
        with urllib.request.urlopen(f"{FILES_BASE}/{name}.json", timeout=90) as r:
            return json.load(r)["results"]

    reporters, partners, hs = grab("Reporters"), grab("partnerAreas"), grab("HS")

    areas: dict[int, dict] = {}
    for r in reporters:
        c = int(r["reporterCode"])
        areas[c] = {"code": c, "name": (r["reporterDesc"] or "").strip(),
                    "iso2": r.get("reporterCodeIsoAlpha2"), "iso3": r.get("reporterCodeIsoAlpha3"),
                    "reporter": True, "partner": False}
    for p in partners:
        c = int(p["PartnerCode"])
        if c in areas:
            areas[c]["partner"] = True
        else:
            areas[c] = {"code": c, "name": (p["PartnerDesc"] or "").strip(),
                        "iso2": p.get("PartnerCodeIsoAlpha2"), "iso3": p.get("PartnerCodeIsoAlpha3"),
                        "reporter": False, "partner": True}
    # Dissolved states stay in the list and collide on ISO3 with current ones
    # ('Rep. of Vietnam (...1974)' vs 'Viet Nam'). Flag them so resolution can
    # deprioritize them instead of silently returning a code with no data.
    for a in areas.values():
        a["historical"] = bool(re.search(r"\(\.\.\.\d{4}\)", a["name"]))
    out = sorted(areas.values(), key=lambda a: a["code"])
    (REF / "areas.json").write_text(json.dumps(out, ensure_ascii=False, indent=0), encoding="utf-8")
    print(f"areas.json: {len(out)}개 지역 (보고국 {sum(a['reporter'] for a in out)}개)")

    slim = [{"code": h["id"], "desc": h["text"], "level": h.get("aggrLevel"),
             "unit": h.get("standardUnitAbbr")} for h in hs]
    (REF / "hs.json").write_text(json.dumps(slim, ensure_ascii=False, indent=0), encoding="utf-8")
    print(f"hs.json: {len(slim)}개 HS코드")


def refresh_partners(year: int | None) -> None:
    y = year or date.today().year
    rows: list[dict] = []
    for _ in range(3):
        rows = [r for r in ct.fetch(freq="A", period=y, reporter=ct.KOREA, partner=None,
                                    hs="TOTAL", flow="X", use_cache=False)
                if r["partner_code"] not in (ct.WORLD, None) and r["value_usd"]]
        if rows:
            break
        print(f"  {y}년 데이터 없음 → {y - 1}년", file=sys.stderr)
        y -= 1
    if not rows:
        raise ct.ComtradeError("한국 총수출 데이터를 찾지 못했습니다.")

    rows.sort(key=lambda r: r["value_usd"], reverse=True)
    total = sum(r["value_usd"] for r in rows)

    def rec(r: dict, rank: int) -> dict:
        a = next((x for x in ct.areas() if x["code"] == r["partner_code"]), {})
        return {"rank": rank, "code": r["partner_code"], "name": r["partner_name"],
                "iso2": a.get("iso2"), "export_usd": r["value_usd"],
                "share_pct": round(100 * r["value_usd"] / total, 2),
                "reports_to_comtrade": bool(a.get("reporter"))}

    data = {
        "source": "UN Comtrade preview, reporter=KOR, cmdCode=TOTAL, flow=X",
        "year": y,
        "generated": date.today().isoformat(),
        "partners": [rec(r, i) for i, r in enumerate(rows[:20], 1)],
        "test_partners": [rec(r, i) for i, r in enumerate(rows, 1)
                          if r["partner_code"] in (398, 860)],
    }
    (REF / "kr-top-partners.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"kr-top-partners.json: {y}년 기준 상위 20개국")
    for p in data["partners"][:10]:
        print(f"  {p['rank']:2d} {p['name']:<24} {p['share_pct']:5.2f}%")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("target", choices=["partners", "codes", "all"])
    p.add_argument("--year", type=int, help="partners 기준 연도 고정")
    a = p.parse_args()
    try:
        if a.target in ("codes", "all"):
            refresh_codes()
        if a.target in ("partners", "all"):
            refresh_partners(a.year)
    except ct.ComtradeError as exc:
        print(f"실패: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
