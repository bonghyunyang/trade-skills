#!/usr/bin/env python3
"""Thin CLI over the UN Comtrade preview API. Prints JSON to stdout.

Use this for one-off lookups. For a full market report use analyze.py.

  python3 fetch_comtrade.py hs-search "polyethylene" --level 6
  python3 fetch_comtrade.py country-search 카자흐
  python3 fetch_comtrade.py rank --hs 3907 --year 2023
  python3 fetch_comtrade.py series --hs 3907 --partner KZ --from 2023-01 --to 2024-12
  python3 fetch_comtrade.py mirror --hs 3907 --importer KZ --year 2023
"""

from __future__ import annotations

import argparse
import json
import sys

import comtrade as ct


def _out(obj) -> None:
    json.dump(obj, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")


def cmd_hs_search(a) -> None:
    rows = ct.search_hs(a.keyword, level=a.level, limit=a.limit)
    _out({"keyword": a.keyword, "count": len(rows), "results": rows})


def cmd_country_search(a) -> None:
    rows = ct.search_areas(a.keyword, limit=a.limit)
    _out({"keyword": a.keyword, "count": len(rows), "results": rows})


def cmd_rank(a) -> None:
    hs = ct.validate_hs(a.hs)
    reporter = ct.resolve_area(a.reporter)
    rows = ct.fetch(freq="A", period=a.year, reporter=reporter["code"],
                    partner=None, hs=hs, flow=a.flow)
    rows = [r for r in rows if r["partner_code"] not in (ct.WORLD, None)]
    rows.sort(key=lambda r: r["value_usd"] or 0, reverse=True)
    _out({"hs": hs, "hs_desc": ct.hs_desc(hs), "reporter": reporter["name"],
          "flow": a.flow, "year": a.year, "count": len(rows), "rows": rows[:a.limit]})


def cmd_series(a) -> None:
    hs = ct.validate_hs(a.hs)
    reporter = ct.resolve_area(a.reporter)
    partner = ct.resolve_area(a.partner) if a.partner else {"code": ct.WORLD, "name": "World"}
    periods = ct.months(a.start, a.end) if a.freq == "M" else [
        str(y) for y in range(int(a.start[:4]), int(a.end[:4]) + 1)
    ]
    rows = []
    for i, p in enumerate(periods, 1):
        if a.progress:
            print(f"  {i}/{len(periods)} {p}", file=sys.stderr)
        rows.extend(ct.fetch(freq=a.freq, period=p, reporter=reporter["code"],
                             partner=partner["code"], hs=hs, flow=a.flow))
    _out({"hs": hs, "hs_desc": ct.hs_desc(hs), "reporter": reporter["name"],
          "partner": partner["name"], "flow": a.flow, "freq": a.freq,
          "count": len(rows), "rows": rows})


def cmd_mirror(a) -> int:
    """Who supplies this importer? Mirror data = the competitor-share view."""
    hs = ct.validate_hs(a.hs)
    importer = ct.resolve_area(a.importer)
    if not ct.reports_to_comtrade(importer["code"]):
        # Exit non-zero: this printed an error object, and a shell pipeline that
        # checks $? must not read it as a successful empty result.
        _out({"error": "not_a_reporter",
              "message": f"{importer['name']}는 UN Comtrade에 보고하지 않아 미러 데이터가 없습니다."})
        return 1
    rows = ct.fetch(freq="A", period=a.year, reporter=importer["code"],
                    partner=None, hs=hs, flow="M")
    rows = [r for r in rows if r["partner_code"] not in (ct.WORLD, None)]
    total = sum(r["value_usd"] or 0 for r in rows)
    for r in rows:
        r["share_pct"] = round(100 * (r["value_usd"] or 0) / total, 2) if total else None
    rows.sort(key=lambda r: r["value_usd"] or 0, reverse=True)
    _out({"hs": hs, "hs_desc": ct.hs_desc(hs), "importer": importer["name"],
          "year": a.year, "total_imports_usd": total, "count": len(rows),
          "rows": rows[:a.limit]})


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("hs-search", help="HS코드 검색 (영문 설명 기준)")
    s.add_argument("keyword")
    s.add_argument("--level", type=int, choices=[2, 4, 6])
    s.add_argument("--limit", type=int, default=25)
    s.set_defaults(fn=cmd_hs_search)

    s = sub.add_parser("country-search", help="국가 코드 검색 (한글/영문/ISO)")
    s.add_argument("keyword")
    s.add_argument("--limit", type=int, default=20)
    s.set_defaults(fn=cmd_country_search)

    s = sub.add_parser("rank", help="특정 연도 전체 상대국 랭킹 (1콜)")
    s.add_argument("--hs", required=True)
    s.add_argument("--year", required=True)
    s.add_argument("--reporter", default="KR")
    s.add_argument("--flow", default="X", choices=["X", "M"])
    s.add_argument("--limit", type=int, default=60)
    s.set_defaults(fn=cmd_rank)

    s = sub.add_parser("series", help="시계열 (월간은 기간당 1콜, ~2초)")
    s.add_argument("--hs", required=True)
    s.add_argument("--from", dest="start", required=True)
    s.add_argument("--to", dest="end", required=True)
    s.add_argument("--reporter", default="KR")
    s.add_argument("--partner")
    s.add_argument("--flow", default="X", choices=["X", "M"])
    s.add_argument("--freq", default="M", choices=["M", "A"])
    s.add_argument("--progress", action="store_true")
    s.set_defaults(fn=cmd_series)

    s = sub.add_parser("mirror", help="수입국 기준 공급국 점유율 (경쟁 수출국)")
    s.add_argument("--hs", required=True)
    s.add_argument("--importer", required=True)
    s.add_argument("--year", required=True)
    s.add_argument("--limit", type=int, default=30)
    s.set_defaults(fn=cmd_mirror)

    a = p.parse_args()
    try:
        return a.fn(a) or 0
    except ct.ComtradeError as exc:
        _out({"error": "comtrade_error", "message": str(exc)})
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
