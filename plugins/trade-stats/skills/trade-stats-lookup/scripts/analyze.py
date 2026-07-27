#!/usr/bin/env python3
"""Market prioritisation report for one HS code.

  python3 analyze.py market --hs 3907 --countries KZ,UZ,KG --outdir ./out
  python3 analyze.py market --hs 330499 --top 10 --years 4 --monthly 24

Writes CSVs plus a Korean markdown report, and prints a JSON summary so the
calling agent can narrate without re-reading the files.

Call budget (each Comtrade call is paced ~2s):
  ranking      = --years calls
  competitor   = 2 calls per target country (supplier list + World total)
  market CAGR  = --years calls per target country, mostly served from cache
  monthly      = --monthly calls per target country   (opt-in, the expensive part)
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
import sys
from datetime import date
from pathlib import Path

import comtrade as ct

KOREA = ct.KOREA


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------


def cagr(first: float | None, last: float | None, years: int) -> float | None:
    if not first or not last or first <= 0 or last <= 0 or years <= 0:
        return None
    return (last / first) ** (1 / years) - 1


def unit_price(value: float | None, weight: float | None) -> float | None:
    if not value or not weight or weight <= 0:
        return None
    return value / weight


def latest_available_year(hs: str, log) -> int:
    """Comtrade annual data lags. Walk back from this year until rows appear."""
    y = date.today().year
    for _ in range(4):
        rows = ct.fetch(freq="A", period=y, reporter=KOREA, partner=ct.WORLD,
                        hs=hs, flow="X")
        if rows and (rows[0].get("value_usd") or 0) > 0:
            return y
        log(f"  {y}년 데이터 없음 → {y - 1}년으로 후퇴")
        y -= 1
    raise ct.ComtradeError(f"HS {hs} 의 최근 연간 데이터를 찾지 못했습니다.")


# --------------------------------------------------------------------------
# data collection
# --------------------------------------------------------------------------


def collect_rankings(hs: str, years: list[int], log) -> dict[int, dict[int, dict]]:
    """{year: {partner_code: row}} of Korea's exports of `hs`."""
    out: dict[int, dict[int, dict]] = {}
    for y in years:
        log(f"  랭킹 조회 {y}...")
        rows = ct.fetch(freq="A", period=y, reporter=KOREA, partner=None, hs=hs, flow="X")
        out[y] = {r["partner_code"]: r for r in rows
                  if r["partner_code"] not in (ct.WORLD, None)}
        if any(r.get("_truncated") for r in rows):
            log(f"  ! {y}년 응답이 500행 상한에 걸려 하위 국가가 잘렸을 수 있습니다.")
    return out


def collect_competitors(hs: str, area: dict, year: int, log) -> dict:
    """Mirror view: who supplies this importer, and where does Korea sit."""
    if not ct.reports_to_comtrade(area["code"]):
        return {"available": False,
                "reason": f"{area['name']}는 UN Comtrade 보고국이 아닙니다."}
    used_year = year
    rows: list[dict] = []
    for attempt in range(3):
        log(f"  경쟁국 조회 {area['name']} {used_year}...")
        rows = [r for r in ct.fetch(freq="A", period=used_year, reporter=area["code"],
                                    partner=None, hs=hs, flow="M")
                if r["partner_code"] not in (ct.WORLD, None)]
        if rows:
            break
        used_year -= 1
    if not rows:
        return {"available": False,
                "reason": f"{area['name']}의 {year}년 전후 수입 미러 데이터가 없습니다."}

    partner_sum = sum(r["value_usd"] or 0 for r in rows)

    # The reporter's own World row is the authoritative total. Comparing it to
    # the partner sum turns the 500-row preview cap from an unknown into a
    # measured number: reporters that split by mode of transport blow past the
    # cap, and without this check a truncated tail silently inflates every share.
    world = ct.fetch(freq="A", period=used_year, reporter=area["code"],
                     partner=ct.WORLD, hs=hs, flow="M")

    # The World row itself can arrive as a partner2Code breakdown — India's 2024
    # HS3907 World request returns 88 rows, one per country of consignment, plus
    # the real aggregate. _collapse_breakdowns picks the aggregate when present,
    # but falls back to summing when it is not, and that sum is exactly double.
    # Since this value is the denominator of every share, trusting a summed one
    # would halve all of them silently. Prefer the partner sum in that case.
    world_row = world[0] if world else None
    world_total = None
    if world_row and not world_row.get("is_partial_sum"):
        world_total = world_row["value_usd"]
    elif world_row:
        log(f"  ! {area['name']} World 합계 행이 잘려 내역 합산값입니다 — 분모로 쓰지 않습니다.")

    total = world_total or partner_sum
    coverage = (partner_sum / world_total) if world_total else None
    truncated = any(r.get("_truncated") for r in rows)

    rows.sort(key=lambda r: r["value_usd"] or 0, reverse=True)
    suppliers = [{
        "supplier": r["partner_name"],
        "supplier_code": r["partner_code"],
        "value_usd": r["value_usd"],
        "share_pct": round(100 * (r["value_usd"] or 0) / total, 2) if total else None,
        "unit_price_usd_per_kg": unit_price(r["value_usd"], r["net_weight_kg"]),
    } for r in rows]
    kr = next((s for s in suppliers if s["supplier_code"] == KOREA), None)

    partial = sum(1 for r in rows if r.get("is_partial_sum"))
    warning = None
    if coverage is not None and coverage < 0.99:
        detail = (f" 이 중 {partial}개국은 합계 행이 잘려 내역 합산으로 추정한 값이라 과소집계됩니다."
                  if partial else "")
        warning = (f"공급국 목록이 총수입의 {coverage * 100:.1f}%만 덮습니다 "
                   f"(500행 상한).{detail} 점유율 분모는 공식 총수입이므로 상위 공급국 "
                   f"점유율은 유효하지만, 목록과 하위 순위는 완전하지 않습니다.")
        log(f"  ! {area['name']}: {warning}")
    elif truncated:
        pct = f"{coverage * 100:.1f}%" if coverage is not None else "확인 불가"
        log(f"  {area['name']}: 500행 상한에 걸렸으나 파트너 합계가 총수입의 {pct} — 사실상 누락 없음")

    # A low Korean share reads as "room to grow", but the room may already be
    # occupied: Korea holds 1.4% of India's HS8507 imports and China holds 87%.
    # Headroom alone cannot tell those apart, so carry the incumbent alongside it.
    top = suppliers[0] if suppliers else None
    top_share = (top or {}).get("share_pct")

    return {
        "available": True,
        "year": used_year,
        "stale": used_year != year,
        "total_imports_usd": total,
        "partner_coverage_pct": round(coverage * 100, 1) if coverage is not None else None,
        "warning": warning,
        # Korea missing from a *complete* list means it genuinely sold nothing.
        # Korea missing from a *truncated* list means we do not know — and 0.0
        # would hand that country a perfect headroom score, making a data gap
        # look like an open market.
        "korea_share_pct": (kr["share_pct"] if kr
                            else (0.0 if (coverage is None or coverage >= 0.99) else None)),
        "korea_rank": suppliers.index(kr) + 1 if kr else None,
        "korea_value_per_partner": kr["value_usd"] if kr else None,
        "top_supplier": (top or {}).get("supplier"),
        "top_supplier_share_pct": top_share,
        "dominated": bool(top_share and top_share >= 60
                          and (top or {}).get("supplier_code") != KOREA),
        "suppliers": suppliers[:15],
    }


