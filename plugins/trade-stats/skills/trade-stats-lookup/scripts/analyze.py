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
import re
import statistics
import sys
from datetime import date
from pathlib import Path

import comtrade as ct
import customs as kcs

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


# 여유 시장(untapped) 축의 절대 기준선. 달러 절대액이라 비교군이 바뀌어도 이 축의
# 점수는 흔들리지 않는다 — 이번 조회에 따라 달라지는 것은 성장률 축뿐이다.
#
# 상한을 두는 것이 이 축의 핵심이다. 규모를 log 최소-최대로 정규화하면 규모가 순위를
# 지배한다: 실측 HS3304 10개국에서 옛 3축 점수는 시장 규모 순위와 Spearman +0.891
# 이었다. 4분을 기다려 "수입액 큰 나라 순"을 다시 받는 셈이고, 그건 해외영업 담당자가
# 이미 아는 정보다. 상한($10억)을 넘는 시장은 전부 만점으로 묶어 "충분히 크다" 이상의
# 구분을 하지 않는다 — 중소 수출기업 입장에서 $75억 시장과 $130억 시장의 차이는
# 어느 쪽을 먼저 갈지를 바꾸지 않는다. 하한($1천만) 밑은 순위에서 뺀다.
UNTAPPED_FLOOR = 10_000_000
# 상한을 $10억으로 두면 실측 10개국 중 6개국이 만점에 몰려 여유 축이 순위를 못 가르고
# 점수가 사실상 성장률 하나가 된다(그때 Spearman(점수,성장률) = +0.94). 하한에서 세
# 자릿수 위인 $100억으로 올리면 여유 축이 0.42~1.0으로 펴지면서 두 축이 실제로 같이
# 작동한다 — 그러면서도 규모 순위와의 상관은 +0.07에 머문다.
UNTAPPED_CEIL = 10_000_000_000

# 성장 축도 절대 기준이다. 연 -10% 이하면 0점, +20% 이상이면 만점.
# 이전에는 이 축을 "이번 조회에 포함된 국가들" 사이의 최소-최대로 폈는데, 그러면
# 무관한 국가 하나가 비교군에 들어오고 나가는 것만으로 점수가 바뀐다 — 실측 결과
# 성장률 최저국(인도)을 빼자 다른 나라 점수가 최대 17.9pt 움직였고 1위가 7.1%
# 확률로 바뀌었다. 두 축을 모두 절대화하면 그 의존성이 정의상 0이 되고, 덤으로
# 점수가 조회 간에 비교 가능해진다("이 시장 78점"이 언제나 같은 뜻이 된다).
GROWTH_FLOOR = -0.10
GROWTH_CEIL = 0.20

SCORE_WEIGHTS = {"untapped": 0.5, "growth": 0.5}


def untapped_usd(entry: dict) -> float | None:
    """아직 한국 몫이 아닌 수입액 = 그 나라 총수입 × (1 − 한국 점유율).

    규모와 점유율 여유를 곱으로 합친 값이다. 옛 점수는 둘을 따로 더해서, 규모가 큰
    시장과 여유가 큰 시장이 서로 상쇄됐다. 실무 질문은 "시장이 큰가"도 "여유가 있나"도
    아니고 **"아직 테이블에 남아 있는 돈이 얼마인가"** 하나다.

    같은 미러(CIF) 통계 안에서만 계산하므로 FOB/CIF를 섞지 않는다.
    """
    size = entry.get("size_usd")
    share = entry.get("korea_share_pct")
    if size is None or share is None or size <= 0:
        return None
    return size * max(0.0, 1 - share / 100)


def _log_saturating(v: float | None, floor: float, ceil: float) -> float | None:
    """하한 밑은 0, 상한 위는 1, 사이는 로그로 편다.

    상한을 두는 것이 이 축의 핵심이다. 규모를 로그 최소-최대로 정규화하면 규모가 순위를
    지배한다: 실측 HS3304 10개국에서 옛 3축 점수는 시장 규모 순위와 Spearman +0.891
    이었다. 4분을 기다려 "수입액 큰 나라 순"을 다시 받는 셈이고, 그건 해외영업 담당자가
    이미 아는 정보다. 상한 위 시장을 전부 만점으로 묶으면 "충분히 크다" 이상의 구분을
    하지 않게 된다 — 중소 수출기업에게 $75억 시장과 $130억 시장의 차이는 어느 쪽을
    먼저 갈지를 바꾸지 않는다.
    """
    if v is None or v <= 0:
        return None
    if v <= floor:
        return 0.0
    if v >= ceil:
        return 1.0
    return math.log10(v / floor) / math.log10(ceil / floor)


def _clamped(v: float | None, floor: float, ceil: float) -> float | None:
    if v is None:
        return None
    return min(1.0, max(0.0, (v - floor) / (ceil - floor)))


