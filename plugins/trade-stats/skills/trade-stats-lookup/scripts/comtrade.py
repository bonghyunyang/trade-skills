"""UN Comtrade public-preview client.

Talks to ``https://comtradeapi.un.org/public/v1/preview/C/{freq}/HS``, the
preview tier UN Comtrade publishes without an API key. Preview limits shape the
whole design: responses cap at 500 rows, and ``period`` takes exactly one value
per call, so a monthly series costs one request per month.

This is a free public tier, so the client is deliberately unhurried — a minimum
interval between requests (floored, never zero), ``Retry-After`` honored on 429,
and a 7-day disk cache so a repeated question costs nothing. Anyone needing bulk
extraction should get a subscription key rather than lean on this path.

Parsing is defensive throughout: an upstream schema change is the most likely
way this breaks, so no field is assumed to exist.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import socket
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Iterable

MIN_PYTHON = (3, 11)
if sys.version_info < MIN_PYTHON:
    # Every script imports this module, so the check lands here once. Without it
    # an old interpreter fails somewhere deep with a message that means nothing
    # to a salesperson who never chose their Python version.
    raise SystemExit(
        f"Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]} 이상이 필요합니다 "
        f"(현재 {sys.version_info.major}.{sys.version_info.minor}).\n"
        f"macOS 기본 파이썬은 3.9라 별도 설치가 필요합니다: brew install python@3.11"
    )

BASE_URL = "https://comtradeapi.un.org/public/v1/preview/C/{freq}/HS"
REF_DIR = Path(__file__).resolve().parent.parent / "references"
CACHE_DIR = Path(
    os.environ.get("TRADE_STATS_CACHE_DIR", Path.home() / ".cache" / "trade-stats-lookup")
)
CACHE_TTL_SECONDS = int(os.environ.get("TRADE_STATS_CACHE_TTL", 7 * 24 * 3600))
# Pacing has a floor. The env var exists to slow requests down on a shared IP,
# not to speed them up: a knob that lets any user set 0 turns a courtesy delay
# into a suggestion, and the endpoint is an unauthenticated public tier.
MIN_INTERVAL = max(1.0, float(os.environ.get("TRADE_STATS_MIN_INTERVAL", "2.0")))
MAX_RETRIES = 7
PREVIEW_ROW_CAP = 500

WORLD = 0
KOREA = 410

_last_call_at = 0.0


class ComtradeError(RuntimeError):
    pass


# --------------------------------------------------------------------------
# reference data
# --------------------------------------------------------------------------

_areas: list[dict] | None = None
_hs: list[dict] | None = None
_aliases: dict[str, int] | None = None


def areas() -> list[dict]:
    global _areas
    if _areas is None:
        _areas = json.loads((REF_DIR / "areas.json").read_text(encoding="utf-8"))
    return _areas


def hs_table() -> list[dict]:
    global _hs
    if _hs is None:
        _hs = json.loads((REF_DIR / "hs.json").read_text(encoding="utf-8"))
    return _hs


def ko_aliases() -> dict[str, int]:
    global _aliases
    if _aliases is None:
        raw = json.loads((REF_DIR / "country_aliases_ko.json").read_text(encoding="utf-8"))
        _aliases = {_norm(k): int(v) for k, v in raw.items()}
    return _aliases


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFC", str(s)).strip().lower()
    return re.sub(r"[\s\-_.,'()]+", "", s)


def _preference(area: dict) -> tuple:
    """Sort key for picking between areas that share a code/name.

    Comtrade keeps dissolved states alongside current ones and they collide on
    ISO3 — 'Viet Nam'(704) vs 'Rep. of Vietnam (...1974)'(868), 'India'(699) vs
    'India (...1974)'(356), 'USA'(842) vs 'United States of America'(840).
    Historical entities lose first, then non-reporters, then longer names
    (so 'France' beats 'Metropolitan France').
    """
    return (bool(area.get("historical")),
            not area.get("reporter"),
            len(area.get("name") or ""))


# Codes that exist in the reference list but carry no trade data. Taiwan is
# listed as 158 yet every transaction is booked under 490 'Other Asia, nes' —
# resolving to 158 silently returns zero rows, which reads as "no exports".
CODE_REDIRECTS = {158: 490}


def _display(area: dict) -> dict:
    """Return a copy whose ``name`` is the user-facing label, after redirecting
    codes that hold no data to the code that does."""
    code = CODE_REDIRECTS.get(area["code"])
    if code is not None:
        area = next((a for a in areas() if a["code"] == code), area)
    out = dict(area)
    out["name"] = area_name(area["code"]) or area["name"]
    return out


def resolve_area(token: str | int) -> dict:
    """Resolve 'KZ' / 'KAZ' / '398' / 'Kazakhstan' / '카자흐스탄' to an area record."""
    if isinstance(token, int) or (isinstance(token, str) and token.strip().isdigit()):
        code = int(token)
        for a in areas():
            if a["code"] == code:
                return _display(a)
        raise ComtradeError(f"알 수 없는 국가 코드: {token}")

    key = _norm(token)
    if key in {"world", "전세계", "세계", "전세게"}:
        return {"code": WORLD, "name": "World", "iso2": None, "iso3": None,
                "reporter": False, "partner": True}

    alias = ko_aliases().get(key)
    if alias is not None:
        for a in areas():
            if a["code"] == alias:
                return _display(a)

    exact, prefix = [], []
    for a in areas():
        for field in (a.get("iso2"), a.get("iso3"), a.get("name")):
            if not field:
                continue
            nf = _norm(field)
            if nf == key:
                exact.append(a)
                break
            if nf.startswith(key) and len(key) >= 3:
                prefix.append(a)
                break
    for bucket in (exact, prefix):
        if not bucket:
            continue
        bucket.sort(key=_preference)
        best = _preference(bucket[0])
        tied = [a for a in bucket if _preference(a)[:2] == best[:2]]
        if len(tied) == 1 or len(bucket) == 1:
            return _display(bucket[0])
        names = ", ".join(f"{a['name']}({a.get('iso2') or a['code']})" for a in tied[:8])
        raise ComtradeError(f"'{token}' 가 여러 국가와 매칭됩니다: {names}")
    raise ComtradeError(
        f"'{token}' 국가를 찾지 못했습니다. `python3 scripts/fetch_comtrade.py country-search <키워드>` 로 확인하세요."
    )


def search_areas(keyword: str, limit: int = 20) -> list[dict]:
    key = _norm(keyword)
    hits = [a for a in areas()
            if key in _norm(a["name"]) or key == _norm(a.get("iso2") or "") or key == _norm(a.get("iso3") or "")]
    for k, code in ko_aliases().items():
        if key in k:
            hits.extend(a for a in areas() if a["code"] == code)
    seen, out = set(), []
    for a in sorted(hits, key=_preference):
        if a["code"] not in seen:
            seen.add(a["code"])
            out.append(a)
    return out[:limit]


_hs_ko: dict[str, str] | None = None


def hs_ko_index() -> dict[str, str]:
    """Korean keywords per HS code. Comtrade ships English descriptions only,
    so '화장품' or '이차전지' matches nothing without this layer."""
    global _hs_ko
    if _hs_ko is None:
        path = REF_DIR / "hs_ko.json"
        _hs_ko = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    return _hs_ko


def search_hs(keyword: str, level: int | None = None, limit: int = 25) -> list[dict]:
    """Search HS codes by Korean keyword or English description.

    Korean matches rank first and are marked, because a Korean hit is an
    intentional curation while an English one is a substring coincidence.
    """
    query = keyword.strip()
    key = _norm(query)
    raw_words = [w.lower() for w in re.split(r"\s+", query) if w]
    ko = hs_ko_index()

    # Rank by how close the keyword is to what was actually typed, not by which
    # matched first or which is longest. "휴대폰케이스" contains "휴대폰", so a
    # first-match rule sends a phone-case query to 8517 (handsets) — a
    # confidently wrong code producing an entirely wrong report — while a
    # longest-match rule sends a plain "휴대폰" query to 3926 (cases). Exact
    # match wins, then the smallest length difference.
    def _closeness(word: str) -> tuple:
        nw = _norm(word)
        return (nw != key, abs(len(nw) - len(key)))

    ko_hits: dict[str, str] = {}
    if key:
        for code, words in ko.items():
            best = None
            for word in words.split():
                nw = _norm(word)
                if nw == key or (len(key) >= 2 and key in nw) or (len(nw) >= 2 and nw in key):
                    if best is None or _closeness(word) < _closeness(best):
                        best = word
            if best is not None:
                ko_hits[code] = best

    out, seen = [], set()
    for row in hs_table():
        code = str(row.get("code"))
        if level is not None and row.get("level") != level:
            continue
        matched_ko = ko_hits.get(code)
        desc = (row.get("desc") or "").lower()
        matched_en = bool(raw_words) and all(w in desc for w in raw_words)
        if not (matched_ko or matched_en):
            continue
        hit = dict(row)
        hit["matched"] = "ko" if matched_ko else "en"
        if matched_ko:
            hit["ko_keyword"] = matched_ko
        out.append(hit)
        seen.add(code)

    # Korean hits first; among them the closest keyword wins, so "핸드폰케이스"
    # beats a partial "휴대폰" and a bare "휴대폰" query still lands on handsets.
    out.sort(key=lambda r: (r["matched"] != "ko",
                            _closeness(r.get("ko_keyword") or "\uffff"),
                            r.get("level") or 99,
                            len(r.get("desc") or "")))
    return out[:limit]


def hs_desc(code: str) -> str | None:
    code = str(code)
    for row in hs_table():
        if str(row.get("code")) == code:
            return row.get("desc")
    return None


def validate_hs(code: str) -> str:
    code = re.sub(r"\D", "", str(code))
    if code == "":
        raise ComtradeError("HS코드는 숫자여야 합니다.")
    if len(code) in (8, 10):
        # Comtrade only carries HS2/4/6. Truncate and tell the caller loudly.
        raise ComtradeError(
            f"UN Comtrade는 HS 6단위까지만 제공합니다. {len(code)}단위 '{code}' 대신 "
            f"'{code[:6]}'(6단위)로 조회하세요. HS 10단위는 관세청 오픈API가 필요합니다."
        )
    if len(code) not in (2, 4, 6):
        raise ComtradeError(f"HS코드는 2/4/6 단위여야 합니다: '{code}'")

    # Catch typos here rather than letting them look like "이 품목은 수출이 없다".
    # An unknown code returns empty rows from every call, which is
    # indistinguishable from a real zero unless we check the code list first.
    known = {str(r.get("code")) for r in hs_table()}
    if code not in known:
        parent = next((c for c in (code[:4], code[:2]) if c and c in known), None)
        hint = (f" 상위 코드 '{parent}'({hs_desc(parent)})는 존재합니다."
                if parent else
                " `fetch_comtrade.py hs-search <영문 키워드>` 로 코드를 확인하세요.")
        raise ComtradeError(f"HS '{code}' 는 존재하지 않는 코드입니다.{hint}")
    return code


# --------------------------------------------------------------------------
# HTTP
# --------------------------------------------------------------------------


MAX_INTERVAL = 15.0


def _slow_down() -> None:
    """Raise the pacing floor for the remainder of this process after a 429."""
    global MIN_INTERVAL
    if MIN_INTERVAL < MAX_INTERVAL:
        MIN_INTERVAL = min(MIN_INTERVAL * 2, MAX_INTERVAL)


def _user_agent() -> str:
    """Identify the client, and let an operator attach a way to reach them.

    A data publisher that notices odd traffic from a shared office IP currently
    has no route back to whoever is running this. Setting TRADE_STATS_CONTACT to
    an email or repo URL gives them one.
    """
    contact = (os.environ.get("TRADE_STATS_CONTACT") or "").strip()
    return f"trade-stats-lookup/1.0 (+{contact})" if contact else "trade-stats-lookup/1.0"


def _cache_path(url: str) -> Path:
    return CACHE_DIR / (hashlib.sha256(url.encode()).hexdigest()[:32] + ".json")


def _read_cache(url: str) -> dict | None:
    p = _cache_path(url)
    try:
        if p.exists() and (time.time() - p.stat().st_mtime) < CACHE_TTL_SECONDS:
            return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        pass
    return None


def _write_cache(url: str, payload: dict) -> None:
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        target = _cache_path(url)
        # Two runs can request the same URL at once — several agents sharing one
        # cache is the normal case here. A half-written file would be read back
        # as corrupt (survivable) or, worse, as valid truncated JSON.
        tmp = target.with_suffix(f".{os.getpid()}.tmp")
        tmp.write_text(json.dumps(payload), encoding="utf-8")
        os.replace(tmp, target)
    except OSError:
        pass  # cache is an optimization, never a hard dependency


def _get(url: str, use_cache: bool = True) -> dict:
    global _last_call_at
    if use_cache:
        cached = _read_cache(url)
        if cached is not None:
            return cached

    delay = MIN_INTERVAL
    last_err: Exception | None = None
    for attempt in range(MAX_RETRIES):
        wait = MIN_INTERVAL - (time.time() - _last_call_at)
        if wait > 0:
            time.sleep(wait)
        try:
            req = urllib.request.Request(url, headers={"Accept": "application/json",
                                                       "User-Agent": _user_agent()})
            with urllib.request.urlopen(req, timeout=90) as resp:
                body = resp.read()
            _last_call_at = time.time()
            payload = json.loads(body)
            if use_cache:
                _write_cache(url, payload)
            return payload
        except urllib.error.HTTPError as exc:
            _last_call_at = time.time()
            last_err = exc
            if exc.code in (429, 500, 502, 503, 504):
                # If the server says how long to wait, wait that long. Ignoring
                # Retry-After and running our own backoff is what "trying to get
                # around the limit" looks like, whatever the intent.
                wait_hint = None
                try:
                    raw_hint = (exc.headers or {}).get("Retry-After")
                    if raw_hint is not None:
                        wait_hint = float(str(raw_hint).strip())
                except (TypeError, ValueError):
                    wait_hint = None
                if exc.code == 429:
                    # Retrying at the same cadence just walks back into the
                    # limit: a 5-country, 4-year run exhausted all five retries
                    # at the default 2s pacing. Slow the *rest of the run* down,
                    # not only this one call — the limit is about sustained rate,
                    # so the pacing that caused it has to change.
                    _slow_down()
                time.sleep(max(wait_hint, delay) if wait_hint else delay)
                delay = min(delay * 2, 60)
                continue
            detail = ""
            try:
                detail = exc.read().decode("utf-8", "replace")[:300]
            except Exception:
                pass
            raise ComtradeError(f"Comtrade HTTP {exc.code}: {detail}") from exc
        except (urllib.error.URLError, TimeoutError, ValueError) as exc:
            _last_call_at = time.time()
            last_err = exc
            # DNS/name resolution won't fix itself inside a retry loop. Backing
            # off 5 times costs a full minute per call to reach the same answer,
            # so surface "네트워크가 안 된다" immediately.
            if isinstance(getattr(exc, "reason", None), socket.gaierror):
                raise ComtradeError(
                    "Comtrade 서버에 연결할 수 없습니다. 인터넷 연결을 확인하세요. "
                    f"({exc.reason})"
                ) from exc
            time.sleep(delay)
            delay = min(delay * 2, 30)
    raise ComtradeError(f"Comtrade 호출이 {MAX_RETRIES}회 실패했습니다: {last_err}")


def _f(row: dict, *keys: str) -> float | None:
    for k in keys:
        v = row.get(k)
        if isinstance(v, (int, float)) and v != 0:
            return float(v)
    for k in keys:
        v = row.get(k)
        if isinstance(v, (int, float)):
            return float(v)
    return None


def _collapse_breakdowns(data: list[dict]) -> list[dict]:
    """Keep one row per (period, reporter, partner, commodity).

    The reporter belongs in the key even though most calls request a single one:
    ``reporterCode`` accepts a comma list, and without it every reporter in such
    a response collapses to one row — or worse, falls into the summing branch
    below and returns the sum of 60 countries as if it were one country's total.

    Some reporters (Viet Nam, for one) return the partner total **and** its
    mode-of-transport breakdown in the same response. Viet Nam's 2023 imports of
    HS3304 from Korea come back as four rows — 127.1M total plus 110.2M sea,
    16.9M air, 0.02M other. Treating those as separate suppliers inflates the
    market total and wrecks every share percentage computed from it.

    ``motCode=0`` / ``partner2Code=0`` / ``customsCode=C00`` / ``mosCode=0`` is
    the aggregate slice. If a group has no aggregate row we sum its breakdown
    rows instead, so a reporter that only publishes detail still yields a total.
    """
    groups: dict[tuple, list[dict]] = {}
    for r in data:
        key = (r.get("period"), r.get("reporterCode"), r.get("partnerCode"),
               r.get("cmdCode"), r.get("flowCode"))
        groups.setdefault(key, []).append(r)

    out = []
    for rows in groups.values():
        if len(rows) == 1:
            out.append(rows[0])
            continue
        totals = [r for r in rows
                  if (r.get("motCode") or 0) == 0
                  and (r.get("partner2Code") or 0) == 0
                  and str(r.get("customsCode") or "C00") == "C00"
                  and str(r.get("mosCode") or "0") == "0"]
        if len(totals) == 1:
            out.append(totals[0])
        elif totals:
            out.append(max(totals, key=lambda r: r.get("primaryValue") or 0))
        else:
            # No aggregate row. Either the reporter publishes detail only, or
            # the 500-row cap cut the aggregate away and left some breakdowns —
            # in which case this sum is an undercount, not a total. The caller
            # decides how loudly to say so, using `truncated` on the response.
            merged = dict(rows[0])
            for field in ("primaryValue", "fobvalue", "cifvalue", "netWgt", "grossWgt", "qty", "altQty"):
                vals = [r.get(field) for r in rows if isinstance(r.get(field), (int, float))]
                merged[field] = sum(vals) if vals else None
            merged["_summed_breakdown"] = len(rows)
            out.append(merged)
    return out


def fetch(
    *,
    freq: str,
    period: str | int,
    reporter: int | str,
    partner: int | None,
    hs: str,
    flow: str,
    use_cache: bool = True,
) -> list[dict]:
    """One Comtrade preview call → normalized rows.

    ``partner=None`` requests every partner (the country-ranking case).
    """
    if freq not in ("A", "M"):
        raise ComtradeError("freq는 'A'(연간) 또는 'M'(월간) 이어야 합니다.")
    if flow not in ("X", "M"):
        raise ComtradeError("flow는 'X'(수출) 또는 'M'(수입) 이어야 합니다.")

    params = {
        "reporterCode": reporter,
        "period": period,
        "cmdCode": hs,
        "flowCode": flow,
    }
    if partner is not None:
        params["partnerCode"] = partner
    url = BASE_URL.format(freq=freq) + "?" + urllib.parse.urlencode(params)

    payload = _get(url, use_cache=use_cache)
    if not isinstance(payload, dict):
        raise ComtradeError("Comtrade 응답 형식이 예상과 다릅니다.")
    if payload.get("error"):
        raise ComtradeError(f"Comtrade error: {payload['error']}")

    raw = [r for r in (payload.get("data") or []) if isinstance(r, dict)]
    data = _collapse_breakdowns(raw)

    rows = []
    for r in data:
        rows.append({
            "period": str(r.get("period") or period),
            "freq": freq,
            "flow": flow,
            "reporter_code": r.get("reporterCode"),
            "partner_code": r.get("partnerCode"),
            "partner_name": area_name(r.get("partnerCode")),
            "reporter_name": area_name(r.get("reporterCode")),
            "hs": str(r.get("cmdCode") or hs),
            "value_usd": _f(r, "primaryValue", "fobvalue", "cifvalue"),
            "net_weight_kg": _f(r, "netWgt"),
            "qty": _f(r, "qty"),
            "qty_unit": r.get("qtyUnitAbbr"),
            "is_weight_estimated": bool(r.get("isNetWgtEstimated")),
            "is_partial_sum": bool(r.get("_summed_breakdown")),
        })

    # Preview truncates silently at 500 rows — surface it instead of hiding it.
    # Counted on the raw response: transport breakdowns eat into the same cap.
    if len(raw) >= PREVIEW_ROW_CAP:
        for row in rows:
            row["_truncated"] = True
    return rows


_ko_names: dict[int, str] | None = None


def ko_names() -> dict[int, str]:
    """Korean display labels. Comtrade's own labels are English and sometimes
    politically neutral to the point of being unrecognizable ('Other Asia, nes')."""
    global _ko_names
    if _ko_names is None:
        raw = json.loads((REF_DIR / "country_names_ko.json").read_text(encoding="utf-8"))
        _ko_names = {int(k): v for k, v in raw.items()}
    return _ko_names


def area_name(code: Any) -> str | None:
    if code is None:
        return None
    try:
        code = int(code)
    except (TypeError, ValueError):
        return None
    if code in ko_names():
        return ko_names()[code]
    if code == WORLD:
        return "World"
    for a in areas():
        if a["code"] == code:
            return a["name"]
    return f"code-{code}"


def months(start: str, end: str) -> list[str]:
    """'2023-01', '2023-12' → ['202301', ...]. Accepts YYYYMM too."""
    def parse(s: str) -> tuple[int, int]:
        d = re.sub(r"\D", "", s)
        if len(d) != 6:
            raise ComtradeError(f"기간 형식은 YYYY-MM 이어야 합니다: '{s}'")
        return int(d[:4]), int(d[4:])

    y0, m0 = parse(start)
    y1, m1 = parse(end)
    out = []
    y, m = y0, m0
    while (y, m) <= (y1, m1):
        out.append(f"{y}{m:02d}")
        m += 1
        if m > 12:
            y, m = y + 1, 1
        if len(out) > 180:
            raise ComtradeError("월 구간이 너무 깁니다(최대 15년).")
    return out


def top_partners(n: int = 10) -> list[dict]:
    """Korea's largest export destinations overall (not HS-specific).

    Snapshot in references/kr-top-partners.json; refresh with
    ``python3 scripts/refresh_reference.py partners``.
    """
    data = json.loads((REF_DIR / "kr-top-partners.json").read_text(encoding="utf-8"))
    return data["partners"][:n]


def top_partners_meta() -> dict:
    data = json.loads((REF_DIR / "kr-top-partners.json").read_text(encoding="utf-8"))
    return {k: v for k, v in data.items() if k != "partners"}


def reports_to_comtrade(code: int) -> bool:
    for a in areas():
        if a["code"] == code:
            return bool(a.get("reporter"))
    return False