def collect_market_growth(hs: str, area: dict, years: list[int], log) -> dict:
    """The importer's own total imports per year — i.e. how fast the *market*
    is growing, as opposed to how fast Korea's sales into it are growing.

    The growth axis previously used Korea's export CAGR, which meant a shrinking
    market where Korea happened to rebound off a low base scored a perfect 1.0.
    That is what put Hong Kong ahead of the United States on HS8507.

    Costs one call per year per country, minus the latest year already fetched
    by collect_competitors (and served from cache either way).
    """
    def total_for(y: int) -> float | None:
        rows = ct.fetch(freq="A", period=y, reporter=area["code"],
                        partner=ct.WORLD, hs=hs, flow="M")
        row = rows[0] if rows else None
        # A summed World row is roughly double the truth; using it at one end of
        # a CAGR would invent growth or collapse it.
        if row and not row.get("is_partial_sum") and (row.get("value_usd") or 0) > 0:
            return row["value_usd"]
        return None

    totals: dict[int, float] = {}
    for y in years:
        value = total_for(y)
        if value is not None:
            totals[y] = value

    # Reporting lag differs per country: Vietnam's latest mirror year for some
    # codes is two years behind the window we asked for, which would leave a
    # single data point and drop Korea's third-largest partner from the ranking
    # entirely. Reach back a little further before giving up.
    probe = min(years) - 1
    while len(totals) < 2 and probe >= min(years) - 3:
        value = total_for(probe)
        if value is not None:
            totals[probe] = value
        probe -= 1

    if len(totals) < 2:
        return {"available": False, "totals": totals,
                "reason": f"{area['name']}의 연도별 총수입이 2개 연도 미만이라 "
                          f"시장 성장률을 낼 수 없습니다."}

    ordered = sorted(totals)
    first, last = ordered[0], ordered[-1]
    return {
        "available": True,
        "totals": totals,
        "from_year": first,
        "to_year": last,
        "cagr": cagr(totals[first], totals[last], last - first),
    }


def _month_back(y: int, m: int, n: int) -> tuple[int, int]:
    total = y * 12 + (m - 1) - n
    return total // 12, total % 12 + 1


def latest_month_with_data(hs: str, area: dict, log) -> str | None:
    """Monthly reporting lags 2–6 months, and the lag differs per partner.

    Probing for the real edge beats padding a fixed buffer: without it a
    24-month request lands on ~21 months of data and YoY never computes.
    """
    today = date.today()
    for back in range(1, 13):
        y, m = _month_back(today.year, today.month, back)
        p = f"{y}{m:02d}"
        rows = ct.fetch(freq="M", period=p, reporter=KOREA, partner=area["code"],
                        hs=hs, flow="X")
        if rows and (rows[0].get("value_usd") or 0) > 0:
            if back > 1:
                log(f"  {area['name']} 월별 최신: {p} (보고 지연 {back - 1}개월)")
            return p
    return None