def score_markets(entries: list[dict], floor: float = UNTAPPED_FLOOR,
                  ceil: float = UNTAPPED_CEIL) -> None:
    """시장 매력도 = 여유 시장 50% + 시장 성장률 50% (0-100).

    - 여유 시장: 그 나라 총수입 × (1 − 한국 점유율). 달러 절대액을 하한~상한 사이에서
      로그로 편다.
    - 성장률: 그 나라 총수입의 CAGR(한국 수출 성장률이 아니다). -10%~+20% 사이로 편다.

    **두 축 모두 절대 기준이라 어떤 나라를 함께 조회하든 점수가 달라지지 않는다.**
    조회 간 비교도 가능하고, 국가 하나만 조회해도 점수가 나온다.

    측정이 안 된 국가(`unscored`)와 실제로 작은 시장(`below_floor`)은 둘 다 순위에서
    빠지지만 뜻이 정반대라 구분해서 담는다.
    """
    for e in entries:
        e["untapped_usd"] = untapped_usd(e)
        e["attractiveness_score"] = None

        missing = [label for label, val in (("시장 규모", e.get("size_usd")),
                                            ("한국 점유율", e.get("korea_share_pct")),
                                            ("시장 성장률", e.get("growth_cagr")))
                   if val is None]
        # 측정 불가와 규모 미달을 나눈다. 전자는 "모른다", 후자는 "안다, 작다"이다.
        # 한 칸에 뭉뚱그리면 사용자가 데이터 공백을 나쁜 시장으로 읽는다.
        if missing:
            e["score_basis"] = "unscored"
            e["score_note"] = (
                f"{', '.join(missing)} 데이터가 없어 순위에서 제외했습니다. "
                f"측정이 안 된 것이지 나쁜 시장이라는 뜻이 아닙니다. "
                f"결측 축을 빼고 계산하면 데이터가 부족한 국가가 오히려 높은 점수를 받습니다.")
            continue
        if e["untapped_usd"] < floor:
            e["score_basis"] = "below_floor"
            e["score_note"] = (
                f"한국 몫이 아닌 수입액이 {fmt_usd(e['untapped_usd'])}로 기준선 "
                f"{fmt_usd(floor)}에 못 미쳐 순위에서 제외했습니다. 데이터가 없는 게 아니라 "
                f"실제로 작은 시장입니다. 소량·고단가 품목이라면 기준선을 낮춰 다시 보세요.")
            continue

        u = _log_saturating(e["untapped_usd"], floor, ceil)
        g = _clamped(e["growth_cagr"], GROWTH_FLOOR, GROWTH_CEIL)
        e["score_components"] = {"untapped": u, "growth": g, "weights": dict(SCORE_WEIGHTS)}
        e["attractiveness_score"] = round(
            100 * (u * SCORE_WEIGHTS["untapped"] + g * SCORE_WEIGHTS["growth"]), 1)
        e["score_basis"] = "full"

    scored = [e for e in entries if e["attractiveness_score"] is not None]

    # 명목 가중치는 의도이고, 실제로 순위를 움직인 비중은 따로다. 이번 비교군에서
    # 값 차이가 거의 없는 축은 가중치가 높아도 순위를 못 바꾼다 — 여러 나라가 상한에
    # 걸려 나란히 만점이면 여유 축이 바로 그 상태가 된다.
    if len(scored) >= 2:
        influence, total = {}, 0.0
        for axis, weight in SCORE_WEIGHTS.items():
            spread = statistics.pstdev([e["score_components"][axis] for e in scored])
            influence[axis] = weight * spread
            total += influence[axis]
        for e in scored:
            e["score_components"]["realized_influence"] = (
                {a: round(v / total, 3) for a, v in influence.items()} if total else None)

    note = (f"점수는 절대 기준입니다 — 여유 시장 {fmt_usd(floor)}~{fmt_usd(ceil)}, "
            f"시장 성장률 {GROWTH_FLOOR:+.0%}~{GROWTH_CEIL:+.0%}를 각각 0~100으로 편 것입니다. "
            f"**어느 나라를 함께 조회하든 같은 나라는 같은 점수가 나오고, 다른 조회에서 나온 "
            f"점수와도 비교할 수 있습니다.** 다만 점수가 답하는 것은 '남은 파이가 얼마고 "
            f"그게 크고 있는가'뿐입니다 — 경쟁 구도·진입장벽·관세는 별도로 봐야 합니다.")
    for e in scored:
        e["score_note"] = note


# --------------------------------------------------------------------------
# output
# --------------------------------------------------------------------------


