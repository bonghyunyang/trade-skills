"""관세청 클라이언트.

Comtrade 쪽에서 값이 조용히 틀렸던 사고가 두 번 났다(다중 reporter 병합, 잘린 응답의
합산). 관세청은 응답에 총계 행을 같이 주므로 같은 사고를 **탐지할 수 있다** — 그
탐지를 실제로 하고 있는지가 이 파일의 핵심이다.

진짜 인증키 없이 전부 돈다(_get 을 대체하므로 호출이 나가지 않는다). 키가 있어야만 도는
오프라인 테스트는 CI 에서 조용히 건너뛰어지고, 그러면 아무도 깨진 걸 모른다.
"""

from __future__ import annotations

import unittest
import urllib.parse
from unittest import mock

import context
from context import kcs


def setUpModule():
    """캐시를 끈다.

    안 끄면 첫 테스트가 쓴 응답을 다음 테스트가 읽어버린다 — 잘린 응답을 넣었는데
    앞 테스트의 정상 응답이 돌아와 검증 실패 테스트가 통과해버렸다. 캐시 키는 URL
    기준이고 여러 테스트가 같은 URL 을 쓴다.
    """
    for name in ("_read_cache", "_write_cache"):
        patcher = mock.patch.object(kcs, name,
                                    (lambda *_a, **_k: None))
        patcher.start()
        unittest.addModuleCleanup(patcher.stop)


def xml(items, total=None, result="00", msg="정상서비스."):
    def item(period, hs, name, exp, imp=0, kg=1):
        return (f"<item><balPayments>0</balPayments><expDlr>{exp}</expDlr>"
                f"<expWgt>{kg}</expWgt><hsCd>{hs}</hsCd><impDlr>{imp}</impDlr>"
                f"<impWgt>0</impWgt><statCd>US</statCd>"
                f"<statCdCntnKor1>미국</statCdCntnKor1><statKor>{name}</statKor>"
                f"<year>{period}</year></item>")
    body = "".join(item(*i) for i in items)
    if total is not None:
        body += item("총계", "-", "-", total)
    return (f'<?xml version="1.0" encoding="UTF-8"?><response><header>'
            f"<resultCode>{result}</resultCode><resultMsg>{msg}</resultMsg></header>"
            f"<body><items>{body}</items></body></response>").encode("utf-8")


def with_response(body):
    return mock.patch.object(kcs, "_get", return_value=body)


class TestChecksum(unittest.TestCase):
    """총계 행은 서버가 공짜로 주는 무결성 검증 수단이다. 안 쓰면 없는 것과 같다."""

    def test_matching_total_passes(self):
        body = xml([("2025.01", "3304991000", "기초화장용", 100),
                    ("2025.02", "3304991000", "기초화장용", 250)], total=350)
        with with_response(body):
            rows = kcs.fetch(country="US", hs="330499", start="202501", end="202502")
        self.assertEqual(len(rows), 2)
        self.assertAlmostEqual(sum(r["export_usd"] for r in rows), 350)

    def test_short_rows_against_the_total_is_a_hard_failure(self):
        """행이 빠졌는데 총계는 온전한 상태 = 응답이 잘린 것. Comtrade 에서 이 상황을
        탐지하지 못해 말레이시아 CAGR 이 +6.7% 대신 +187% 로 나왔다."""
        body = xml([("2025.01", "3304991000", "기초화장용", 100)], total=350)
        with with_response(body):
            with self.assertRaises(kcs.CustomsError) as cm:
                kcs.fetch(country="US", hs="330499", start="202501", end="202502")
        self.assertIn("무결성", str(cm.exception))
        self.assertIn("쓰지 마세요", str(cm.exception))

    def test_no_total_row_is_tolerated(self):
        """총계가 없는 응답도 있을 수 있다. 그때는 검증을 못 할 뿐 실패는 아니다."""
        with with_response(xml([("2025.01", "3304991000", "기초", 100)])):
            rows = kcs.fetch(country="US", hs="330499", start="202501", end="202501")
        self.assertEqual(len(rows), 1)

    def test_verification_runs_before_prefix_filtering(self):
        """접두어로 걸러낸 뒤에 총계와 대조하면 정상 응답이 전부 실패한다."""
        body = xml([("2025.01", "3304991000", "기초", 100),
                    ("2025.01", "0101219000", "말", 900)], total=1000)
        with with_response(body):
            rows = kcs.fetch(country="US", start="202501", end="202501", hs_prefix="3304")
        self.assertEqual([r["hs"] for r in rows], ["3304991000"])


