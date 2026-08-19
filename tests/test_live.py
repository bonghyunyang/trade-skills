"""Live contract tests against the real Comtrade endpoint.

Skipped unless TRADE_STATS_LIVE=1, because they need network and are paced at
~2s per call. Run them when a report looks wrong, before a release, or on a
schedule — they are the early warning for the brief's top risk, "API 스펙 변경 →
스크립트 파손". The offline suite cannot catch that: it replays recordings.

    TRADE_STATS_LIVE=1 python3 -m unittest test_live -v
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "plugins" / "trade-stats" / \
    "skills" / "trade-stats-lookup" / "scripts"
sys.path.insert(0, str(SCRIPTS))

LIVE = os.environ.get("TRADE_STATS_LIVE") == "1"


@unittest.skipUnless(LIVE, "TRADE_STATS_LIVE=1 을 설정해야 실행됩니다")
class TestLiveContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import comtrade as ct
        cls.ct = ct
        # Never read the developer's warm cache — that would hide a broken API.
        ct.CACHE_DIR = Path(tempfile.mkdtemp(prefix="trade-live-"))

    def test_endpoint_answers_without_an_api_key(self):
        """The entire product depends on this staying keyless."""
        rows = self.ct.fetch(freq="A", period=2024, reporter=410, partner=0,
                             hs="3907", flow="X")
        self.assertTrue(rows, "한국의 2024년 HS3907 총수출이 비어 있을 수 없다")
        self.assertGreater(rows[0]["value_usd"], 0)

    def test_response_still_carries_the_fields_we_parse(self):
        rows = self.ct.fetch(freq="A", period=2024, reporter=410, partner=None,
                             hs="3907", flow="X")
        row = rows[0]
        for key in ("period", "partner_code", "value_usd", "net_weight_kg", "hs"):
            with self.subTest(field=key):
                self.assertIn(key, row)

    def test_all_partners_in_one_call_still_works(self):
        """The country-ranking feature is one call; if this ever needs
        pagination the cost model changes completely."""
        rows = self.ct.fetch(freq="A", period=2024, reporter=410, partner=None,
                             hs="3907", flow="X")
        self.assertGreater(len(rows), 50)

    def test_monthly_still_accepts_only_one_period(self):
        """If this limit ever lifts, monthly collection gets ~24x cheaper and
        collect_monthly should be rewritten."""
        import urllib.parse
        url = self.ct.BASE_URL.format(freq="M") + "?" + urllib.parse.urlencode(
            {"reporterCode": 410, "period": "202401,202402", "cmdCode": "3907",
             "flowCode": "X", "partnerCode": 0})
        with self.assertRaises(self.ct.ComtradeError) as cm:
            self.ct._get(url, use_cache=False)
        self.assertIn("400", str(cm.exception))

    def test_mirror_data_still_resolves_korea_as_a_supplier(self):
        rows = self.ct.fetch(freq="A", period=2024, reporter=392, partner=None,
                             hs="3907", flow="M")
        codes = {r["partner_code"] for r in rows}
        self.assertIn(self.ct.KOREA, codes, "일본의 HS3907 수입에 한국이 없을 수 없다")

    def test_taiwan_code_490_still_carries_data_and_158_does_not(self):
        live = self.ct.fetch(freq="A", period=2024, reporter=410, partner=490,
                             hs="3907", flow="X")
        dead = self.ct.fetch(freq="A", period=2024, reporter=410, partner=158,
                             hs="3907", flow="X")
        self.assertTrue(live)
        self.assertFalse(dead, "158에 데이터가 생겼다면 CODE_REDIRECTS를 재검토할 것")

    def test_reference_snapshots_still_match_the_upstream_lists(self):
        """areas.json / hs.json drift silently. A mismatch means it is time to
        run scripts/refresh_reference.py."""
        import json
        import urllib.request
        with urllib.request.urlopen(
                "https://comtradeapi.un.org/files/v1/app/reference/Reporters.json",
                timeout=90) as r:
            upstream = json.load(r)["results"]
        local = [a for a in self.ct.areas() if a.get("reporter")]
        self.assertEqual(
            len(local), len(upstream),
            "보고국 수가 달라졌습니다. `python3 scripts/refresh_reference.py codes` 를 실행하세요.")


if __name__ == "__main__":
    unittest.main()


@unittest.skipUnless(LIVE, "TRADE_STATS_LIVE=1 을 설정해야 실행됩니다")
@unittest.skipUnless(os.environ.get("TRADE_STATS_CUSTOMS_KEY"),
                     "TRADE_STATS_CUSTOMS_KEY 가 있어야 실행됩니다 (관세청은 무인증 티어가 없음)")
class TestLiveCustomsContract(unittest.TestCase):
    """관세청 API 계약. 이 스킬이 의존하는 성질이 네 가지 있고 전부 문서에 없다.

    1) 응답이 요청보다 정확히 한 단계 아래로 분해된다 (6자리 → 10자리)
    2) 총계 행이 같이 와서 무결성 검증이 가능하다
    3) 기술문서상 '최대 메시지 4000 byte' 가 실제로는 적용되지 않는다
    4) 한글 품목명이 응답에 들어 있다 (로컬 색인 불필요)

    하나라도 바뀌면 조용히 틀린 숫자가 나오므로 주기적으로 확인한다.
    """

    @classmethod
    def setUpClass(cls):
        import customs as kcs
        cls.kcs = kcs
        cls.kcs.CACHE_DIR = Path(tempfile.mkdtemp(prefix="customs-live-"))

    def test_six_digit_request_still_returns_ten_digit_lines(self):
        rows = self.kcs.fetch(country="US", hs="330499",
                              start="202501", end="202503")
        self.assertTrue(rows)
        self.assertEqual({len(r["hs"]) for r in rows}, {10},
                         "6자리 요청이 10자리로 분해되지 않으면 domestic 의 전제가 깨진다")

    def test_total_row_still_arrives_and_reconciles(self):
        """_verify 가 이 행에 의존한다. 사라지면 검증이 조용히 무력화된다."""
        rows = self.kcs.fetch(country="US", hs="3304", start="202501", end="202512")
        self.assertTrue(rows)  # _verify 는 fetch 안에서 이미 돌았다

    def test_documented_4kb_cap_is_still_not_enforced(self):
        """문서는 4,000 byte 라는데 실측 21MB 가 온다. 정말 4KB 로 조여지면
        전 품목 조회가 조용히 잘리므로 즉시 알아야 한다."""
        rows = self.kcs.fetch(country="US", start="202501", end="202501")
        self.assertGreater(len(rows), 1000,
                           "전 품목 응답이 급감했다면 서버가 상한을 걸기 시작한 것이다")

    def test_korean_item_names_are_still_included(self):
        rows = self.kcs.fetch(country="US", hs="330499", start="202501", end="202501")
        self.assertTrue(all(r["item_name_ko"] for r in rows))

    def test_range_over_twelve_months_is_still_rejected_by_the_server(self):
        """_spans 가 이 제약 때문에 존재한다. 풀리면 콜 수를 줄일 수 있다."""
        import urllib.parse, urllib.request
        params = {"strtYymm": "202412", "endYymm": "202512", "cntyCd": "US", "hsSgn": "3304"}
        url = (f"{self.kcs.BASE_URL}?serviceKey={self.kcs._encoded_key()}"
               f"&{urllib.parse.urlencode(params)}")
        body = self.kcs._get(url)
        self.assertIn("1년이내", body.decode("utf-8", "replace"))