def collect_monthly(hs: str, area: dict, n_months: int, log) -> tuple[list[dict], dict]:
    edge = latest_month_with_data(hs, area, log)
    if edge is None:
        return [], {"available": False,
                    "reason": f"{area['name']} 월별 데이터가 최근 12개월 내 없습니다."}

    ey, em = int(edge[:4]), int(edge[4:])
    seq = sorted(f"{y}{m:02d}" for y, m in
                 (_month_back(ey, em, back) for back in range(n_months)))

    rows = []
    for i, p in enumerate(seq, 1):
        log(f"  월별 {area['name']} {i}/{len(seq)} {p}")
        rows.extend(ct.fetch(freq="M", period=p, reporter=KOREA,
                             partner=area["code"], hs=hs, flow="X"))
    rows.sort(key=lambda r: r["period"])
    have = [r for r in rows if r["value_usd"]]
    return rows, {
        "available": bool(have),
        "requested_months": n_months,
        "months_with_data": len(have),
        "range": f"{have[0]['period']}–{have[-1]['period']}" if have else None,
        "latest_reported": edge,
    }


# --------------------------------------------------------------------------
# scoring
# --------------------------------------------------------------------------


def score_markets(entries: list[dict]) -> None:
    """시장 매력도 = 규모 × 성장률 × 한국 점유율 여유 (0-100).

    가중치는 규모 40 / 성장 35 / 여유 25. 이 배분은 정답이 아니라 기본값이며
    리포트에 그대로 노출한다. 각 축은 이번 조회에 포함된 국가들 사이의
    상대 순위이므로, 비교군이 바뀌면 점수도 바뀐다.
    """
    # A score averaged over "whichever axes we happened to measure" is not
    # comparable to one averaged over all three. Libya, measured on growth
    # alone, took first place over real markets that way. Only countries with
    # the market-size anchor get ranked; the rest are reported separately.
    for e in entries:
        if e.get("size_usd") is None:
            e["attractiveness_score"] = None
            e["score_basis"] = "unscored"
            e["score_note"] = ("시장 규모를 확인할 수 없어(미러 데이터 없음) 순위에서 제외했습니다. "
                               "한국 수출 실적만 따로 확인하세요.")
    scorable = [e for e in entries if e.get("size_usd") is not None]
    if not scorable:
        return

    # Each axis is min-max normalized across the countries in this run, so with
    # one country every axis collapses to 0.5 and the score is always 50.0 — a
    # confident-looking number carrying no information. With two it is always
    # 0 vs 100. Refuse to emit a score that cannot mean anything.
    if len(scorable) < 2:
        for e in scorable:
            e["attractiveness_score"] = None
            e["score_basis"] = "n/a"
            e["score_note"] = ("비교 가능한 국가가 1개뿐이라 매력도 점수를 계산하지 않습니다. "
                               "점수는 국가 간 상대 순위입니다 — 여러 국가를 함께 조회하세요.")
        return

    entries = scorable

    def norm(vals: list[float | None]) -> list[float | None]:
        real = [v for v in vals if v is not None]
        if not real:
            return [None] * len(vals)
        lo, hi = min(real), max(real)
        if math.isclose(lo, hi):
            return [0.5 if v is not None else None for v in vals]
        return [None if v is None else (v - lo) / (hi - lo) for v in vals]

    sizes = norm([math.log10(e["size_usd"]) if (e.get("size_usd") or 0) > 0 else None
                  for e in entries])
    growths = norm([e.get("growth_cagr") for e in entries])
    headrooms = [None if e.get("korea_share_pct") is None
                 else max(0.0, 1 - (e["korea_share_pct"] or 0) / 100) for e in entries]

    # Renormalizing over "whichever axes exist" rewards missing data: India
    # scored 49.7 (5th) with a -29.3% CAGR and 68.9 (3rd) with that CAGR simply
    # absent. A bad value is penalized, a missing one is not. Any entry short of
    # all three axes is therefore unscored — same rule already applied to size.
    for e, s, g, h in zip(entries, sizes, growths, headrooms):
        e["score_components"] = {"size": s, "growth": g, "headroom": h,
                                 "weights": {"size": 0.40, "growth": 0.35, "headroom": 0.25}}
        missing = [label for label, val in (("성장률", g), ("점유율", h)) if val is None]
        if s is None or missing:
            e["attractiveness_score"] = None
            e["score_basis"] = "unscored"
            e["score_note"] = (f"{', '.join(missing) or '시장 규모'} 데이터가 없어 순위에서 "
                               f"제외했습니다. 결측 축을 빼고 계산하면 데이터가 부족한 국가가 "
                               f"오히려 높은 점수를 받습니다.")
            continue
        score = 100 * (s * 0.40 + g * 0.35 + h * 0.25)
        e["attractiveness_score"] = round(score, 1)
        e["score_basis"] = "full"

    scored = [e for e in entries if e.get("attractiveness_score") is not None]

    # Nominal weights are not realized influence. An axis whose values barely
    # differ across this comparison set moves the ranking hardly at all, however
    # heavily it is weighted: with Korea's share at 1–15% everywhere, headroom
    # spanned 0.853–0.986 and drove 5.9% of the spread, not the nominal 25%.
    # Publishing the nominal split alone overstates what it did.
    if len(scored) >= 2:
        influence, total = {}, 0.0
        for axis, weight in (("size", 0.40), ("growth", 0.35), ("headroom", 0.25)):
            spread = statistics.pstdev([e["score_components"][axis] for e in scored])
            influence[axis] = weight * spread
            total += influence[axis]
        for e in scored:
            e["score_components"]["realized_influence"] = (
                {a: round(v / total, 3) for a, v in influence.items()} if total else None)

    notes = []
    if len(scored) < 4:
        notes.append(f"비교 대상이 {len(scored)}개국뿐이라 점수가 0–100 전 구간에 강제로 "
                     f"펼쳐집니다. 점수 차이를 크게 읽지 마세요.")
    notes.append("각 축은 이번 조회에 포함된 국가들 사이의 상대값이라, 관계없는 국가를 "
                 "하나 넣고 빼는 것만으로 점수뿐 아니라 **순위 자체가 뒤집힐 수 있습니다.** "
                 "비교군을 바꿔 두세 번 돌려보고 순위가 유지되는 국가를 신뢰하세요.")
    for e in scored:
        e["score_note"] = " ".join(notes)