class TestErrorMapping(unittest.TestCase):
    def test_agency_error_code_becomes_a_readable_message(self):
        with with_response(xml([], result="03", msg="인증에 실패하였습니다.")):
            with self.assertRaises(kcs.CustomsError) as cm:
                kcs.fetch(country="US", start="202501", end="202501")
        self.assertIn("TRADE_STATS_CUSTOMS_KEY", str(cm.exception))

    def test_gateway_error_has_a_different_schema_and_is_still_read(self):
        """포털 게이트웨이 실패는 resultCode 가 아예 없는 다른 문서로 온다."""
        body = (b'<OpenAPI_ServiceResponse><cmmMsgHeader>'
                b'<errMsg>SERVICE ERROR</errMsg>'
                b'<returnAuthMsg>LIMITED_NUMBER_OF_SERVICE_REQUESTS_EXCEEDS_ERROR</returnAuthMsg>'
                b'<returnReasonCode>22</returnReasonCode></cmmMsgHeader></OpenAPI_ServiceResponse>')
        with with_response(body):
            with self.assertRaises(kcs.CustomsError) as cm:
                kcs.fetch(country="US", start="202501", end="202501")
        self.assertIn("일일 호출 한도", str(cm.exception))

    def test_parameter_rejection_without_a_result_code_still_raises(self):
        body = ('<?xml version="1.0"?><response><header><resultCode></resultCode>'
                '<resultMsg>시작과 종료의 조회기간은 1년이내 기간만 가능합니다.</resultMsg>'
                '</header><body><items/></body></response>').encode("utf-8")
        with with_response(body):
            with self.assertRaises(kcs.CustomsError) as cm:
                kcs.fetch(country="US", start="202501", end="202501")
        self.assertIn("1년이내", str(cm.exception))

    def test_missing_key_names_the_exact_steps(self):
        with mock.patch.dict("os.environ", {"TRADE_STATS_CUSTOMS_KEY": ""}, clear=False):
            with self.assertRaises(kcs.CustomsKeyMissing) as cm:
                kcs.service_key()
        msg = str(cm.exception)
        self.assertIn("data.go.kr", msg)
        self.assertIn("TRADE_STATS_CUSTOMS_KEY", msg)


class TestServiceKeyForm(unittest.TestCase):
    """포털은 인코딩 키와 디코딩 키를 나란히 보여주고 어느 쪽을 쓰라고 말해주지 않는다."""

    # 진짜 키를 흉내 낸 값이 아니라 형태만 같은 합성 값이다. 포털 키는 base64라
    # `+` `/` `=` 가 섞여 나오고, 그 세 글자가 이 테스트의 전부다.
    RAW = "SAMPLE+FAKE/KEY+FOR/TESTS+ONLY/abcdefgh=="
    ENC = urllib.parse.quote(RAW, safe="")

    def test_both_forms_produce_the_same_request_key(self):
        with mock.patch.dict("os.environ", {"TRADE_STATS_CUSTOMS_KEY": self.RAW}):
            a = kcs._encoded_key()
        with mock.patch.dict("os.environ", {"TRADE_STATS_CUSTOMS_KEY": self.ENC}):
            b = kcs._encoded_key()
        self.assertEqual(a, b)

    def test_an_encoded_key_is_not_encoded_twice(self):
        """이중 인코딩이면 % 가 %25 가 되어 '등록되지 않은 키'로 튕긴다 — 키는 맞는데
        키가 틀렸다는 메시지가 나와서 원인을 찾기 어렵다."""
        with mock.patch.dict("os.environ", {"TRADE_STATS_CUSTOMS_KEY": self.ENC}):
            self.assertNotIn("%25", kcs._encoded_key())


class TestPeriodSplitting(unittest.TestCase):
    def test_a_span_longer_than_a_year_is_split(self):
        """API 가 13개월 요청을 거절한다. 사용자가 아니라 클라이언트가 나눠야 한다."""
        self.assertEqual(kcs._spans("202401", "202412"), [("202401", "202412")])
        self.assertEqual(kcs._spans("202401", "202501"),
                         [("202401", "202412"), ("202501", "202501")])
        self.assertEqual(len(kcs._spans("202401", "202607")), 3)

    def test_every_split_span_is_within_the_api_limit(self):
        for a, b in kcs._spans("202001", "202607"):
            self.assertLessEqual(kcs._ym_index(b) - kcs._ym_index(a) + 1,
                                 kcs.MAX_SPAN_MONTHS)

    def test_reversed_range_is_rejected_before_a_call(self):
        with self.assertRaises(kcs.CustomsError):
            kcs._spans("202512", "202501")

    def test_bad_month_is_rejected(self):
        for bad in ("2025", "202513", "202500", "20250101"):
            with self.subTest(bad=bad), self.assertRaises(kcs.CustomsError):
                kcs._ym(bad)


class TestCountryCode(unittest.TestCase):
    def test_non_iso2_is_rejected_locally(self):
        """관세청은 이상한 국가코드에도 resultCode 00 으로 답한다(실측: cntyCd=ZZ 가
        26행을 반환). 서버가 안 막으니 클라이언트가 막아야 한다."""
        for bad in ("USA", "410", "미국", ""):
            with self.subTest(bad=bad), self.assertRaises(kcs.CustomsError):
                kcs.fetch(country=bad, start="202501", end="202501")


