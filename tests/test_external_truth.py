"""숫자가 실제와 맞는지 본다. 나머지 스위트가 구조적으로 못 하는 일이다.

오프라인 스위트는 픽스처를 재생하므로 픽스처가 곧 정답이고, `test_live` 는 응답의
'모양'만 본다. 둘 다 통과하면서 값이 통째로 틀릴 수 있다 — v0.3.0 에서 잡은 500행
잘림 버그가 정확히 그랬다. 슬로베니아 HS3304 총수입이 $6.19억으로 나왔고(실제
$1.24억), 말레이시아 CAGR 이 +6.7% 대신 +187.5% 로 나왔는데, 리포트는 멀쩡해
보였고 트리거 테스트도 전부 통과했다. 그럴듯한 숫자를 반박할 기준점이 없었기 때문이다.

여기 테스트는 기준점 네 개를 세운다.

  1. 한국 reporter 절대값을 관세청 공표치와 대조한다 (tests/external_truth.json)
  2. 대형 양국 교역에서 미러 비율이 밴드를 벗어나지 않는지 본다
  3. 여러 보고국에서 파트너 합계가 World 행과 맞는지 훑는다
  4. 상위권 성장률이 실물에서 가능한 크기인지 본다

네트워크가 필요하므로 `test_live` 와 같은 스위치를 쓴다.

    TRADE_STATS_LIVE=1 python3 -m unittest test_external_truth -v
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

TESTS = Path(__file__).resolve().parent
SCRIPTS = TESTS.parent / "plugins" / "trade-stats" / "skills" / "trade-stats-lookup" / "scripts"
sys.path.insert(0, str(SCRIPTS))

LIVE = os.environ.get("TRADE_STATS_LIVE") == "1"
TRUTH = json.loads((TESTS / "external_truth.json").read_text(encoding="utf-8"))


@unittest.skipUnless(LIVE, "TRADE_STATS_LIVE=1 을 설정해야 실행됩니다")
class TestAgainstPublishedKoreanStatistics(unittest.TestCase):
    """Comtrade 의 한국 reporter 데이터는 관세청이 UN 에 제출한 것이다.

    따라서 관세청 공표치와 일치해야 한다. 어긋나면 우리 파싱이 깨졌거나 Comtrade 가
    단위·범위·집계를 바꾼 것이고, 둘 다 조용히 틀린 리포트를 낳는다.
    """

    @classmethod
    def setUpClass(cls):
        import comtrade as ct
        cls.ct = ct
        # 개발자의 데워진 캐시를 읽으면 깨진 API 를 못 본다.
        ct.CACHE_DIR = Path(tempfile.mkdtemp(prefix="trade-truth-"))

    def test_korea_export_matches_the_published_figure(self):
        for anchor in TRUTH["korea_export"]:
            src = TRUTH["sources"][anchor["source"]]
            with self.subTest(hs=anchor["hs"], year=anchor["year"]):
                rows = self.ct.fetch(freq="A", period=anchor["year"],
                                     reporter=self.ct.KOREA, partner=0,
                                     hs=anchor["hs"], flow="X")
                self.assertTrue(rows, f"{anchor['hs']} {anchor['year']} 한국 수출이 비어 있다")
                got = rows[0]["value_usd"]
                want = anchor["value_usd"]
                drift = abs(got - want) / want
                self.assertLessEqual(
                    drift, anchor["tolerance"],
                    f"\n  공표치  {want:>18,.0f}  ({src['title']}, {src['published']})"
                    f"\n  Comtrade {got:>18,.0f}"
                    f"\n  차이 {drift:.2%} > 허용 {anchor['tolerance']:.2%}"
                    f"\n  → 우리 파싱이 깨졌거나 Comtrade 가 단위·범위를 바꿨다. 둘 다 즉시 확인할 것.")


@unittest.skipUnless(LIVE, "TRADE_STATS_LIVE=1 을 설정해야 실행됩니다")
class TestMirrorStaysWithinBand(unittest.TestCase):
    """한국이 신고한 대X 수출과 X 가 신고한 대한국 수입은 원리상 같은 거래다.

    FOB/CIF 차이·통관 시점·경유 재수출 때문에 정확히 같지는 않다. 실측(2026-08-28,
    HS3304·3907 2024)으로 대형 교역은 0.87~1.14 안에 들어왔다. 밴드를 넉넉히 [0.6,
    1.5] 로 잡아도, 500행 잘림 같은 오염은 배수로 튀기 때문에 여기서 걸린다.

    소액 교역은 한 건의 선적이 비율을 흔들어 노이즈가 크므로(슬로베니아 3304 는
    1.86 이었다) 하한 이상만 본다.
    """

    MIN_FLOW_USD = 100_000_000
    BAND = (0.6, 1.5)
    PARTNERS = {"미국": 842, "일본": 392, "중국": 156, "베트남": 704, "독일": 276}

    @classmethod
    def setUpClass(cls):
        import comtrade as ct
        cls.ct = ct
        ct.CACHE_DIR = Path(tempfile.mkdtemp(prefix="trade-mirror-"))

    def test_large_bilateral_flows_agree_within_the_band(self):
        checked = 0
        for hs in ("3304", "3907"):
            kr = {r["partner_code"]: r["value_usd"] for r in self.ct.fetch(
                freq="A", period=2024, reporter=self.ct.KOREA, partner=None,
                hs=hs, flow="X")}
            for name, code in self.PARTNERS.items():
                exported = kr.get(code)
                if not exported or exported < self.MIN_FLOW_USD:
                    continue
                rows = self.ct.fetch(freq="A", period=2024, reporter=code,
                                     partner=self.ct.KOREA, hs=hs, flow="M")
                if not rows:
                    continue  # 상대국이 2024년을 아직 안 올린 경우 (베트남이 그렇다)
                ratio = rows[0]["value_usd"] / exported
                checked += 1
                with self.subTest(hs=hs, partner=name):
                    self.assertTrue(
                        self.BAND[0] <= ratio <= self.BAND[1],
                        f"\n  {name} HS{hs} 2024"
                        f"\n  한국 신고 수출  {exported:>15,.0f}"
                        f"\n  상대국 신고 수입 {rows[0]['value_usd']:>15,.0f}"
                        f"\n  비율 {ratio:.3f} 이 밴드 {self.BAND} 밖이다."
                        f"\n  → 한쪽 다리가 오염됐을 가능성이 높다. 총수입 행부터 확인할 것.")
        self.assertGreaterEqual(checked, 4, "검사된 조합이 너무 적어 이 테스트는 아무것도 보증하지 못한다")


@unittest.skipUnless(LIVE, "TRADE_STATS_LIVE=1 을 설정해야 실행됩니다")
class TestPartnerSumsReconcileAcrossReporters(unittest.TestCase):
    """`test_comtrade` 에도 같은 대조가 있지만 인도 한 나라만 본다.

    500행 잘림은 '어느 나라에서 터지는지' 미리 알 수 없는 종류의 사고였다. 한 나라만
    지켜보면 다른 나라에서 같은 일이 나도 모른다. 넓게 훑는 것이 요점이다.
    """

    REPORTERS = {"미국": 842, "일본": 392, "중국": 156, "독일": 276, "프랑스": 251,
                 "폴란드": 616, "인도": 699, "멕시코": 484, "브라질": 76, "튀르키예": 792}

    @classmethod
    def setUpClass(cls):
        import comtrade as ct
        cls.ct = ct
        ct.CACHE_DIR = Path(tempfile.mkdtemp(prefix="trade-reconcile-"))

    def test_every_reporter_sums_to_its_own_world_row(self):
        reconciled = 0
        for name, code in self.REPORTERS.items():
            # partner=None 은 상대국 행과 World 행을 같이 돌려준다. World 를 안 걸러내면
            # 커버리지가 정확히 2.0 이 되고, 그건 오염이 아니라 이 줄을 빠뜨린 것이다.
            rows = [r for r in self.ct.fetch(freq="A", period=2024, reporter=code,
                                             partner=None, hs="3304", flow="M")
                    if r["partner_code"] not in (self.ct.WORLD, None)]
            world = self.ct.fetch(freq="A", period=2024, reporter=code,
                                  partner=0, hs="3304", flow="M")
            if not rows or not world or not world[0]["value_usd"]:
                continue
            coverage = sum(r["value_usd"] or 0 for r in rows) / world[0]["value_usd"]
            reconciled += 1
            with self.subTest(reporter=name):
                self.assertGreater(
                    coverage, 0.97,
                    f"\n  {name} HS3304 2024 커버리지 {coverage:.1%}"
                    f"\n  → 응답이 잘렸다. 파트너 행이 빠진 채로 합계가 만들어지고 있다.")
                self.assertLessEqual(
                    coverage, 1.001,
                    f"\n  {name} HS3304 2024 커버리지 {coverage:.1%}"
                    f"\n  → 합계가 World 행을 넘었다. 내역행이 중복 합산되고 있다"
                    f" (운송수단·통관구분·2차 상대국 축을 안 접었을 때 나오는 증상).")
        self.assertGreaterEqual(reconciled, 6,
                                "대조된 보고국이 너무 적어 이 테스트는 아무것도 보증하지 못한다")


@unittest.skipUnless(LIVE, "TRADE_STATS_LIVE=1 을 설정해야 실행됩니다")
class TestGrowthRatesArePhysicallyPossible(unittest.TestCase):
    """오염의 지문은 '말이 안 되게 큰 성장률'이었다.

    v0.2.7 리포트에서 튀르키예 +116.8%, 말레이시아 +187.5% 가 상위권에 올라왔다.
    한 나라의 특정 품목 총수입이 2년 만에 3배가 되는 일은 실물에서 거의 없다.
    그래서 절대 못 넘는 선이 아니라 '이걸 넘으면 사람이 봐야 한다'는 선을 긋는다.
    """

    CEILING = 1.0  # 2년 CAGR +100%

    @classmethod
    def setUpClass(cls):
        import comtrade as ct
        cls.ct = ct
        ct.CACHE_DIR = Path(tempfile.mkdtemp(prefix="trade-growth-"))

    def test_no_major_market_doubles_its_imports_every_year(self):
        suspects = []
        for name, code in TestPartnerSumsReconcileAcrossReporters.REPORTERS.items():
            new = self.ct.fetch(freq="A", period=2025, reporter=code, partner=0,
                                hs="3304", flow="M")
            old = self.ct.fetch(freq="A", period=2023, reporter=code, partner=0,
                                hs="3304", flow="M")
            if not new or not old or not old[0]["value_usd"]:
                continue
            cagr = (new[0]["value_usd"] / old[0]["value_usd"]) ** 0.5 - 1
            if cagr > self.CEILING:
                suspects.append(f"{name} {cagr:+.1%} "
                                f"({old[0]['value_usd']:,.0f} → {new[0]['value_usd']:,.0f})")
        self.assertFalse(
            suspects,
            "\n  실물에서 나오기 어려운 성장률이다. 총수입 행이 오염됐는지 먼저 볼 것:\n  "
            + "\n  ".join(suspects))


if __name__ == "__main__":
    unittest.main()
