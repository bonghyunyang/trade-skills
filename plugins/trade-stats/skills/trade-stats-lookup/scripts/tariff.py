#!/usr/bin/env python3
"""수입국이 한국산에 물리는 관세율 — World Bank WITS/TRAINS, 인증키 불필요.

  python3 tariff.py --importer 베트남 --hs 330499
  python3 tariff.py --importer VN --hs 330499 --compare CN,JP,US

한국 관세청 세율표(한국이 수입할 때 무는 세율)가 아니라, **상대국이 한국산 수입품에
적용한 세율**을 조회한다. MFN(일반세율)과 대한국 적용세율(FTA 특혜 반영)을 나란히 줘서
"한국이 경쟁국 대비 몇 %p 유리한가"에 답한다.

수치는 해당 HS6 아래 상대국 세번(8~10단위)들의 단순평균이다. WITS 데이터는 1~5년
지연되므로 기준 연도를 반드시 함께 보고할 것. FTA 단계 인하(staging) 때문에 현재
세율은 표시된 값보다 낮을 수 있다 — 계약용 확정 세율은 TradeNavi/FTA 포털에서 확인.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date

import comtrade as ct

BASE = "https://wits.worldbank.org/API/V1/SDMX/V21/datasource/TRN"
MFN_PARTNER = "000"  # WITS convention: partner 000 = MFN (erga omnes)
MFN_WALKBACK = 6     # anchor-year search — without MFN there is no report
PREF_WALKBACK = 3    # per-partner search; --deep raises it back to 6

ELIGIBILITY_NOTE = (
    "특혜세율은 원산지증명서(CO) 발급과 해당 협정의 품목별 원산지기준(PSR) 충족이 "
    "전제입니다. 원산지기준을 못 맞추면(예: 중국산 원부자재 비중이 높은 경우) "
    "특혜세율이 아니라 MFN 세율이 적용됩니다."
)


# WITS's numeric country dimension is not one system: probing known-FTA pairs
# shows Vietnam←India data under ISO 356 (Comtrade 699 is 404) while
# Canada←USA data sits under Comtrade 842 (ISO 840 is 404). Alpha ISO3 is
# rejected outright (HTML error page). So for countries where the two
# numberings diverge, both codes must be tried — a miss on the wrong code is
# indistinguishable from "no preferential scheme". Misses are negative-cached,
# so the extra walk is paid once.
ALT_WITS_CODES = {
    "842": "840",  # USA
    "699": "356",  # India
    "251": "250",  # France
    "381": "380",  # Italy
    "579": "578",  # Norway
    "757": "756",  # Switzerland
    "490": "158",  # Taiwan / Other Asia nes
    "097": "918",  # EU
}


def _candidates(area: dict) -> list[str]:
    code = f"{area['code']:03d}"
    alt = ALT_WITS_CODES.get(code)
    return [code, alt] if alt else [code]


def _fetch(reporter: str, partner: str, hs: str, year: int) -> list[float] | None:
    """All tariff-line observations for one (importer, partner, hs6, year).

    Returns None when WITS has no record — that is a routine answer here
    (data lag, or no preferential scheme), not an error.
    """
    url = (f"{BASE}/reporter/{reporter}/partner/{partner}/product/{hs}"
           f"/year/{year}/datatype/reported?format=JSON")
    try:
        payload = ct._get(url)
    except ct.ComtradeError as exc:
        if "404" in str(exc):
            # A WITS 404 takes 40-70s and _get caches only successes, so an
            # uncached walk-back miss is repaid in full on every rerun. Cache
            # the miss as an empty payload — rereads return None instantly.
            ct._write_cache(url, {"dataSets": [{"series": {}}]})
            return None
        raise
    rates = []
    for s in (payload.get("dataSets") or [{}])[0].get("series", {}).values():
        for obs in s.get("observations", {}).values():
            if obs and obs[0] is not None:
                rates.append(float(obs[0]))
    return rates or None


def _avg(rates: list[float]) -> float:
    return round(sum(rates) / len(rates), 2)


def cmd(a) -> int:
    log = (lambda *_: None) if a.quiet else (lambda *m: print(*m, file=sys.stderr))
    hs = re.sub(r"\D", "", a.hs)
    if len(hs) > 6:
        hs = hs[:6]
        log(f"WITS는 HS 6단위까지만 — {hs} 로 잘라 조회합니다.")
    if len(hs) < 6:
        # products/market hand over HS4 codes; passing one through would be an
        # opaque WITS HTTP 400, so refuse with directions instead.
        json.dump({"error": "no_hs6",
                   "message": f"관세율은 HS 6단위로만 조회됩니다. '{a.hs}'는 "
                              f"{len(hs)}단위입니다. HS {hs} 하위의 6단위 코드를 먼저 "
                              f"정하세요 (fetch_comtrade.py hs-search 로 찾을 수 있습니다)."},
                  sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
        return 1
    importer = ct.resolve_area(a.importer)
    log(f"수입국: {importer['name']}")

    partners = [("한국", ["410"])]
    for tok in (a.compare.split(",") if a.compare else []):
        area = ct.resolve_area(tok.strip())
        partners.append((area["name"], _candidates(area)))

    # MFN is reported for far more (importer, year) pairs than any single
    # preferential line, so it anchors the year walk-back. The importer's own
    # code can sit under either numbering — try candidates in turn.
    rep, year, mfn = None, None, None
    for rep_c in _candidates(importer):
        y = date.today().year - 1
        for _ in range(MFN_WALKBACK):
            log(f"  MFN 조회 {y} (코드 {rep_c})...")
            mfn = _fetch(rep_c, MFN_PARTNER, hs, y)
            if mfn:
                rep, year = rep_c, y
                break
            y -= 1
        if rep:
            break
    if year is None:
        json.dump({"error": "no_data",
                   "message": f"{importer['name']}의 HS {hs} 관세율이 WITS에 없습니다. "
                              f"최근 {MFN_WALKBACK}개 연도를 모두 확인했습니다."},
                  sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
        return 1

    mfn_avg = _avg(mfn)
    mfn_by_year = {year: mfn_avg}

    # Preferential lines lag further behind than MFN (e.g. Vietnam reports MFN
    # through 2023 but Korea-preferential only through 2021), so each partner
    # walks back independently from the MFN anchor year. The advantage is then
    # computed against MFN of the SAME year the preferential rate came from.
    rows = []
    depth = MFN_WALKBACK if a.deep else PREF_WALKBACK
    for name, codes in partners:
        # One partner failing (429 exhausted, WITS 5xx, malformed response)
        # must not throw away the MFN and the other partners already paid for.
        try:
            pref, pyear = None, None
            for code in codes:
                for yy in range(year, year - depth, -1):
                    log(f"  {name} 적용세율 조회 {yy} (코드 {code})...")
                    pref = _fetch(rep, code, hs, yy)
                    if pref:
                        pyear = yy
                        break
                if pref:
                    break
        except ct.ComtradeError as exc:
            rows.append({"partner": name,
                         "error": str(exc).replace("Comtrade", "WITS")})
            continue
        if pref is None:
            # No preferential record is NOT the same as "no benefit" — never
            # coin a 0.0pp here; three different situations map onto it.
            rows.append({
                "partner": name,
                "applied_avg_pct": None,
                "preferential_found": False,
                "year": None,
                "advantage_vs_mfn_pp": None,
                "fallback_used": "mfn",
                "note": (f"최근 {depth}개 연도에 특혜세율 기록 없음(가능한 국가코드 "
                         f"{len(codes)}종 모두 시도). 둘 중 하나입니다: "
                         f"①{importer['name']}이(가) {name}산에 적용하는 특혜협정 없음"
                         f"(MFN {mfn_avg}% 적용) ②협정은 있으나 WITS 미반영. "
                         f"'혜택 없음'으로 단정하지 말고 TradeNavi에서 교차확인 필요."),
            })
            continue
        applied = _avg(pref)
        if pyear not in mfn_by_year:
            log(f"  MFN 조회 {pyear} (비교 기준 맞춤)...")
            base = _fetch(rep, MFN_PARTNER, hs, pyear)
            mfn_by_year[pyear] = _avg(base) if base else None
        base_mfn = mfn_by_year[pyear]
        if base_mfn is None:
            base_mfn = mfn_avg
            note = (f"특혜세율은 {pyear}년 기록인데 그 해 MFN이 WITS에 없어 "
                    f"{year}년 MFN과 비교했습니다. 유불리 %p는 참고치로만 보세요.")
        elif pyear != year:
            note = (f"특혜세율 최신 기록이 {pyear}년이라 그 해 기준으로 비교. "
                    f"FTA 단계 인하로 현재는 이보다 낮을 수 있음")
        else:
            note = None
        rows.append({
            "partner": name,
            "applied_avg_pct": applied,
            "preferential_found": True,
            "year": pyear,
            "advantage_vs_mfn_pp": round(base_mfn - applied, 2),
            "fallback_used": None,
            "note": note,
        })

    summary = {
        "importer": importer["name"],
        "hs": hs,
        "hs_desc": ct.hs_desc(hs),
        "year": year,
        "year_note": (None if year >= date.today().year - 2 else
                      f"WITS 최신 기록이 {year}년입니다. FTA 단계 인하로 현재 세율은 "
                      f"이보다 낮을 수 있습니다."),
        "mfn_avg_pct": mfn_avg,
        "partners": rows,
        "eligibility_note": ELIGIBILITY_NOTE,
        "basis": (f"HS {hs} 아래 {importer['name']} 세번들의 단순평균. "
                  "종량세·쿼터는 반영되지 않음"),
        "data_source": "World Bank WITS / UNCTAD TRAINS",
        "confirm_at": "계약용 확정 세율은 TradeNavi(tradenavi.or.kr) 또는 FTA 포털에서 확인",
    }
    json.dump(summary, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--importer", required=True, help="수입국 (ISO2·한글명·숫자코드)")
    p.add_argument("--hs", required=True, help="HS 6단위 (더 길면 6단위로 자름)")
    p.add_argument("--compare", help="비교할 경쟁 수출국, 쉼표 구분 (예: CN,JP,US)")
    p.add_argument("--deep", action="store_true",
                   help=f"특혜세율 후퇴 조회를 {PREF_WALKBACK}년 대신 {MFN_WALKBACK}년까지 "
                        f"(연도당 40~70초 추가)")
    p.add_argument("--quiet", action="store_true")
    a = p.parse_args()
    try:
        return cmd(a)
    except ct.ComtradeError as exc:
        json.dump({"error": "wits_error",
                   "message": str(exc).replace("Comtrade", "WITS")},
                  sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