# --------------------------------------------------------------------------
# output
# --------------------------------------------------------------------------


def write_csv(path: Path, rows: list[dict], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=columns, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def fmt_usd(v) -> str:
    if v is None:
        return "-"
    for unit, div in (("억", 1e8), ("백만", 1e6), ("천", 1e3)):
        if abs(v) >= div:
            return f"${v / div:,.1f}{unit}"
    return f"${v:,.0f}"


def fmt_pct(v, digits=1) -> str:
    return "-" if v is None else f"{v * 100:+.{digits}f}%"


def fmt_num(v, digits=0) -> str:
    return "-" if v is None else f"{v:,.{digits}f}"


def build_report(ctx: dict) -> str:
    hs, desc = ctx["hs"], ctx["hs_desc"] or ""
    L = [f"# HS {hs} 시장 스캔", "",
         f"- 품목: {desc}",
         "- 기준 데이터: UN Comtrade (한국 신고 기준 수출 / 상대국 신고 기준 수입 미러)",
         f"- 대상 연도: {ctx['years'][0]}–{ctx['years'][-1]}",
         f"- 대상국 선정: {ctx['target_basis']}",
         f"- 생성일: {ctx['generated_at']}", ""]

    scored = [e for e in ctx["entries"] if e.get("attractiveness_score") is not None]
    unscored = [e for e in ctx["entries"] if e.get("attractiveness_score") is None]
    ranked = sorted(scored, key=lambda x: x["attractiveness_score"], reverse=True)
    ranked += sorted(unscored, key=lambda x: x.get("kr_export_usd") or 0, reverse=True)

    L += ["## 1. 시장 우선순위", "",
          "| # | 국가 | 매력도 | 현지 총수입 | **시장 CAGR** | 한국 수출액 | 한국 수출 CAGR | 한국 점유율 | 1위 공급국 |",
          "|---|---|---|---|---|---|---|---|---|"]
    for i, e in enumerate(ranked, 1):
        if e["attractiveness_score"] is None:
            score, rank_label = "순위제외", "–"
        else:
            score = f"**{e['attractiveness_score']}**"
            if e.get("score_basis", "").startswith("partial"):
                score += "*"
            rank_label = str(i)
        share = e.get("korea_share_pct")
        share_s = "-" if share is None else f"{share:.1f}%"
        top = e.get("top_supplier")
        top_s = ("-" if not top else
                 f"{top} {e['top_supplier_share_pct']:.0f}%"
                 + (" ⚠️" if e.get("dominated") else ""))
        L.append(
            f"| {rank_label} | {e['name']} | {score} | {fmt_usd(e.get('market_size_usd'))} | "
            f"**{fmt_pct(e.get('market_cagr'))}** | {fmt_usd(e.get('kr_export_usd'))} | "
            f"{fmt_pct(e.get('kr_export_cagr'))} | {share_s} | {top_s} |")
    note = next((e.get("score_note") for e in ranked if e.get("score_note")), None)
    if note:
        L += ["", f"> ⚠️ {note}"]
    L += ["", "`순위제외` = 세 축(규모·성장률·점유율) 중 하나라도 측정되지 않은 국가. "
          "시장이 나쁘다는 뜻이 아니라 **비교할 수 없다**는 뜻이다.",
          "점수 = 시장규모 40% + **시장 CAGR** 35% + 점유율 여유 25%.",
          "성장 축은 **그 나라의 총수입 성장률**이다(한국 수출 성장률이 아니다). "
          "두 열을 나란히 두었으니 같이 읽을 것 — 시장은 크는데 한국 수출만 줄고 있다면 "
          "점유율을 잃고 있다는 뜻이고, 반대면 시장이 죽는데 우리만 버티는 것이다."]

    infl = next((e["score_components"].get("realized_influence") for e in scored
                 if e.get("score_components", {}).get("realized_influence")), None)
    if infl:
        # The nominal split describes intent; this describes what actually moved
        # the ranking. They diverge whenever an axis is near-constant here.
        L.append(f"다만 **이번 조회에서 실제로 순위를 움직인 비중은 "
                 f"규모 {infl['size']:.0%} · 성장률 {infl['growth']:.0%} · "
                 f"점유율 여유 {infl['headroom']:.0%}** 였다. "
                 f"국가 간 차이가 거의 없는 축은 가중치가 높아도 순위를 바꾸지 못한다.")

    L += ["각 축은 **이번 조회에 포함된 국가들 사이의 상대값**(0–1)이다. "
          "관계없는 국가를 하나 넣고 빼는 것만으로 점수뿐 아니라 **순위 자체가 뒤집힐 수 있다.** "
          "비교군을 바꿔 두세 번 돌려보고 순위가 유지되는 국가를 신뢰할 것.",
          "⚠️ = 1위 공급국이 60% 이상을 쥔 과점 시장. **점유율 여유 점수가 가장 오해를 부르는 곳이다** — "
          "한국 점유율이 낮아 '여유'로 잡히지만 그 자리는 이미 남이 차지하고 있다. "
          "빈 시장이 아니라 진입장벽이 높은 시장으로 읽어야 한다.",
          "점유율 여유는 '아직 안 뚫린 몫'이라는 뜻이지 '뚫기 쉽다'는 뜻이 아니다. "
          "한국 점유율이 이미 높은 시장은 여유 점수는 낮지만 제품 적합성은 이미 입증된 시장이다.",
          "홍콩·싱가포르·네덜란드·UAE처럼 중계무역 비중이 큰 나라는 수입액에 재수출분이 섞여 "
          "실제 소비 시장보다 크게 잡힌다. 상위권에 오르면 최종 소비지인지 따로 확인할 것.", ""]

    L += ["## 2. 국가별 상세", ""]
    for e in ranked:
        suffix = " *(순위 제외)*" if e["attractiveness_score"] is None else ""
        L += [f"### {e['name']}{suffix}", ""]
        if e.get("score_note") and e["attractiveness_score"] is None:
            L += [f"> {e['score_note']}", ""]
        series = e.get("annual_series") or []
        if series:
            L += ["| 연도 | 한국 수출액 | 중량(kg) | 단가($/kg) |", "|---|---|---|---|"]
            for s in series:
                L.append(f"| {s['year']} | {fmt_usd(s['value_usd'])} | "
                         f"{fmt_num(s['weight_kg'])} | {fmt_num(s['unit_price'], 2)} |")
            L.append("")
        if e.get("price_trend"):
            L.append(f"- 단가 추세: {e['price_trend']}")
        if e.get("mirror_gap_note"):
            L += [f"> ⚠️ **미러 불일치** — {e['mirror_gap_note']}", ""]
        cov = e.get("monthly_coverage") or {}
        if cov.get("available"):
            L.append(f"- 월별 데이터 범위: {cov['range']} ({cov['months_with_data']}개월)")
        elif cov.get("reason"):
            L.append(f"- 월별 데이터: {cov['reason']}")
        if e.get("yoy_12m") is not None:
            L.append(f"- 최근 12개월 YoY: {fmt_pct(e['yoy_12m'])}")
        elif e.get("yoy_note"):
            L.append(f"- 최근 12개월 YoY: {e['yoy_note']}")
        if e.get("seasonality_note"):
            L.append(f"- 계절성: {e['seasonality_note']}")

        comp = e.get("competitors") or {}
        if comp.get("available"):
            stale = " (요청 연도 데이터가 없어 대체 연도)" if comp.get("stale") else ""
            L += ["",
                  f"**{comp['year']}년 공급국 점유율** — 총수입 {fmt_usd(comp['total_imports_usd'])}{stale}",
                  ""]
            if comp.get("warning"):
                L += [f"> ⚠️ {comp['warning']}", ""]
            L += ["| 순위 | 공급국 | 점유율 | 금액 | 단가($/kg) |",
                  "|---|---|---|---|---|"]
            for j, s in enumerate(comp["suppliers"][:10], 1):
                name = f"**{s['supplier']}** ◀" if s["supplier_code"] == KOREA else s["supplier"]
                L.append(f"| {j} | {name} | {s['share_pct']}% | "
                         f"{fmt_usd(s['value_usd'])} | "
                         f"{fmt_num(s['unit_price_usd_per_kg'], 2)} |")
        else:
            L += ["", f"- 경쟁국 점유율: 조회 불가 — {comp.get('reason', '사유 미상')}"]
        L.append("")

    L += ["## 3. 데이터 한계", "",
          "- **점유율은 '수입 중 점유율'이지 '시장 점유율'이 아니다.** 이 표의 총수입과 공급국 "
          "점유율은 전부 수입 통계 기준이라 **현지 제조사가 빠져 있다.** 예를 들어 "
          "'베트남 라면 한국 점유율 53%'는 수입되는 라면 중 53%라는 뜻이고, 현지 업체가 "
          "가져가는 내수는 잡히지 않는다. 식품·자동차·철강·화장품처럼 현지 생산이 강한 "
          "시장에서는 실제 시장 지위가 이 숫자보다 훨씬 낮을 수 있다. "
          "같은 이유로 '현지 총수입'은 그 나라의 시장 규모가 아니다.",
          "- UN Comtrade는 **HS 6단위까지**만 제공한다. HS 10단위는 관세청 오픈API가 필요하다.",
          "- 상대국 신고 수입액은 CIF, 한국 신고 수출액은 FOB 기준이라 같은 거래도 금액이 다르게 잡힌다.",
          "- 미러 데이터는 보고국만 나온다. 미보고국(다수 개도국)은 경쟁국 점유율이 비어 있다.",
          "- **기업 단위 데이터는 여기에 없다.** 한국은 관세법상 신고정보가 비밀유지 대상이라 "
          "기업명×품목×금액이 공개되지 않는다. 바이어 실명은 B/L 공개국(미국·인도 등) 유료 데이터가 필요하다.",
          "- 최신 월 데이터는 보고 지연으로 2~6개월 비어 있을 수 있다.", ""]
    return "\n".join(L)


# --------------------------------------------------------------------------
# main command
# --------------------------------------------------------------------------


def cmd_market(a) -> int:
    quiet = a.quiet
    def log(msg: str) -> None:
        if not quiet:
            print(msg, file=sys.stderr)

    hs = ct.validate_hs(a.hs)
    desc = ct.hs_desc(hs)
    log(f"HS {hs} — {desc}")

    latest = int(a.latest_year) if a.latest_year else latest_available_year(hs, log)
    years = list(range(latest - a.years + 1, latest + 1))
    log(f"대상 연도: {years}")

    rankings = collect_rankings(hs, years, log)
    latest_rank = rankings[latest]

    if a.countries:
        targets = [ct.resolve_area(c.strip()) for c in a.countries.split(",") if c.strip()]
        target_basis = "사용자 지정"
    elif a.preset == "hs-top":
        top = sorted(latest_rank.values(), key=lambda r: r["value_usd"] or 0, reverse=True)
        targets = [ct.resolve_area(r["partner_code"]) for r in top[:a.top]]
        target_basis = f"이 HS코드의 한국 수출액 상위 {a.top}개국"
    else:
        meta = ct.top_partners_meta()
        targets = [ct.resolve_area(p["code"]) for p in ct.top_partners(a.top)]
        target_basis = (f"한국 전체 교역 상위 {a.top}개국 "
                        f"({meta.get('year')}년 총수출 기준 스냅샷)")
    log(f"대상국({target_basis}): " + ", ".join(t["name"] for t in targets))

    entries = []
    for area in targets:
        code = area["code"]
        series = []
        for y in years:
            r = rankings[y].get(code)
            v = r["value_usd"] if r else None
            w = r["net_weight_kg"] if r else None
            series.append({"year": y, "value_usd": v, "weight_kg": w,
                           "unit_price": unit_price(v, w)})

        first, last = series[0]["value_usd"], series[-1]["value_usd"]
        prices = [s["unit_price"] for s in series if s["unit_price"]]
        trend = None
        if len(prices) >= 2 and prices[0] > 0:
            chg = prices[-1] / prices[0] - 1
            # 금액÷중량의 변화는 가격 변동과 품목 믹스 변동의 합이고, HS 6단위가
            # 끝인 이상 둘을 분해할 수 없다. HS4 8507 하나에 납축전지(~$2/kg)와
            # 리튬이온(~$30/kg)이 같이 들어 있어, 믹스가 조금만 움직여도 '단가'가
            # 크게 뛴다. '프리미엄화'로 읽으면 대부분 오독이다.
            mix_caveat = "" if len(hs) == 6 else " ※ HS 6단위가 아니라 품목 믹스 변동일 가능성이 큼"
            if chg > 0.10:
                trend = f"{chg * 100:+.0f}% (원인 미분해: 가격 상승 또는 고단가 품목 비중 증가){mix_caveat}"
            elif chg < -0.10:
                trend = f"{chg * 100:+.0f}% (원인 미분해: 가격 하락 또는 저단가 품목 비중 증가){mix_caveat}"
            else:
                trend = f"{chg * 100:+.0f}% 보합"

        if a.no_competitors:
            comp = {"available": False, "reason": "--no-competitors 로 생략"}
        else:
            # One country's mirror lookup failing must not discard the work
            # already done for the others — degrade this row, keep the report.
            try:
                comp = collect_competitors(hs, area, latest, log)
            except ct.ComtradeError as exc:
                log(f"  ! {area['name']} 경쟁국 조회 실패: {exc}")
                comp = {"available": False, "reason": f"조회 실패: {exc}"}

        growth = ({"available": False, "reason": "--no-competitors 로 생략"}
                  if a.no_competitors or not comp.get("available")
                  else collect_market_growth(hs, area, years, log))

        entry = {
            "code": code, "name": area["name"], "iso2": area.get("iso2"),
            "annual_series": series,
            "kr_export_usd": last,
            "kr_export_cagr": cagr(first, last, len(years) - 1),
            "unit_price": series[-1]["unit_price"],
            "price_trend": trend,
            "competitors": comp,
            "market_size_usd": comp.get("total_imports_usd") if comp.get("available") else None,
            "korea_share_pct": comp.get("korea_share_pct") if comp.get("available") else None,
            "korea_rank": comp.get("korea_rank") if comp.get("available") else None,
            "top_supplier": comp.get("top_supplier"),
            "top_supplier_share_pct": comp.get("top_supplier_share_pct"),
            "dominated": comp.get("dominated", False),
            "market_cagr": growth.get("cagr") if growth.get("available") else None,
            "market_growth_span": (f"{growth['from_year']}–{growth['to_year']}"
                                   if growth.get("available") else None),
            "market_growth_note": None if growth.get("available") else growth.get("reason"),
        }
        # The size axis is the importer's total imports and nothing else.
        # Substituting Korea's export value when the mirror is missing mixes two
        # quantities that differ by ~10x, and the country with no mirror lands at
        # the bottom of a normalized axis regardless of how big it actually is —
        # the USA outranks Japan in Korean exports yet scored 0.0 that way.
        # Leaving it None costs that country one axis and says so, which is the
        # honest version.
        # Both sides of the same trade are already in hand, so comparing them is
        # free. They should differ by the FOB/CIF margin — roughly 5-15%. When
        # they differ by a multiple, something else is going on: re-export
        # through a third country, under-declaration at the border, or a
        # reporter whose statistics simply miss volume. Kyrgyzstan showed a 9x
        # gap on HS3304, which made its market look flat (+0.2% CAGR) when the
        # likelier story is that its statistics do not capture the inflow.
        # Presenting that as a stagnant market is exactly the silent wrong
        # answer this report keeps trying not to give.
        if comp.get("available") and comp.get("korea_value_per_partner"):
            kr_same_year = rankings.get(comp["year"], {}).get(code, {}).get("value_usd")
            partner_side = comp["korea_value_per_partner"]
            if kr_same_year and partner_side > 0:
                ratio = kr_same_year / partner_side
                entry["mirror_ratio"] = round(ratio, 1)
                entry["mirror_year"] = comp["year"]
                if ratio >= 2 or ratio <= 0.5:
                    entry["mirror_gap_note"] = (
                        f"{comp['year']}년 한국 신고 수출 {fmt_usd(kr_same_year)} vs "
                        f"{area['name']} 신고 대한국 수입 {fmt_usd(partner_side)} — "
                        f"{ratio:.1f}배 차이. FOB/CIF로는 설명되지 않는 크기다. "
                        f"제3국 경유 재수출, 통관 신고 축소, 또는 상대국 통계 커버리지 부족일 수 "
                        f"있다. 이 나라의 시장 규모·성장률·점유율은 과소집계일 가능성이 크다.")

        entry["size_usd"] = entry["market_size_usd"]
        # The market's growth, not Korea's. Korea's own CAGR stays in the table
        # as a separate column — it answers "how are we doing", which is a
        # different question from "is this market worth entering".
        entry["growth_cagr"] = entry["market_cagr"]
        entries.append(entry)

    if a.monthly:
        for e in entries:
            area = ct.resolve_area(e["code"])
            try:
                rows, coverage = collect_monthly(hs, area, a.monthly, log)
            except ct.ComtradeError as exc:
                log(f"  ! {area['name']} 월별 조회 실패: {exc}")
                rows, coverage = [], {"available": False, "reason": f"조회 실패: {exc}"}
            e["monthly"] = rows
            e["monthly_coverage"] = coverage
            vals = [(r["period"], r["value_usd"] or 0) for r in rows if r["value_usd"]]

            if len(vals) >= 24:
                recent = sum(v for _, v in vals[-12:])
                prior = sum(v for _, v in vals[-24:-12])
                e["yoy_12m"] = (recent / prior - 1) if prior else None
            elif coverage.get("available"):
                e["yoy_note"] = (f"YoY는 24개월이 필요한데 {len(vals)}개월만 있습니다"
                                 f"(--monthly {max(24, a.monthly)} 로 재조회).")

            # Averaging calendar months needs ≥2 observations each, otherwise
            # months sampled once dominate and the "성수기" is an artifact.
            by_month: dict[str, list[float]] = {}
            for p, v in vals:
                by_month.setdefault(p[4:6], []).append(v)
            if len(by_month) == 12 and all(len(v) >= 2 for v in by_month.values()):
                avg = {m: statistics.mean(vs) for m, vs in by_month.items()}
                overall = statistics.mean(avg.values())
                if overall > 0:
                    hi = sorted(avg, key=lambda m: avg[m], reverse=True)[:3]
                    lo = sorted(avg, key=lambda m: avg[m])[:3]
                    spread = (max(avg.values()) - min(avg.values())) / overall
                    e["seasonality_note"] = (
                        f"성수기 {', '.join(f'{int(m)}월' for m in sorted(hi))} / "
                        f"비수기 {', '.join(f'{int(m)}월' for m in sorted(lo))} "
                        f"(진폭 {spread * 100:.0f}%)"
                        + ("" if spread > 0.4 else " — 진폭이 작아 계절성은 약함"))
            elif coverage.get("available"):
                e["seasonality_note"] = (
                    f"계절성은 각 월 2회 이상 관측이 필요합니다. 현재 {len(vals)}개월"
                    f"({coverage.get('range')}) — --monthly 24 이상으로 재조회하세요.")

    score_markets(entries)

    outdir = Path(a.outdir).expanduser().resolve()
    outdir.mkdir(parents=True, exist_ok=True)

    write_csv(outdir / f"hs{hs}_markets.csv",
              [{"country": e["name"], "iso2": e["iso2"], "score": e["attractiveness_score"],
                "score_basis": e["score_basis"],
                "kr_export_usd_latest": e["kr_export_usd"], "kr_export_cagr": e["kr_export_cagr"],
                "market_cagr": e.get("market_cagr"),
                "market_size_usd": e["market_size_usd"], "korea_share_pct": e["korea_share_pct"],
                "korea_rank": e["korea_rank"], "unit_price_usd_per_kg": e["unit_price"]}
               for e in (sorted([x for x in entries if x["attractiveness_score"] is not None],
                                key=lambda x: x["attractiveness_score"], reverse=True)
                         + sorted([x for x in entries if x["attractiveness_score"] is None],
                                  key=lambda x: x.get("kr_export_usd") or 0, reverse=True))],
              ["country", "iso2", "score", "score_basis", "kr_export_usd_latest",
               "kr_export_cagr", "market_cagr", "market_size_usd", "korea_share_pct", "korea_rank",
               "unit_price_usd_per_kg"])

    write_csv(outdir / f"hs{hs}_annual_series.csv",
              [{"country": e["name"], **s} for e in entries for s in e["annual_series"]],
              ["country", "year", "value_usd", "weight_kg", "unit_price"])

    comp_rows = [{"importer": e["name"], "year": e["competitors"].get("year"), **s}
                 for e in entries if e["competitors"].get("available")
                 for s in e["competitors"]["suppliers"]]
    if comp_rows:
        write_csv(outdir / f"hs{hs}_competitors.csv", comp_rows,
                  ["importer", "year", "supplier", "supplier_code", "value_usd",
                   "share_pct", "unit_price_usd_per_kg"])

    if a.monthly:
        write_csv(outdir / f"hs{hs}_monthly.csv",
                  [{"country": e["name"], **r} for e in entries for r in e.get("monthly", [])],
                  ["country", "period", "value_usd", "net_weight_kg", "qty", "qty_unit"])

    ctx = {"hs": hs, "hs_desc": desc, "years": years, "entries": entries,
           "target_basis": target_basis, "generated_at": date.today().isoformat()}
    report_path = outdir / f"hs{hs}_report.md"
    report_path.write_text(build_report(ctx), encoding="utf-8")

    summary = {
        "hs": hs, "hs_desc": desc, "years": years, "outdir": str(outdir),
        "target_basis": target_basis, "report": str(report_path),
        "files": sorted(p.name for p in outdir.glob(f"hs{hs}_*")),
        "ranking": [{"country": e["name"], "score": e["attractiveness_score"],
                     "score_basis": e["score_basis"],
                     "score_note": e.get("score_note"),
                     "kr_export_usd": e["kr_export_usd"], "kr_export_cagr": e["kr_export_cagr"],
                     "market_cagr": e.get("market_cagr"),
                     "mirror_ratio": e.get("mirror_ratio"),
                     "mirror_gap_note": e.get("mirror_gap_note"),
                     "market_growth_span": e.get("market_growth_span"),
                     "market_growth_note": e.get("market_growth_note"),
                     "market_size_usd": e["market_size_usd"],
                     "korea_share_pct": e["korea_share_pct"], "korea_rank": e["korea_rank"],
                     "top_supplier": e.get("top_supplier"),
                     "top_supplier_share_pct": e.get("top_supplier_share_pct"),
                     "dominated": e.get("dominated", False),
                     "unit_price": e["unit_price"], "price_trend": e["price_trend"],
                     "yoy_12m": e.get("yoy_12m"), "yoy_note": e.get("yoy_note"),
                     "seasonality": e.get("seasonality_note"),
                     "monthly_coverage": e.get("monthly_coverage"),
                     "top_competitors": [
                         {"supplier": s["supplier"], "share_pct": s["share_pct"]}
                         for s in (e["competitors"].get("suppliers") or [])[:5]
                     ] if e["competitors"].get("available") else None,
                     "competitor_warning": e["competitors"].get("warning"),
                     "partner_coverage_pct": e["competitors"].get("partner_coverage_pct"),
                     "competitor_note": None if e["competitors"].get("available")
                     else e["competitors"].get("reason")}
                    for e in (sorted([x for x in entries if x["attractiveness_score"] is not None],
                                     key=lambda x: x["attractiveness_score"], reverse=True)
                              + sorted([x for x in entries if x["attractiveness_score"] is None],
                                       key=lambda x: x.get("kr_export_usd") or 0, reverse=True))],
    }
    json.dump(summary, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("market", help="HS코드 시장 우선순위 리포트")
    s.add_argument("--hs", required=True, help="HS 2/4/6 단위")
    s.add_argument("--countries", help="쉼표 구분(KZ,UZ 또는 카자흐스탄,우즈베키스탄). 생략 시 --preset 사용")
    s.add_argument("--preset", default="kr-top", choices=["kr-top", "hs-top"],
                   help="kr-top=한국 전체 교역 상위국(기본) / hs-top=이 HS의 한국 수출 상위국")
    s.add_argument("--top", type=int, default=10, help="--countries 생략 시 대상국 수 (기본 10)")
    s.add_argument("--years", type=int, default=3)
    s.add_argument("--latest-year", help="최신 연도 자동탐지 대신 고정")
    s.add_argument("--monthly", type=int, metavar="N",
                   help="최근 N개월 월별 시계열도 수집 (국가당 N콜, ~2초/콜)")
    s.add_argument("--no-competitors", action="store_true")
    s.add_argument("--outdir", default="./trade-stats-out")
    s.add_argument("--quiet", action="store_true")
    s.set_defaults(fn=cmd_market)

    a = p.parse_args()
    try:
        return a.fn(a)
    except ct.ComtradeError as exc:
        json.dump({"error": "comtrade_error", "message": str(exc)},
                  sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
