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