class TestDrillToTenDigits(unittest.TestCase):
    """API 는 요청보다 정확히 한 단계 아래로만 분해한다 — 실측: 2→4, 4→6, 6→10, 미지정→10.
    HSK 10단위를 원하면 6자리를 넣어야 하는데, 사용자는 6자리를 모른다."""

    def test_six_digit_input_needs_one_call(self):
        with mock.patch.object(kcs, "fetch", return_value=[{"hs": "3304991000"}]) as f:
            kcs.drill(country="US", hs="330499", start="202501", end="202501")
        self.assertEqual(f.call_count, 1)

    def test_four_digit_input_discovers_children_then_fetches_each(self):
        calls = []

        def fake(*, country, start, end, hs=None, hs_prefix=None, use_cache=True):
            calls.append(hs)
            if hs == "3304":
                return [{"hs": "330410"}, {"hs": "330499"}]
            return [{"hs": (hs or "") + "1000"}]

        with mock.patch.object(kcs, "fetch", side_effect=fake):
            rows = kcs.drill(country="US", hs="3304", start="202501", end="202501")
        self.assertEqual(calls, ["3304", "330410", "330499"])
        self.assertEqual({r["hs"] for r in rows}, {"3304101000", "3304991000"})

    def test_chapter_uses_one_bulk_call_instead_of_forty(self):
        """챕터를 끝까지 파면 1+7+40 콜이다. 전 품목 덤프는 한 콜이고 이미 10단위다."""
        seen = {}

        def fake(*, country, start, end, hs=None, hs_prefix=None, use_cache=True):
            seen["hs"], seen["prefix"] = hs, hs_prefix
            return [{"hs": "3304991000"}]

        with mock.patch.object(kcs, "fetch", side_effect=fake) as f:
            kcs.drill(country="US", hs="33", start="202501", end="202501")
        self.assertEqual(f.call_count, 1)
        self.assertIsNone(seen["hs"])
        self.assertEqual(seen["prefix"], "33")

    def test_odd_code_lengths_are_rejected(self):
        for bad in ("3", "330", "33049", "330499100"):
            with self.subTest(bad=bad), self.assertRaises(kcs.CustomsError):
                kcs.drill(country="US", hs=bad, start="202501", end="202501")


class TestParsing(unittest.TestCase):
    def test_dash_and_blank_numerics_become_none_not_zero(self):
        """'-' 를 0 으로 읽으면 '보고 안 함'이 '수출 없음'으로 바뀐다."""
        body = ('<?xml version="1.0"?><response><header><resultCode>00</resultCode>'
                '<resultMsg>OK</resultMsg></header><body><items><item>'
                "<expDlr>-</expDlr><expWgt></expWgt><impDlr>5</impDlr><impWgt>-</impWgt>"
                "<balPayments>-</balPayments><hsCd>3304991000</hsCd><statCd>US</statCd>"
                "<statCdCntnKor1>미국</statCdCntnKor1><statKor>기초</statKor>"
                "<year>2025.01</year></item></items></body></response>").encode("utf-8")
        with with_response(body):
            rows = kcs.fetch(country="US", start="202501", end="202501")
        self.assertIsNone(rows[0]["export_usd"])
        self.assertIsNone(rows[0]["export_kg"])
        self.assertEqual(rows[0]["import_usd"], 5)

    def test_korean_item_name_comes_from_the_api_not_a_local_index(self):
        """statKor 이 응답에 들어 있어서 HSK 한국어 색인을 따로 관리하지 않아도 된다."""
        with with_response(xml([("2025.01", "3304991000", "기초화장용 제품류", 1)])):
            rows = kcs.fetch(country="US", start="202501", end="202501")
        self.assertEqual(rows[0]["item_name_ko"], "기초화장용 제품류")

    def test_non_xml_body_fails_loudly(self):
        with with_response(b"<html>503 Service Unavailable</html>"):
            with self.assertRaises(kcs.CustomsError):
                kcs.fetch(country="US", start="202501", end="202501")


class TestCacheKey(unittest.TestCase):
    def test_service_key_is_scrubbed_from_the_cache_key(self):
        """키를 캐시 키에 넣으면 키를 갱신하는 순간 캐시가 통째로 죽는다."""
        a = kcs._cache_path("https://x/y?serviceKey=AAA&cntyCd=US")
        b = kcs._cache_path("https://x/y?serviceKey=BBB&cntyCd=US")
        self.assertEqual(a, b)

    def test_different_queries_do_not_collide(self):
        a = kcs._cache_path("https://x/y?serviceKey=A&cntyCd=US")
        b = kcs._cache_path("https://x/y?serviceKey=A&cntyCd=JP")
        self.assertNotEqual(a, b)


if __name__ == "__main__":
    unittest.main()
