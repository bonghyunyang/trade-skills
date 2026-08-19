"""관세청 수출입통계 클라이언트 — 한국 신고 기준, HSK 10단위, 월별.

UN Comtrade 와 성격이 정반대라 별도 모듈로 둔다.

|            | UN Comtrade                | 관세청                         |
|------------|----------------------------|--------------------------------|
| 관점       | 상대국 신고 수입(CIF)      | **한국 신고 수출입(FOB)**      |
| 세분화     | HS 6단위가 끝              | **HSK 10단위**                 |
| 최신성     | 연간 1~2년 지연            | **익월 공표**                  |
| 응답 상한  | 500행에서 조용히 잘림      | 실측 77,606행까지 무제한       |
| 무결성     | 없음                       | **총계 행이 체크섬**           |
| 인증       | 불필요                     | 서비스키 필요                  |

두 소스를 **절대 섞어 계산하지 마라.** 한국 신고 수출은 FOB, 상대국 신고 수입은 CIF라
같은 거래도 금액이 다르다(실측: 2024년 대미 화장품 FOB $15.5억 vs CIF $17.6억, +13.5%).
그리고 결정적으로, HSK 10단위 분자를 HS 6단위 분모로 나누면 점유율이 실제보다 낮게
나온다 — 세상 어느 나라도 상대국 수입을 10단위로 공개하지 않기 때문에 그 분모는
존재하지 않는다. 점유율·시장 규모·매력도는 전부 Comtrade 미러 안에서만 계산한다.

서비스: 관세청_품목별 국가별 수출입실적(GW) / getNitemtradeList
인증키: 환경변수 TRADE_STATS_CUSTOMS_KEY (공공데이터포털 '일반 인증키')
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

BASE_URL = "https://apis.data.go.kr/1220000/nitemtrade/getNitemtradeList"
CACHE_DIR = Path(
    os.environ.get("TRADE_STATS_CACHE_DIR", Path.home() / ".cache" / "trade-stats-lookup")
) / "customs"
# 관세청 통계는 월 1회 갱신이라 7일 캐시가 데이터를 낡게 만들지 않는다.
CACHE_TTL_SECONDS = int(os.environ.get("TRADE_STATS_CACHE_TTL", 7 * 24 * 3600))
# 문서상 30 tps. 그 근처로 몰아붙일 이유가 없어 0.2초를 바닥으로 둔다.
MIN_INTERVAL = max(0.2, float(os.environ.get("TRADE_STATS_CUSTOMS_MIN_INTERVAL", "0.3")))
MAX_RETRIES = 5
MAX_SPAN_MONTHS = 12  # API 제약: "조회기간 1년이내"

_last_call_at = 0.0


class CustomsError(RuntimeError):
    pass


class CustomsKeyMissing(CustomsError):
    pass


# 제공기관 에러코드(기술문서 2-2). 00 이외는 전부 실패다.
_AGENCY_ERRORS = {
    "01": "관세청 서비스 시스템 오류입니다. 잠시 후 다시 시도하세요.",
    "02": "인증키가 요청에 포함되지 않았습니다.",
    "03": "인증키가 올바르지 않습니다. TRADE_STATS_CUSTOMS_KEY 값을 확인하세요.",
    "99": "필수 요청변수가 누락되었습니다.",
}


SIGNUP_GUIDE = """관세청 정밀 조회(HSK 10단위·최신월)에는 인증키가 필요합니다.
이 스킬의 나머지 기능은 전부 키 없이 동작합니다 — 시장 우선순위, 전 세계 발굴,
경쟁국 점유율, 품목 검색은 지금 그대로 쓸 수 있습니다.

