"""World-wide discovery scan.

The scan is the only part of the skill that asks Comtrade about many reporters
at once, and that is where the preview API's 500-row cap turns into wrong
numbers rather than missing ones. Every case here is a real defect that shipped
a confident total which was off by a multiple.
"""

from __future__ import annotations

import unittest
from unittest import mock

import context
from context import analyze
from context import ct


def rows(*specs):
    """(reporter, partner, value, partial) -> the shape fetch() returns."""
    return [{"reporter_code": r, "partner_code": p, "value_usd": v,
             "is_partial_sum": partial, "_truncated": truncated}
            for r, p, v, partial, truncated in specs]


class TestAggregateReporters(unittest.TestCase):
    def test_eu_and_asean_are_not_offered_as_destinations(self):
        """They are sums of their members, so they sort straight to the top of
        a table their own members are also in. 'European Union' outranked
        France and Italy in a real run. Nobody can fly to the European Union."""
        codes = {a["code"] for a in analyze.discover_reporters()}
        self.assertNotIn(97, codes, "EU 집계 코드가 대상국에 남아 있다")
        self.assertNotIn(975, codes, "ASEAN 집계 코드가 대상국에 남아 있다")

    def test_korea_is_not_its_own_export_destination(self):
        self.assertNotIn(analyze.KOREA, {a["code"] for a in analyze.discover_reporters()})

    def test_taiwan_survives_the_filter(self):
        """Taiwan books under 'Other Asia, nes' (490), which has no ISO2 and
        looks like an aggregate. It is a real market and must stay."""
        self.assertIn(490, {a["code"] for a in analyze.discover_reporters()})


class TestTruncationHandling(unittest.TestCase):
    """A truncated response must never yield a total."""

    def test_summed_breakdown_is_refetched_instead_of_trusted(self):
        """Slovenia returns 500 rows of partner2 breakdown and no aggregate
        row. Summing those gave $6.19억 against a true $1.24억 — five times
        over, not under. Undercounting was the anticipated failure; this one
        reads as a booming market that does not exist.
        """
        calls = []

        def fake_fetch(*, freq, period, reporter, partner, hs, flow, use_cache=True):
            calls.append((str(reporter), str(partner)))
            if "," in str(partner):
                # World+Korea in one call: 500 rows of partner2 detail, no
                # aggregate row, so the collapse layer hands back a sum.
                return rows((705, 0, 618_625_521.0, True, True),
                            (705, 410, 3_231_269.0, False, True))
            if str(partner) == "0":
                return rows((705, 0, 123_985_726.0, False, None))
            return rows((705, 410, 3_231_269.0, False, None))

        with mock.patch.object(ct, "fetch", side_effect=fake_fetch):
            out = analyze.scan_world("3304", 2025, [705], lambda *_: None)

        self.assertAlmostEqual(out[705]["total"], 123_985_726.0)
        self.assertFalse(out[705]["partial"])
        self.assertIn(("705", "0"), calls, "상대국별 분리 조회로 폴백하지 않았다")

    def test_only_the_incomplete_reporters_are_refetched(self):
        """Halving the batch and re-asking for everything turned one truncated
        response into up to fifteen calls; a real run logged 55 splits and had
        not finished after fifteen minutes. Rows already in hand are complete."""
        calls = []

        def fake_fetch(*, freq, period, reporter, partner, hs, flow, use_cache=True):
            asked = [int(c) for c in str(reporter).split(",")]
            calls.append(asked)
            if len(asked) > 1:
                # 10 and 20 answered cleanly; 30 got cut off entirely
                return rows((10, 0, 5e8, False, True), (10, 410, 1e8, False, True),
                            (20, 0, 4e8, False, True), (20, 410, 2e7, False, True))
            return rows((asked[0], 0, 3e8, False, None), (asked[0], 410, 1e7, False, None))

        with mock.patch.object(ct, "fetch", side_effect=fake_fetch):
            out = analyze.scan_world("3304", 2025, [10, 20, 30], lambda *_: None)

        self.assertEqual(set(out), {10, 20, 30})
        self.assertAlmostEqual(out[10]["total"], 5e8)
        self.assertAlmostEqual(out[30]["total"], 3e8)
        refetched = [c for c in calls[1:] if len(c) == 1]
        self.assertTrue(all(c == [30] for c in refetched),
                        f"이미 받은 국가까지 다시 불렀다: {refetched}")

    def test_a_reporter_that_only_ever_publishes_detail_is_kept_and_flagged(self):
        """Cyprus has no aggregate row even alone. Dropping it loses a real
        market; trusting it silently is what this whole class is about. Keep
        the number, carry the flag."""
        def fake_fetch(*, freq, period, reporter, partner, hs, flow, use_cache=True):
            if "," in str(partner):
                return rows((196, 0, 605_068_052.0, True, True),
                            (196, 410, 5_709_621.0, False, True))
            if str(partner) == "0":
                return rows((196, 0, 605_068_052.0, True, None))
            return rows((196, 410, 5_709_621.0, False, None))

        with mock.patch.object(ct, "fetch", side_effect=fake_fetch):
            out = analyze.scan_world("3304", 2025, [196], lambda *_: None)

        self.assertAlmostEqual(out[196]["total"], 605_068_052.0)
        self.assertTrue(out[196]["partial"], "집계 불확실 표시가 사라졌다")

    def test_an_untruncated_batch_costs_exactly_one_call(self):
        calls = []

        def fake_fetch(*, freq, period, reporter, partner, hs, flow, use_cache=True):
            calls.append(reporter)
            return rows((10, 0, 5e8, False, None), (10, 410, 1e8, False, None),
                        (20, 0, 4e8, False, None), (20, 410, 2e7, False, None))

        with mock.patch.object(ct, "fetch", side_effect=fake_fetch):
            analyze.scan_world("3304", 2025, [10, 20], lambda *_: None)
        self.assertEqual(len(calls), 1)