COLUMN_GUIDE = """\
# CSV 컬럼 설명

숫자마다 "언제 기준인지, 어디서 나온 값인지"를 옆 컬럼에 같이 담았습니다.
이 파일만 있으면 채팅 리포트 없이 CSV만 전달받아도 해석할 수 있습니다.

## markets.csv — 국가별 요약

| 컬럼 | 뜻 |
|---|---|
| country / iso2 | 국가명 / 국가코드 |
| score | 시장 매력도 점수(0–100) = 여유 시장 50% + 시장 CAGR 50% |
| score_basis | `full`=정상 산출 / `unscored`=필요한 값이 없어 순위에서 뺌(나쁜 시장이라는 뜻이 아님) / `below_floor`=여유 시장이 기준선 미만, 즉 실제로 작은 시장 / `n/a`=비교 대상이 1개국뿐 |
| untapped_usd | **여유 시장** = market_size_usd × (1 − 한국 점유율). 아직 한국 몫이 아닌 수입액(달러). 점수의 절반을 차지합니다 |
| kr_export_usd_latest | 한국의 이 나라向 수출액(달러). 기준 연도는 kr_export_year |
| kr_export_year | 위 수출액이 어느 연도 값인지 |
| kr_export_cagr | 한국 수출액의 연평균 성장률. 계산 구간은 kr_export_cagr_span |
| market_cagr | 이 나라 전체 수입(=시장)의 연평균 성장률. 계산 구간은 market_cagr_span |
| market_size_usd | 이 나라의 이 품목 전체 수입액(달러). 시장 규모의 근사치이며, 현지 생산분은 포함되지 않음 |
| partner_import_year | 시장 규모·점유율이 어느 연도 수입 통계 기준인지 |
| partner_import_lagged | True면 이 나라가 최신 연도 통계를 아직 안 올려서 한두 해 전 통계로 대신 조회했다는 뜻 |
| korea_share_pct | 이 나라 수입 중 한국산 비중(%). **수입 중 점유율**이지 내수 시장 점유율이 아님 |
| korea_rank | 공급국 중 한국 순위 |
| top_supplier / top_supplier_share_pct | 1위 공급국과 그 비중(%) |
| dominated | True면 한 나라가 수입의 60% 이상을 차지하는 과점 시장 |
| unit_price_usd_per_kg | 한국 수출 단가(달러/kg) |
| price_trend | 단가 추이 요약 |
| basis_note | 점수 제외 사유, 데이터 공백 등 해석에 필요한 비고 |
| data_source | 데이터 출처. 한국 수출은 FOB, 상대국 수입은 CIF 기준이라 같은 거래도 금액이 다를 수 있음 |
| retrieved_at | 조회한 날짜 |

## annual_series.csv — 연도별 한국 수출 시계열

country(국가), year(연도), value_usd(수출액 달러), weight_kg(중량 kg), unit_price(단가 달러/kg)

## competitors.csv — 국가별 공급국 점유율

importer(수입국), year(기준 연도), supplier(공급국), value_usd(수입액 달러),
share_pct(수입 중 비중 %), unit_price_usd_per_kg(그 공급국의 수출 단가)

## monthly.csv — 월별 시계열 (월별 조회 시에만)

country(국가), period(연월), value_usd(수출액 달러), net_weight_kg(중량 kg)
"""


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
          "| # | 국가 | 매력도 | **여유 시장** | 현지 총수입 | **시장 CAGR** | 한국 수출액 | 한국 수출 CAGR | 한국 점유율 | 1위 공급국 |",
          "|---|---|---|---|---|---|---|---|---|---|"]
    for i, e in enumerate(ranked, 1):
        if e["attractiveness_score"] is None:
            score = "규모 미달" if e.get("score_basis") == "below_floor" else "측정불가"
            rank_label = "–"
        else:
            score = f"**{e['attractiveness_score']}**"
            rank_label = str(i)
        share = e.get("korea_share_pct")
        share_s = "-" if share is None else f"{share:.1f}%"
        top = e.get("top_supplier")
        top_s = ("-" if not top else
                 f"{top} {e['top_supplier_share_pct']:.0f}%"
                 + (" ⚠️" if e.get("dominated") else ""))
        L.append(
            f"| {rank_label} | {e['name']} | {score} | **{fmt_usd(e.get('untapped_usd'))}** | "
            f"{fmt_usd(e.get('market_size_usd'))} | "
            f"**{fmt_pct(e.get('market_cagr'))}** | {fmt_usd(e.get('kr_export_usd'))} | "
            f"{fmt_pct(e.get('kr_export_cagr'))} | {share_s} | {top_s} |")
    note = next((e.get("score_note") for e in ranked if e.get("score_note")), None)
    if note:
        L += ["", f"> ⚠️ {note}"]
    L += ["", "**점수 = 여유 시장 50% + 시장 CAGR 50%.**",
          "**여유 시장 = 현지 총수입 × (1 − 한국 점유율)** — 아직 한국 몫이 아닌 수입액이다. "
          "'시장이 큰가'와 '들어갈 자리가 있는가'를 한 개의 달러 금액으로 합친 값이고, "
          "실무 언어로는 **지금 테이블에 남아 있는 돈**이다.",
          f"이 축은 {fmt_usd(UNTAPPED_CEIL)} 위로는 전부 만점이다. 그 이상의 규모 차이는 "
          f"어느 나라를 먼저 갈지를 바꾸지 않기 때문이다 — 상한을 안 두면 점수가 그냥 "
          f"'수입액 큰 나라 순'이 된다(실측 Spearman +0.89).",
          "성장 축은 **그 나라의 총수입 성장률**이다(한국 수출 성장률이 아니다). "
          "두 열을 나란히 두었으니 같이 읽을 것 — 시장은 크는데 한국 수출만 줄고 있다면 "
          "점유율을 잃고 있다는 뜻이고, 반대면 시장이 죽는데 우리만 버티는 것이다.",
          f"`측정불가` = 시장 규모·한국 점유율·시장 성장률 중 하나라도 없는 국가. 시장이 나쁜 게 "
          f"아니라 **비교할 수 없다**는 뜻이다. `규모 미달` = 여유 시장이 {fmt_usd(UNTAPPED_FLOOR)}에 "
          f"못 미치는 국가 — 이쪽은 데이터가 없는 게 아니라 실제로 작은 시장이다. 둘을 혼동하지 말 것."]

    infl = next((e["score_components"].get("realized_influence") for e in scored
                 if e.get("score_components", {}).get("realized_influence")), None)
    if infl:
        # The nominal split describes intent; this describes what actually moved
        # the ranking. They diverge whenever an axis is near-constant here.
        L.append(f"다만 **이번 조회에서 실제로 순위를 움직인 비중은 "
                 f"여유 시장 {infl['untapped']:.0%} · 성장률 {infl['growth']:.0%}** 였다. "
                 f"국가 간 차이가 거의 없는 축은 가중치가 높아도 순위를 바꾸지 못한다 — "
                 f"여러 나라가 상한에 걸려 나란히 만점이면 여유 축이 바로 그 상태가 된다.")

    L += [f"**두 축 모두 절대 기준이다** — 여유 시장 {fmt_usd(UNTAPPED_FLOOR)}~{fmt_usd(UNTAPPED_CEIL)}, "
          f"시장 성장률 {GROWTH_FLOOR:+.0%}~{GROWTH_CEIL:+.0%}. 어느 나라를 함께 조회하든 "
          "같은 나라는 같은 점수가 나오고, **다른 조회에서 나온 점수와도 비교할 수 있다.** "
          "비교군을 바꿔 여러 번 돌릴 필요가 없다.",
          "⚠️ = 1위 공급국이 60% 이상을 쥔 과점 시장. **여유 시장 금액이 가장 오해를 부르는 곳이다** — "
          "한국 점유율이 낮아 '여유'로 잡히지만 그 자리는 이미 남이 차지하고 있다. "
          "빈 시장이 아니라 진입장벽이 높은 시장으로 읽어야 한다.",
          "여유 시장은 '아직 안 뚫린 몫'이라는 뜻이지 '뚫기 쉽다'는 뜻이 아니다. "
          "한국 점유율이 이미 높은 시장은 여유 금액은 작아도 제품 적합성은 이미 입증된 시장이다.",
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

    if a.csv:
        # Every number in markets.csv carries its basis alongside it — which
        # year it comes from, whether the mirror walked back, what span the
        # CAGR covers, and any caveat notes — so the file stands on its own
        # when it is forwarded around without the chat report.
        def _basis_note(e):
            comp = e["competitors"]
            parts = [e.get("score_note"), e.get("market_growth_note"),
                     e.get("mirror_gap_note"),
                     None if comp.get("available") else comp.get("reason")]
            return " / ".join(p for p in parts if p) or None

        write_csv(outdir / f"hs{hs}_markets.csv",
                  [{"country": e["name"], "iso2": e["iso2"], "score": e["attractiveness_score"],
                    "score_basis": e["score_basis"],
                    "kr_export_usd_latest": e["kr_export_usd"],
                    "kr_export_year": years[-1],
                    "kr_export_cagr": e["kr_export_cagr"],
                    "kr_export_cagr_span": f"{years[0]}–{years[-1]}",
                    "market_cagr": e.get("market_cagr"),
                    "market_cagr_span": e.get("market_growth_span"),
                    "market_size_usd": e["market_size_usd"],
                    "untapped_usd": e.get("untapped_usd"),
                    "partner_import_year": e["competitors"].get("year"),
                    "partner_import_lagged": e["competitors"].get("stale"),
                    "korea_share_pct": e["korea_share_pct"],
                    "korea_rank": e["korea_rank"],
                    "top_supplier": e.get("top_supplier"),
                    "top_supplier_share_pct": e.get("top_supplier_share_pct"),
                    "dominated": e.get("dominated"),
                    "unit_price_usd_per_kg": e["unit_price"],
                    "price_trend": e.get("price_trend"),
                    "basis_note": _basis_note(e),
                    "data_source": "UN Comtrade(한국 신고 수출 FOB + 상대국 신고 수입 CIF 미러)",
                    "retrieved_at": date.today().isoformat()}
                   for e in (sorted([x for x in entries if x["attractiveness_score"] is not None],
                                    key=lambda x: x["attractiveness_score"], reverse=True)
                             + sorted([x for x in entries if x["attractiveness_score"] is None],
                                      key=lambda x: x.get("kr_export_usd") or 0, reverse=True))],
                  ["country", "iso2", "score", "score_basis",
                   "kr_export_usd_latest", "kr_export_year",
                   "kr_export_cagr", "kr_export_cagr_span",
                   "market_cagr", "market_cagr_span", "market_size_usd", "untapped_usd",
                   "partner_import_year", "partner_import_lagged",
                   "korea_share_pct", "korea_rank",
                   "top_supplier", "top_supplier_share_pct", "dominated",
                   "unit_price_usd_per_kg", "price_trend",
                   "basis_note", "data_source", "retrieved_at"])

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

        (outdir / f"hs{hs}_columns.md").write_text(COLUMN_GUIDE, encoding="utf-8")

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
                     "untapped_usd": e.get("untapped_usd"),
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


# 미보고국은 어차피 미러 데이터가 없고, historical 코드(구 유고, 1964년 이전
# 탕가니카 등)는 오늘의 시장이 아니다. 대만은 'Other Asia, nes'(490)로 남겨둔다 —
# historical이 아니고 실재하는 시장이다.
#
# EU(97)·ASEAN(975)은 회원국을 합산한 집계 코드다. 걸러내지 않으면 회원국들과 같은
# 표에 나란히 앉아 "European Union" 이 프랑스·이탈리아보다 위에 뜬다 — 실제로 그렇게
# 나왔다. 갈 수 있는 나라가 아니므로 대상에서 뺀다.
AGGREGATE_REPORTERS = {97, 975}


def discover_reporters() -> list[dict]:
    return [a for a in ct.areas()
            if a.get("reporter") and not a.get("historical")
            and isinstance(a.get("code"), int) and a["code"] > 0
            and a["code"] != KOREA and a["code"] not in AGGREGATE_REPORTERS]


DISCOVER_BATCH = 8


def scan_world(hs: str, year: int, codes: list[int], log,
               batch: int = DISCOVER_BATCH) -> dict[int, dict]:
    """주어진 보고국들의 (총수입, 대한국 수입)을 배치로 훑는다.

    reporterCode 와 partnerCode 는 둘 다 콤마 리스트를 받는다. partner=World,한국 을
    한 콜에 묶으면 **같은 CIF 통계 안에서** 시장 규모와 한국 몫이 같이 나오므로,
    한국 신고 수출(FOB)을 상대국 수입(CIF)으로 나누는 단위 혼용을 피할 수 있다.

    preview 응답은 500행에서 조용히 잘린다. 운송수단별 내역행이 같은 상한을 먹기
    때문에 안전한 배치 크기는 품목마다 다르다. 잘렸을 때 배치를 반씩 쪼개 전부 다시
    부르면 한 번 잘릴 때마다 1콜이 최대 15콜로 불어난다(실측: 분할 55회 발생 후
    15분 경과에도 미완). 대신 **응답에 안 담긴 보고국만** 골라 다시 부른다 — 이미
    받은 행은 잘림과 무관하게 그 나라의 완전한 값이다.
    """
    out: dict[int, dict] = {}
    queue = [codes[i:i + batch] for i in range(0, len(codes), batch)]
    done = 0
    while queue:
        chunk = queue.pop(0)
        rows = ct.fetch(freq="A", period=year, reporter=",".join(map(str, chunk)),
                        partner=f"{ct.WORLD},{KOREA}", hs=hs, flow="M")
        truncated = bool(rows) and any(r.get("_truncated") for r in rows)

        got: dict[int, dict] = {}
        for r in rows:
            rec = got.setdefault(r["reporter_code"],
                                 {"total": None, "from_korea": None, "partial": False})
            if r["partner_code"] == ct.WORLD:
                rec["total"] = r["value_usd"]
            elif r["partner_code"] == KOREA:
                rec["from_korea"] = r["value_usd"]
            # 잘린 응답에서 집계행이 사라지면 _collapse_breakdowns 가 남은 내역행을
            # 합산해 돌려준다. 그 값은 총계처럼 생겼지만 과소집계다. 실측: 말레이시아
            # 2023년이 배치 조회에서 $75.6M(실제 $548.8M)로 잡혀 CAGR이 +187%로
            # 튀었다. 숫자가 조용히 틀리는 유형이라 반드시 다시 물어봐야 한다.
            if r.get("is_partial_sum"):
                rec["partial"] = True

        if len(chunk) > 1 and truncated:
            suspect = [c for c in chunk
                       if c not in got or got[c]["total"] is None
                       or got[c]["from_korea"] is None or got[c]["partial"]]
            for c in chunk:
                if c not in suspect:
                    out[c] = got[c]
            done += len(chunk) - len(suspect)
            if suspect:
                half = max(1, len(suspect) // 2)
                queue[:0] = [suspect[i:i + half] for i in range(0, len(suspect), half)]
                log(f"  {year}년: 응답이 잘려 {len(suspect)}개국 재조회 "
                    f"({len(chunk) - len(suspect)}개국은 확보)")
            continue

        if len(chunk) == 1 and (truncated or (got.get(chunk[0]) or {}).get("partial")):
            # 배치를 1개국까지 줄여도 잘리는 나라가 있다. 슬로베니아는 partner2(2차
            # 상대국) 내역만 500행을 채워 보내고 집계행이 잘려나가는데, 남은 내역행을
            # 합치면 $6.19억이 나온다 — 실제 총수입 $1.24억의 5배다. 과소집계만
            # 걱정했지 과대집계는 예상 못 한 형태라 더 위험하다.
            #
            # 상대국을 하나씩 나눠 부르면 응답이 상한 밑으로 떨어져 집계행이 살아온다.
            # 그 나라 하나에만 2콜을 더 쓰는 대신 숫자가 조용히 틀리지 않는다.
            code = chunk[0]
            log(f"  {year}년: {ct.area_name(code)} 응답이 잘려 상대국별로 분리 조회")
            rec = {"total": None, "from_korea": None, "partial": False}
            for partner, key in ((ct.WORLD, "total"), (KOREA, "from_korea")):
                rows2 = ct.fetch(freq="A", period=year, reporter=code,
                                 partner=partner, hs=hs, flow="M")
                if rows2:
                    rec[key] = rows2[0]["value_usd"]
                    rec["partial"] = rec["partial"] or bool(rows2[0].get("is_partial_sum"))
            out[code] = rec
            done += 1
            continue

        out.update(got)
        done += len(chunk)
        if done % 40 < batch:
            log(f"  {year}년 스캔 {done}/{len(codes)}개국")
    return out


def cmd_discover(a) -> int:
    """어느 나라부터 뚫을지를 **전 세계에서** 찾는다.

    `market` 은 이미 정해진 후보군을 깊게 파는 명령이고, 기본값은 한국 교역 상위
    10개국이다. 그 10개국은 정의상 이미 팔고 있는 나라라서, 거기서는 신규 시장이
    나올 수 없다. 이 명령은 반대로 전 보고국(약 225개국)을 얕게 훑어 후보를 만든다.
    """
    log = (lambda *_: None) if a.quiet else (lambda *m: print(*m, file=sys.stderr))
    hs = ct.validate_hs(a.hs)
    desc = ct.hs_desc(hs)
    log(f"HS {hs} — {desc}")

    latest = int(a.latest_year) if a.latest_year else latest_available_year(hs, log)
    base = latest - a.years_gap
    codes = [x["code"] for x in discover_reporters()]

    # 성장률을 전 세계에서 구하려면 연도마다 전량 스캔이 필요하고, 그러면 콜 수가
    # 두 배가 된다(실측: 무료 티어에서 15분 이상). 최신 연도만 전량 훑어 여유 시장
    # 기준 후보를 추린 뒤, 과거 연도는 그 후보에만 물어본다. 잘려나간 나라가 최종
    # 상위권에 들어오려면 성장 축 만점을 받고도 여유 축에서 후보군 최하위를 이겨야
    # 하므로, 후보군을 최종 출력의 3배로 잡아 그 여지를 남긴다.
    log(f"1단계 — {latest}년 전 세계 스캔: {len(codes)}개국 "
        f"(배치 {DISCOVER_BATCH}, 약 {-(-len(codes) // DISCOVER_BATCH)}콜)")
    cur = scan_world(hs, latest, codes, log)

    def untapped_of(rec):
        t, k = rec.get("total"), rec.get("from_korea")
        if not t or t <= 0:
            return None
        return t - (k or 0)

    pool = sorted(((c, r) for c, r in cur.items() if (untapped_of(r) or 0) >= a.min_market),
                  key=lambda kv: -(untapped_of(kv[1]) or 0))
    shortlist = [c for c, _ in pool[:a.shortlist]]
    log(f"2단계 — 여유 시장 {fmt_usd(a.min_market)} 이상 {len(pool)}개국 중 상위 "
        f"{len(shortlist)}개국만 {base}년 재조회 "
        f"(약 {-(-len(shortlist) // DISCOVER_BATCH)}콜)")
    old = scan_world(hs, base, shortlist, log)

    entries = []
    for code in shortlist:
        rec = cur[code]
        total, from_kr = rec["total"], rec["from_korea"]
        prev = (old.get(code) or {}).get("total")
        entries.append({
            "code": code, "name": ct.area_name(code),
            "iso2": next((x.get("iso2") for x in ct.areas() if x["code"] == code), None),
            "market_size_usd": total,
            "kr_import_usd": from_kr,
            "korea_share_pct": round(100 * (from_kr or 0) / total, 2),
            "market_cagr": cagr(prev, total, a.years_gap),
            "market_cagr_span": f"{base}–{latest}",
            "size_usd": total,
            # 단독 조회에서도 집계행 없이 내역행만 온 나라. 총계가 과소집계일 수 있다.
            "partial_total": bool(rec.get("partial") or (old.get(code) or {}).get("partial")),
        })
    for e in entries:
        e["growth_cagr"] = e["market_cagr"]

    score_markets(entries, floor=a.min_market)

    ranked = sorted((e for e in entries if e["attractiveness_score"] is not None),
                    key=lambda e: -e["attractiveness_score"])

    # 한국 점유율이 낮다는 것은 "자리가 비었다"가 아니라 "아직 우리가 못 들어갔다"다.
    # 그 자리에 이미 누가 앉아 있는지는 이 얕은 스캔으로 알 수 없다 — 후보를 좁힌 뒤
    # market 으로 넘어가야 나온다. 그래서 여기서는 사실만 태그로 남긴다.
    for e in ranked:
        tags = []
        if e["korea_share_pct"] < 1:
            tags.append("미개척")
        elif e["korea_share_pct"] < 5:
            tags.append("초기진입")
        if (e["market_cagr"] or 0) >= 0.10:
            tags.append("고성장")
        if (e["market_cagr"] or 0) < 0:
            tags.append("시장축소")
        if e.get("partial_total"):
            tags.append("집계주의")
        e["tags"] = tags

    top = ranked[:a.top]
    summary = {
        "hs": hs, "hs_desc": desc,
        "latest_year": latest, "base_year": base,
        "reporters_scanned": len(cur),
        "passed_min_market": len(pool),
        "shortlisted": len(shortlist),
        "ranked": len(ranked),
        "min_market_usd": a.min_market,
        "ranking": [{k: e[k] for k in
                     ("name", "iso2", "attractiveness_score", "untapped_usd",
                      "market_size_usd", "market_cagr", "market_cagr_span",
                      "kr_import_usd", "korea_share_pct", "tags")}
                    for e in top],
        "excluded": {
            "below_floor": len(cur) - len(pool),
            "no_growth_data": sum(1 for e in entries if e.get("score_basis") == "unscored"),
        },
        "score_note": top[0]["score_note"] if top else None,
        "method_note": (f"{latest}년은 {len(cur)}개 보고국 전량을 훑었고, {base}년 성장률은 "
                        f"여유 시장 상위 {len(shortlist)}개국만 조회했습니다. 전량 2회 스캔은 "
                        f"무료 공개 티어에서 15분 이상 걸립니다. 후보군 밖 국가가 최종 상위권에 "
                        f"들 여지는 남겨두었지만, 여유 시장이 아주 작은 고성장 시장은 빠질 수 "
                        f"있습니다 — 그런 틈새를 노린다면 --shortlist 를 키우세요."),
        "next_step": (f"후보를 2~5개국으로 좁힌 뒤 `market --hs {hs} --countries <국가들>` 로 "
                      f"넘어가라. 경쟁 구도(1위 공급국·과점 여부)와 한국 수출 추이는 이 스캔에 "
                      f"없다 — 여기서 나온 순위는 '어디를 들여다볼지'까지만 답한다."),
        "limits": [
            "점유율은 수입 중 점유율이다. 현지 생산분은 이 통계에 아예 없다.",
            "중계무역 허브(홍콩·싱가포르·네덜란드·UAE 등)는 재수출분이 섞여 실제 소비 시장보다 크게 잡힌다.",
            "UN Comtrade 미보고국은 아예 나오지 않는다. 목록에 없다 = 시장이 없다가 아니다.",
            f"{base}년 통계를 아직 안 올린 나라는 성장률이 없어 순위에서 빠진다.",
        ],
        "data_source": "UN Comtrade, 상대국 신고 수입(CIF) 기준 — 시장 규모와 한국 몫이 같은 통계 안에서 계산됨",
    }
    json.dump(summary, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


def cmd_products(a) -> int:
    """Reverse lookup: country fixed, product open.

    Answers "이 나라에 뭘 팔면 좋을까" by ranking every HS chapter and HS4
    line Korea already exports there, with growth against a base year. Korea's
    existing exports are the demand-proof proxy — this deliberately does not
    guess at markets Korea has never entered.
    """
    log = (lambda *_: None) if a.quiet else (lambda *m: print(*m, file=sys.stderr))
    area = ct.resolve_area(a.to)
    log(f"대상국: {area['name']}")

    # AG2 is ~100 rows and never truncates, so it is the year probe too.
    latest = None
    y = date.today().year
    for _ in range(4):
        rows = ct.fetch(freq="A", period=y, reporter=KOREA, partner=area["code"],
                        hs="AG2", flow="X")
        if rows:
            latest = y
            break
        log(f"  {y}년 데이터 없음 → {y - 1}년으로 후퇴")
        y -= 1
    if latest is None:
        raise ct.ComtradeError(f"{area['name']}向 한국 수출 연간 데이터를 찾지 못했습니다.")
    base = latest - a.years_gap
    log(f"비교 구간: {base} → {latest}")

    def by_hs(year: int, agg: str) -> dict[str, float]:
        rows = ct.fetch(freq="A", period=year, reporter=KOREA, partner=area["code"],
                        hs=agg, flow="X")
        return {r["hs"]: (r["value_usd"] or 0) for r in rows}

    ch_latest = by_hs(latest, "AG2")
    ch_base = by_hs(base, "AG2")

    # A single AG4 call truncates at 500 rows in HS-code order, not value
    # order — for large partners that silently drops every chapter past ~56
    # (electronics, apparel, machinery) while looking complete. So HS4 detail
    # is fetched chapter by chapter for the top chapters instead: complete
    # within what it covers, with the coverage reported explicitly.
    hs4_by_chapter: dict[str, list[str]] = {}
    for r in ct.hs_table():
        c = str(r.get("code"))
        if len(c) == 4 and c.isdigit():
            hs4_by_chapter.setdefault(c[:2], []).append(c)

    top_chapters = sorted(
        {c for src in (ch_latest, ch_base)
         for c in sorted(src, key=lambda k: -src[k])[:a.chapters]}
        & hs4_by_chapter.keys())
    log(f"HS4 상세: 수출액 상위 {len(top_chapters)}개 챕터 × 2개 연도 조회 "
        f"(~{2 * len(top_chapters)}콜)")

    h4_latest: dict[str, float] = {}
    h4_base: dict[str, float] = {}
    for ch in top_chapters:
        codes = ",".join(hs4_by_chapter[ch])
        for year, acc in ((latest, h4_latest), (base, h4_base)):
            for r in ct.fetch(freq="A", period=year, reporter=KOREA,
                              partner=area["code"], hs=codes, flow="X"):
                acc[r["hs"]] = r["value_usd"] or 0

    total_latest = sum(ch_latest.values())
    covered_latest = sum(ch_latest.get(c, 0) for c in top_chapters)
    coverage_pct = round(100 * covered_latest / total_latest, 1) if total_latest else None

    def growth(code: str, cur: dict, old: dict) -> float | None:
        b = old.get(code) or 0
        return (cur[code] / b - 1) if b > 0 else None

    def table(cur: dict, old: dict, top: int) -> list[dict]:
        codes = sorted(cur, key=lambda c: -cur[c])[:top]
        return [{"hs": c, "desc": ct.hs_desc(c),
                 "value_latest_usd": cur[c], "value_base_usd": old.get(c),
                 "growth_pct": (round(g * 100, 1) if (g := growth(c, cur, old)) is not None
                                else None)}
                for c in codes]

    # Rising list: growth needs a floor so a $30k line tripling doesn't outrank
    # a $15M line growing 40%.
    floor = a.min_value
    rising = sorted((c for c in h4_latest
                     if h4_latest[c] >= floor and growth(c, h4_latest, h4_base) is not None),
                    key=lambda c: -growth(c, h4_latest, h4_base))[:a.top]

    # Declining ranks over the BASE-year population: a line that vanished
    # entirely by the latest year is the clearest decline of all, and it never
    # appears in h4_latest.
    declining = sorted((c for c in h4_base
                        if h4_base[c] >= floor and h4_latest.get(c, 0) < h4_base[c] * 0.8),
                       key=lambda c: h4_latest.get(c, 0) / h4_base[c])[:a.top]

    summary = {
        "to": area["name"], "iso2": area.get("iso2"),
        "latest_year": latest, "base_year": base,
        "chapters": table(ch_latest, ch_base, a.top),
        "hs4_top_by_value": table(h4_latest, h4_base, a.top),
        "hs4_top_by_growth": [
            {"hs": c, "desc": ct.hs_desc(c),
             "value_latest_usd": h4_latest[c], "value_base_usd": h4_base.get(c),
             "growth_pct": round(growth(c, h4_latest, h4_base) * 100, 1)}
            for c in rising],
        "hs4_declining": [
            {"hs": c, "desc": ct.hs_desc(c),
             "value_latest_usd": h4_latest.get(c, 0), "value_base_usd": h4_base[c],
             "growth_pct": round((h4_latest.get(c, 0) / h4_base[c] - 1) * 100, 1)}
            for c in declining],
        "growth_floor_usd": floor,
        "hs4_coverage": {
            "chapters_covered": top_chapters,
            "value_coverage_pct": coverage_pct,
            "note": (f"HS4 상세(규모·성장·감소 표)는 수출액 상위 {len(top_chapters)}개 "
                     f"챕터만 조회한 것으로, 최신연도 수출액의 "
                     f"{coverage_pct if coverage_pct is not None else '?'}%를 커버합니다. "
                     "챕터(HS2) 표는 전 품목 기준입니다."),
        },
        "data_source": "UN Comtrade, 한국 신고 수출(FOB) 기준",
    }
    json.dump(summary, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


def cmd_domestic(a) -> int:
    """한국 신고 기준 정밀 조회 — HSK 10단위, 월별, 관세청.

    이 명령은 **점유율도 매력도 점수도 내지 않는다.** 관세청은 한국 쪽 숫자만 주고,
    상대국 수입을 10단위로 공개하는 나라는 없어서 분모가 존재하지 않는다. HSK10 분자를
    HS6 분모로 나누면 점유율이 실제보다 낮게 나오는데 숫자는 그럴듯해 보인다 — 이
    스킬이 계속 막으려는 바로 그 유형이라, score_markets 로 가는 경로 자체를 안 만든다.

    시장 규모·경쟁 구도·매력도가 필요하면 `market` 을 쓴다. 이건 그 다음 단계,
    "우리 제품이 정확히 어느 라인이고 단가가 어떻게 움직였나"에만 답한다.
    """
    log = (lambda *_: None) if a.quiet else (lambda *m: print(*m, file=sys.stderr))
    hs = re.sub(r"\D", "", a.hs) if a.hs else None
    if hs and len(hs) not in (2, 4, 6, 10):
        raise kcs.CustomsError(f"HSK 코드는 2·4·6·10 자리여야 합니다: '{a.hs}'")

    targets = [ct.resolve_area(c.strip()) for c in a.countries.split(",") if c.strip()]
    for t in targets:
        if not t.get("iso2"):
            raise kcs.CustomsError(
                f"{t['name']}는 ISO2 코드가 없어 관세청 조회를 할 수 없습니다"
                f"(관세청 API는 ISO2 국가코드만 받습니다).")
    log(f"대상국: {', '.join(t['name'] for t in targets)}")

    edge = a.latest_month or kcs.latest_month(targets[0]["iso2"], hs)
    if not edge:
        raise kcs.CustomsError("관세청에서 최근 12개월 내 데이터를 찾지 못했습니다.")
    end_i = kcs._ym_index(kcs._ym(edge))
    start = kcs._ym_from_index(end_i - a.months + 1)
    log(f"기간: {start}~{edge} ({a.months}개월, 관세청 최신 공표월 기준)")

    entries = []
    for area in targets:
        rows = kcs.drill(country=area["iso2"], hs=hs, start=start, end=edge, log=log)
        by_line: dict[tuple, list[dict]] = {}
        for r in rows:
            by_line.setdefault((r["hs"], r["item_name_ko"]), []).append(r)

        lines = []
        for (code, name), rs in by_line.items():
            rs.sort(key=lambda r: r["period"])
            series = [{"period": r["period"], "export_usd": r["export_usd"],
                       "export_kg": r["export_kg"],
                       "unit_price": unit_price(r["export_usd"], r["export_kg"])}
                      for r in rs]
            recent = [s for s in series[-12:]]
            prior = [s for s in series[-24:-12]]
            r_usd = sum(s["export_usd"] or 0 for s in recent)
            p_usd = sum(s["export_usd"] or 0 for s in prior)
            r_kg = sum(s["export_kg"] or 0 for s in recent)
            p_kg = sum(s["export_kg"] or 0 for s in prior)

            # HSK 10단위는 품목 믹스가 사실상 고정이라 단가 변화를 가격 변화로 읽을 수
            # 있다 — HS 6단위까지는 못 하던 해석이다. 다만 '기타'로 끝나는 코드는
            # 10단위여도 잡탕이라 같은 함정이 남는다.
            catchall = bool(name and ("기타" in name or "그 밖" in name))
            price_note = None
            if r_kg > 0 and p_kg > 0:
                chg = (r_usd / r_kg) / (p_usd / p_kg) - 1
                if abs(chg) >= 0.05:
                    if len(str(code)) == 10 and not catchall:
                        price_note = (f"{chg * 100:+.1f}% — HSK 10단위라 품목 믹스가 거의 "
                                      f"고정이다. 단가 변화로 읽어도 된다.")
                    else:
                        price_note = (f"{chg * 100:+.1f}% — 이 코드는 여러 제품이 섞여 있어 "
                                      f"가격 변동인지 믹스 변동인지 분해되지 않는다.")
            lines.append({
                "hs": code, "item_name_ko": name,
                "export_usd_12m": r_usd, "export_kg_12m": r_kg,
                "export_usd_prior_12m": p_usd or None,
                "yoy_pct": (round(100 * (r_usd / p_usd - 1), 1) if p_usd else None),
                "unit_price_12m": unit_price(r_usd, r_kg),
                "unit_price_prior_12m": unit_price(p_usd, p_kg),
                "price_note": price_note,
                "is_catchall_code": catchall,
                "monthly": series,
            })
        lines.sort(key=lambda x: -(x["export_usd_12m"] or 0))
        entries.append({"country": area["name"], "iso2": area["iso2"], "lines": lines,
                        "export_usd_12m": sum(l["export_usd_12m"] or 0 for l in lines)})

    entries.sort(key=lambda e: -e["export_usd_12m"])
    summary = {
        "source": "관세청 수출입통계 (한국 신고 기준, FOB)",
        "hs_requested": hs, "months": a.months,
        "period": {"start": start, "end": edge,
                   "note": f"관세청 최신 공표월은 {edge[:4]}.{edge[4:]}입니다. "
                           f"UN Comtrade 연간 통계보다 통상 1년 이상 최신입니다."},
        "countries": [{"country": e["country"], "iso2": e["iso2"],
                       "export_usd_12m": e["export_usd_12m"],
                       "lines": [{k: v for k, v in l.items() if k != "monthly"}
                                 for l in e["lines"][:a.top]]}
                      for e in entries],
        "isolation_note": (
            "이 수치는 **한국 신고 수출(FOB)**입니다. 시장 규모·경쟁국 점유율·매력도 점수는 "
            "여기서 산출하지 않습니다 — 그것들은 상대국 신고 수입(CIF) 기준이고 HS 6단위가 "
            "한계입니다. 이 표의 HSK 10단위 금액을 시장 규모로 나눠 점유율을 만들지 마세요. "
            "분자만 좁아져 점유율이 실제보다 낮게 나옵니다. 점유율이 필요하면 `market`을 쓰세요."),
    }
    if a.csv:
        outdir = Path(a.outdir).expanduser().resolve()
        outdir.mkdir(parents=True, exist_ok=True)
        tag = hs or "all"
        write_csv(outdir / f"hsk{tag}_domestic.csv",
                  [{"country": e["country"], "iso2": e["iso2"], **{k: v for k, v in l.items()
                                                                   if k != "monthly"},
                    "period": f"{start}-{edge}",
                    "data_source": "관세청 수출입통계(한국 신고 수출 FOB)",
                    "retrieved_at": date.today().isoformat()}
                   for e in entries for l in e["lines"]],
                  ["country", "iso2", "hs", "item_name_ko", "export_usd_12m", "export_kg_12m",
                   "export_usd_prior_12m", "yoy_pct", "unit_price_12m", "unit_price_prior_12m",
                   "price_note", "is_catchall_code", "period", "data_source", "retrieved_at"])
        write_csv(outdir / f"hsk{tag}_domestic_monthly.csv",
                  [{"country": e["country"], "hs": l["hs"], "item_name_ko": l["item_name_ko"], **m}
                   for e in entries for l in e["lines"] for m in l["monthly"]],
                  ["country", "hs", "item_name_ko", "period", "export_usd", "export_kg",
                   "unit_price"])
        summary["files"] = sorted(p.name for p in outdir.glob(f"hsk{tag}_*"))
        summary["outdir"] = str(outdir)

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
    s.add_argument("--csv", action="store_true",
                   help="원본 데이터 CSV도 저장 (기본은 리포트 md + JSON 요약만)")
    s.add_argument("--outdir", default="./trade-stats-out")
    s.add_argument("--quiet", action="store_true")
    s.set_defaults(fn=cmd_market)

    d = sub.add_parser("discover",
                       help="전 세계 스캔: 한국이 아직 안 판 나라까지 포함해 "
                            "'어느 나라부터 뚫을지' 후보를 만든다")
    d.add_argument("--hs", required=True, help="HS 2/4/6 단위")
    d.add_argument("--top", type=int, default=20, help="상위 몇 개국을 낼지 (기본 20)")
    d.add_argument("--years-gap", type=int, default=2,
                   help="성장률 비교 간격 연수 (기본 2 = 최신연도 vs 2년 전)")
    d.add_argument("--min-market", type=float, default=UNTAPPED_FLOOR,
                   help=f"여유 시장 하한 USD (기본 {UNTAPPED_FLOOR:,.0f}). "
                        f"소량·고단가 품목이면 낮춰라")
    d.add_argument("--shortlist", type=int, default=60,
                   help="성장률을 조회할 후보국 수 (기본 60). 키우면 정확해지고 느려진다")
    d.add_argument("--latest-year", help="최신 연도 자동탐지 대신 고정")
    d.add_argument("--quiet", action="store_true")
    d.set_defaults(fn=cmd_discover)

    pr = sub.add_parser("products",
                        help="역방향 조회: 국가를 정했는데 품목을 모를 때, 한국이 그 나라에 "
                             "이미 팔고 있는 품목을 규모·성장률로 랭킹")
    pr.add_argument("--to", required=True, help="대상국 (ISO2·한글명·숫자코드)")
    pr.add_argument("--years-gap", type=int, default=2,
                    help="성장률 비교 간격 연수 (기본 2 = 최신연도 vs 2년 전)")
    pr.add_argument("--top", type=int, default=20, help="각 랭킹의 품목 수 (기본 20)")
    pr.add_argument("--chapters", type=int, default=15,
                    help="HS4 상세를 조회할 수출액 상위 챕터 수 (기본 15, 챕터당 2콜)")
    pr.add_argument("--min-value", type=float, default=1_000_000,
                    help="성장률 랭킹에 넣을 최소 수출액 USD (기본 100만)")
    pr.add_argument("--quiet", action="store_true")
    pr.set_defaults(fn=cmd_products)

    dm = sub.add_parser("domestic",
                        help="관세청 정밀 조회: HSK 10단위 · 월별 · 한국 신고 기준. "
                             "점유율·매력도는 내지 않는다(=market 의 일)")
    dm.add_argument("--hs", help="HSK 2/4/6/10 단위. 생략하면 그 나라 전 품목")
    dm.add_argument("--countries", required=True, help="쉼표 구분(US,JP 또는 미국,일본)")
    dm.add_argument("--months", type=int, default=24,
                    help="최근 N개월 (기본 24 = YoY 계산 가능한 최소치)")
    dm.add_argument("--top", type=int, default=15, help="국가당 상위 품목 수")
    dm.add_argument("--latest-month", help="최신월 자동탐지 대신 고정 (YYYYMM)")
    dm.add_argument("--csv", action="store_true")
    dm.add_argument("--outdir", default="./trade-stats-out")
    dm.add_argument("--quiet", action="store_true")
    dm.set_defaults(fn=cmd_domestic)

    a = p.parse_args()
    try:
        return a.fn(a)
    except kcs.CustomsKeyMissing as exc:
        json.dump({"error": "customs_key_missing", "message": str(exc)},
                  sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
        return 1
    except kcs.CustomsError as exc:
        json.dump({"error": "customs_error", "message": str(exc)},
                  sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
        return 1
    except ct.ComtradeError as exc:
        json.dump({"error": "comtrade_error", "message": str(exc)},
                  sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