키가 필요한 이유: 관세청 통계는 UN Comtrade 와 달리 공개 무인증 엔드포인트가 없습니다.
발급은 무료이고 5분이면 끝납니다.

  1. https://www.data.go.kr 접속 → 회원가입 / 로그인
  2. 검색창에 '수출입무역통계' 입력
  3. 검색 결과에서 **'관세청_품목별 국가별 수출입실적(GW)'** 을 선택
     - 바로가기: https://www.data.go.kr/data/15100475/openapi.do
     - 비슷한 이름이 4개 더 있습니다. 반드시 **'품목별 국가별'** 을 고르세요:
         · 관세청_품목별 국가별 수출입실적(GW)  ← 이것 (국가 + HSK 10단위)
         · 관세청_품목별 수출입실적(GW)          ✗ 국가 구분 없음
         · 관세청_국가별 수출입실적(GW)          ✗ 품목 구분 없음
         · 관세청_시도별 품목별 수출입실적(GW)   ✗ 국내 시도별
         · 관세청_수출입총괄(GW)                 ✗ 총괄 집계
  4. [활용신청] 클릭 → 활용목적 간단히 기재 → 신청
     (개발계정은 대개 즉시 승인, 일일 10,000건)
  5. 마이페이지 → 오픈API → 인증키 발급현황에서 '일반 인증키' 복사
     https://www.data.go.kr/iim/api/selectAPIAcountView.do
  6. 터미널에서:
       export TRADE_STATS_CUSTOMS_KEY='<복사한 키>'
     인코딩·디코딩 어느 쪽을 붙여넣어도 됩니다.

키를 발급받으면 얻는 것:
  · HSK 10단위 — 우리 제품 라인만 정확히 (HS 6단위로는 여러 제품이 섞입니다)
  · 품목 믹스가 고정되어 단가 변화를 '가격 변화'로 읽을 수 있습니다
  · 한국 신고 기준이라 UN Comtrade 보다 1년 이상 최신입니다