class TestDiscoverReportFile(unittest.TestCase):
    """스캔 결과가 세션 안에만 있으면 안 된다.

    실측에서 스캔이 백그라운드로 넘어간 사이 턴이 끝나 사용자는 아무것도 못 받았다.
    캐시가 있으니 재실행은 빠르지만, 그건 다시 물어봐야 한다는 뜻이지 결과를 들고
    있다는 뜻이 아니다.
    """

    def summary(self):
        return {
            "hs": "3304", "hs_desc": "beauty preparations",
            "latest_year": 2025, "base_year": 2023,
            "reporters_scanned": 225, "passed_min_market": 79,
            "min_market_usd": 10_000_000.0,
            "ranking": [
                {"name": "키프로스", "iso2": "CY", "attractiveness_score": 79.6,
                 "untapped_usd": 599_380_413.0, "market_size_usd": 605_068_052.0,
                 "market_cagr": 1.64, "market_cagr_span": "2023–2025",
                 "kr_import_usd": 5_709_621.0, "korea_share_pct": 0.94,
                 "tags": ["미개척", "고성장", "집계주의"]},
            ],
            "score_note": None,
            "method_note": "최신 연도만 전량 스캔했다.",
            "next_step": "후보를 좁힌 뒤 market 으로 넘어가라.",
            "limits": ["점유율은 수입 중 점유율이다."],
            "data_source": "UN Comtrade",
        }

    def test_report_carries_the_tags_and_the_scan_range(self):
        text = analyze.build_discover_report(self.summary())
        self.assertIn("키프로스", text)
        self.assertIn("집계주의", text)
        self.assertIn("225개국", text)
        self.assertIn("후보를 좁힌 뒤", text)

    def test_report_states_what_the_scan_cannot_answer(self):
        """순위만 남기면 '1위 나라로 가라'로 읽힌다. 경쟁 구도가 없다는 사실이
        표와 같은 파일에 있어야 한다."""
        text = analyze.build_discover_report(self.summary())
        self.assertIn("이 표가 답하지 않는 것", text)
        self.assertIn("점유율은 수입 중 점유율이다", text)


class TestScanShape(unittest.TestCase):
    def test_market_size_and_korea_share_come_from_one_statistic(self):
        """Korea's declared exports are FOB and the importer's are CIF, so
        dividing one by the other bakes in a 5-15% error. Asking for World and
        Korea in the same call keeps both sides on the importer's CIF basis."""
        seen = {}

        def fake_fetch(*, freq, period, reporter, partner, hs, flow, use_cache=True):
            seen["partner"] = str(partner)
            seen["flow"] = flow
            return rows((10, 0, 1e9, False, None), (10, 410, 1e8, False, None))

        with mock.patch.object(ct, "fetch", side_effect=fake_fetch):
            out = analyze.scan_world("3304", 2025, [10], lambda *_: None)

        self.assertEqual(seen["flow"], "M", "수입 신고 기준이어야 미러가 성립한다")
        self.assertIn("0", seen["partner"].split(","))
        self.assertIn(str(analyze.KOREA), seen["partner"].split(","))
        self.assertAlmostEqual(out[10]["total"], 1e9)
        self.assertAlmostEqual(out[10]["from_korea"], 1e8)


if __name__ == "__main__":
    unittest.main()