키가 없어도 되는 것: 시장 규모·경쟁국 점유율·매력도는 애초에 관세청에서 나오지
않습니다(상대국 신고 통계라서). 그건 키 없이 `market` / `discover` 로 계속 봅니다."""


def service_key() -> str:
    key = (os.environ.get("TRADE_STATS_CUSTOMS_KEY") or "").strip()
    if not key:
        raise CustomsKeyMissing(SIGNUP_GUIDE)
    return key


def has_key() -> bool:
    """키가 있는지만 확인한다. 호출 없이, 예외 없이.

    스킬이 관세청 기능을 먼저 들이밀지 않고 '가능한지'만 조용히 판단할 때 쓴다.
    """
    return bool((os.environ.get("TRADE_STATS_CUSTOMS_KEY") or "").strip())


def _encoded_key() -> str:
    """포털은 인코딩·디코딩 두 형태를 주는데 사용자는 어느 쪽인지 모른다.

    디코딩 키에는 `+` `/` `=` 가, 인코딩 키에는 그것들이 `%2B` `%2F` `%3D` 로 들어 있다.
    인코딩 키를 다시 인코딩하면 `%` 가 `%25` 가 되어 인증이 조용히 실패한다 — 키가
    틀렸다는 메시지가 나오는데 키는 맞아서 원인을 찾기 어렵다. 그래서 한 번 풀었다가
    다시 인코딩해 어느 쪽을 받든 같은 결과가 되게 한다.
    """
    return urllib.parse.quote(urllib.parse.unquote(service_key()), safe="")


def _cache_path(url: str) -> Path:
    # 캐시 키에 인증키가 섞여 들어가면 키 교체 때 캐시가 통째로 무효화된다.
    scrubbed = re.sub(r"serviceKey=[^&]*", "serviceKey=", url)
    return CACHE_DIR / (hashlib.sha256(scrubbed.encode()).hexdigest()[:32] + ".json")


def _read_cache(url: str) -> list[dict] | None:
    p = _cache_path(url)
    try:
        if p.exists() and (time.time() - p.stat().st_mtime) < CACHE_TTL_SECONDS:
            return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        pass
    return None


def _write_cache(url: str, payload: list[dict]) -> None:
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        target = _cache_path(url)
        tmp = target.with_suffix(f".{os.getpid()}.tmp")
        tmp.write_text(json.dumps(payload), encoding="utf-8")
        os.replace(tmp, target)
    except OSError:
        pass  # 캐시는 최적화지 의존 대상이 아니다


def _num(v: str | None) -> float | None:
    if v is None:
        return None
    s = str(v).strip().replace(",", "")
    if not s or s == "-":
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _get(url: str, use_cache: bool = True) -> bytes:
    global _last_call_at
    delay = MIN_INTERVAL
    last_err: Exception | None = None
    for _ in range(MAX_RETRIES):
        wait = MIN_INTERVAL - (time.time() - _last_call_at)
        if wait > 0:
            time.sleep(wait)
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": "trade-stats-lookup/1.0", "Accept": "application/xml"})
            with urllib.request.urlopen(req, timeout=120) as resp:
                body = resp.read()
            _last_call_at = time.time()
            return body
        except urllib.error.HTTPError as exc:
            _last_call_at = time.time()
            last_err = exc
            if exc.code in (429, 500, 502, 503, 504):
                time.sleep(delay)
                delay = min(delay * 2, 30)
                continue
            detail = ""
            try:
                detail = exc.read().decode("utf-8", "replace")[:300]
            except Exception:
                pass
            raise CustomsError(f"관세청 API HTTP {exc.code}: {detail}") from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            _last_call_at = time.time()
            last_err = exc
            if isinstance(getattr(exc, "reason", None), socket.gaierror):
                raise CustomsError(
                    "관세청 API 서버에 연결할 수 없습니다. 인터넷 연결을 확인하세요. "
                    f"({exc.reason})") from exc
            time.sleep(delay)
            delay = min(delay * 2, 30)
    raise CustomsError(f"관세청 API 호출이 {MAX_RETRIES}회 실패했습니다: {last_err}")


def _parse(body: bytes) -> tuple[list[dict], dict | None]:
    try:
        root = ET.fromstring(body)
    except ET.ParseError as exc:
        raise CustomsError(f"관세청 응답이 XML이 아닙니다: {body[:200]!r}") from exc

    # 포털 게이트웨이 단계 실패는 <OpenAPI_ServiceResponse> 로 온다 — 본문 스키마가
    # 아예 달라서 resultCode 를 찾을 수 없다.
    if root.tag.endswith("OpenAPI_ServiceResponse"):
        msg = root.findtext(".//returnAuthMsg") or root.findtext(".//errMsg") or "알 수 없는 오류"
        code = root.findtext(".//returnReasonCode") or ""
        hint = {
            "22": "일일 호출 한도를 초과했습니다. 개발계정 기본 10,000건/일입니다.",
            "30": "등록되지 않은 인증키입니다. 활용신청 승인 여부와 키를 확인하세요.",
            "31": "인증키 활용기간이 만료됐습니다.",
        }.get(code.strip(), "")
        raise CustomsError(f"관세청 API 인증 오류 [{code}] {msg}. {hint}".strip())

    # 프록시·점검 페이지는 <html>...</html> 로 오는데 그것도 유효한 XML 이라 파싱을
    # 통과한다. 태그를 확인하지 않으면 resultCode 도 item 도 없는 채로 빈 리스트가
    # 돌아가고, 그건 "수출 실적 없음"과 구분되지 않는다.
    if not root.tag.endswith("response"):
        raise CustomsError(
            f"관세청 응답이 예상 형식(<response>)이 아닙니다(<{root.tag}>). "
            f"점검 중이거나 프록시가 가로챘을 수 있습니다: {body[:150]!r}")

    result = (root.findtext(".//resultCode") or "").strip()
    message = (root.findtext(".//resultMsg") or "").strip()
    if result and result != "00":
        raise CustomsError(f"관세청 API 오류 [{result}] "
                           f"{_AGENCY_ERRORS.get(result, message or '사유 미상')}")
    # 파라미터 검증 실패는 resultCode 를 안 채우고 메시지만 오는 경우가 있다.
    if not result and message:
        raise CustomsError(f"관세청 API 오류: {message}")

    rows, total = [], None
    for item in root.iter("item"):
        r = {c.tag: (c.text or "").strip() for c in item}
        rec = {
            "period": r.get("year", ""),
            "country_code": r.get("statCd"),
            "country_name": r.get("statCdCntnKor1"),
            "hs": r.get("hsCd"),
            "item_name_ko": r.get("statKor"),
            "export_usd": _num(r.get("expDlr")),
            "export_kg": _num(r.get("expWgt")),
            "import_usd": _num(r.get("impDlr")),
            "import_kg": _num(r.get("impWgt")),
            "balance_usd": _num(r.get("balPayments")),
        }
        if rec["period"] == "총계":
            total = rec
        else:
            rows.append(rec)
    return rows, total


def _verify(rows: list[dict], total: dict | None, url: str) -> None:
    """총계 행과 명세 행의 합을 대조한다.

    Comtrade 에는 없는 안전장치다. 저쪽은 500행에서 조용히 잘려도 알 방법이 없어
    이 레포에서 두 번(다중 reporter 병합, 잘린 응답의 합산값) 틀린 숫자를 낳았다.
    여기서는 서버가 스스로 합계를 같이 보내주므로, 한 행이라도 빠지면 즉시 드러난다.
    실측 77,606행까지 일치했다 — 안 맞으면 응답이 잘린 것이니 신뢰하면 안 된다.
    """
    if not total or not rows:
        return
    for field in ("export_usd", "import_usd"):
        got = sum(r[field] or 0 for r in rows)
        want = total[field] or 0
        # 달러 정수라 반올림 오차가 없어야 정상이다. 1달러 여유만 둔다.
        if abs(got - want) > 1:
            raise CustomsError(
                f"관세청 응답 무결성 검증 실패: {field} 행 합계 {got:,.0f} ≠ "
                f"총계 {want:,.0f}. 응답이 잘렸을 수 있으니 이 숫자를 쓰지 마세요. "
                f"기간을 좁혀 다시 조회하세요.")


def _ym(v: str | int) -> str:
    d = re.sub(r"\D", "", str(v))
    if len(d) != 6:
        raise CustomsError(f"년월 형식은 YYYYMM 이어야 합니다: '{v}'")
    if not 1 <= int(d[4:]) <= 12:
        raise CustomsError(f"월이 1~12 범위를 벗어났습니다: '{v}'")
    return d


def _ym_index(ym: str) -> int:
    return int(ym[:4]) * 12 + int(ym[4:]) - 1


def _ym_from_index(i: int) -> str:
    return f"{i // 12:04d}{i % 12 + 1:02d}"


def _spans(start: str, end: str) -> list[tuple[str, str]]:
    """1년 제한에 맞춰 구간을 쪼갠다. 12개월 초과 요청은 서버가 거절한다."""
    a, b = _ym_index(start), _ym_index(end)
    if a > b:
        raise CustomsError(f"시작({start})이 종료({end})보다 늦습니다.")
    out = []
    while a <= b:
        stop = min(a + MAX_SPAN_MONTHS - 1, b)
        out.append((_ym_from_index(a), _ym_from_index(stop)))
        a = stop + 1
    return out


def fetch(*, country: str, start: str | int, end: str | int,
          hs: str | None = None, hs_prefix: str | None = None,
          use_cache: bool = True) -> list[dict]:
    """관세청 품목별 국가별 수출입실적.

    country : ISO2 (예 'US'). 필수 파라미터라 전 세계 일괄 조회는 불가능하다.
    hs      : HSK 2/4/6/10 단위. 생략하면 그 나라 전 품목(실측 대미 12개월 77,606행).
              **응답은 요청보다 정확히 한 단계 아래로 분해되어 온다** — 실측:
              2자리→4자리, 4자리→6자리, 6자리→10자리, 미지정→10자리 전량.
              그래서 HSK 10단위를 원하면 6자리를 넣어야 한다. drill() 이 이걸 처리한다.
    hs_prefix : 전량 덤프에서 특정 코드 이하만 남길 때. **캐시에 저장하기 전에**
              걸러서 21MB 응답이 그대로 캐시 파일이 되는 것을 막는다.
    start/end : YYYYMM. 12개월을 넘으면 자동으로 나눠 부른다.
    """
    start, end = _ym(start), _ym(end)
    cc = str(country).strip().upper()
    if not re.fullmatch(r"[A-Z]{2}", cc):
        raise CustomsError(f"국가코드는 ISO2 두 글자여야 합니다: '{country}'")

    out: list[dict] = []
    for a, b in _spans(start, end):
        params = {"strtYymm": a, "endYymm": b, "cntyCd": cc}
        if hs:
            params["hsSgn"] = re.sub(r"\D", "", str(hs))
        url = f"{BASE_URL}?serviceKey={_encoded_key()}&{urllib.parse.urlencode(params)}"
        cache_url = url if not hs_prefix else f"{url}#prefix={hs_prefix}"

        cached = _read_cache(cache_url) if use_cache else None
        if cached is not None:
            out.extend(cached)
            continue

        rows, total = _parse(_get(url))
        # 무결성 검증은 반드시 필터 이전에 — 걸러낸 뒤에는 총계와 안 맞는 게 정상이다.
        _verify(rows, total, url)
        if hs_prefix:
            rows = [r for r in rows if (r["hs"] or "").startswith(hs_prefix)]
        if use_cache:
            _write_cache(cache_url, rows)
        out.extend(rows)
    return out


def drill(*, country: str, start: str | int, end: str | int,
          hs: str | None = None, log=None) -> list[dict]:
    """무엇을 넣든 HSK 10단위 행으로 돌려준다.

    API가 한 단계씩만 내려주기 때문에 필요한 만큼 되짚어 내려간다. 다만 챕터(2자리)를
    끝까지 파면 1 + 7 + 40 콜쯤 되는데, 그 나라 전 품목을 통째로 받는 것은 콜 하나다
    (대미 12개월 실측 21MB / 8.5초). 그래서 2자리 이하는 전량 덤프 후 접두어로 거른다.
    """
    say = log or (lambda *_: None)
    code = re.sub(r"\D", "", str(hs)) if hs else ""

    if len(code) == 10:
        return fetch(country=country, hs=code, start=start, end=end)
    if len(code) == 6:
        return fetch(country=country, hs=code, start=start, end=end)
    if len(code) in (0, 2):
        say(f"  HS{code or '전체'}: 자식 코드를 하나씩 파면 40콜이 넘어 전 품목을 한 번에 받는다")
        return fetch(country=country, start=start, end=end, hs_prefix=code or None)
    if len(code) == 4:
        children = {r["hs"] for r in fetch(country=country, hs=code, start=start, end=end)}
        say(f"  HS{code}: 하위 6단위 {len(children)}개 → HSK 10단위로 재조회")
        rows = []
        for child in sorted(children):
            rows.extend(fetch(country=country, hs=child, start=start, end=end))
        return rows
    raise CustomsError(f"HSK 코드는 2·4·6·10 자리여야 합니다: '{hs}'")


def latest_month(country: str = "US", hs: str | None = None,
                 today: str | None = None) -> str | None:
    """실제로 데이터가 있는 최신 월. 관세청은 익월 공표라 통상 1~2개월 전이다.

    고정 버퍼를 빼는 대신 실제로 물어본다 — 공표일이 달마다 조금씩 다르고, 버퍼를
    잘못 잡으면 있는 데이터를 없다고 하거나 없는 달을 최신이라고 말하게 된다.
    """
    now = today or time.strftime("%Y%m")
    end = _ym_index(_ym(now))
    rows = fetch(country=country, hs=hs,
                 start=_ym_from_index(end - 11), end=_ym_from_index(end))
    months = {r["period"] for r in rows if r.get("period")}
    return max(months).replace(".", "") if months else None
