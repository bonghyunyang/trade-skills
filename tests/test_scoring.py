"""Scoring tests.

Every case here is a defect that produced a confident, plausible-looking number
pointing at the wrong country. Scoring bugs are the dangerous kind: the report
still reads fine, so nobody checks it.
"""

from __future__ import annotations

import unittest

from context import analyze


def entry(name, *, size=None, cagr=None, share=None, kr_export=None):
    """Build the minimal entry shape score_markets() consumes."""
    return {
        "name": name,
        "size_usd": size,
        "growth_cagr": cagr,
        "korea_share_pct": share,
        "kr_export_usd": kr_export if kr_export is not None else size,
        "market_size_usd": size,
    }


def scores(entries):
    analyze.score_markets(entries)
    return {e["name"]: e["attractiveness_score"] for e in entries}


class TestSingleCountry(unittest.TestCase):
    """Min-max normalizing one value collapses every axis to 0.5, so the score
    was always exactly 50.0 — for a booming market and a dead one alike."""

    def test_one_country_gets_no_score(self):
        entries = [entry("베트남", size=1e9, cagr=0.2, share=25.0)]
        self.assertIsNone(scores(entries)["베트남"])
        self.assertEqual(entries[0]["score_basis"], "n/a")
        self.assertIn("1개", entries[0]["score_note"])

    def test_one_country_still_keeps_its_raw_metrics(self):
        entries = [entry("베트남", size=1e9, cagr=0.2, share=25.0)]
        analyze.score_markets(entries)
        self.assertEqual(entries[0]["market_size_usd"], 1e9)
        self.assertEqual(entries[0]["korea_share_pct"], 25.0)


class TestMeasurementParity(unittest.TestCase):
    """Countries measured on different axis sets must not share a ranking."""

    def test_country_without_market_size_is_excluded_not_ranked_last(self):
        """The size axis once fell back to Korea's export value, ~10x smaller
        than a market total. The USA — Korea's largest destination — scored 0.0
        and sorted below Japan."""
        entries = [
            entry("일본", size=2.22e9, cagr=-0.018, share=11.3),
            entry("베트남", size=1.87e9, cagr=-0.002, share=12.8),
            entry("미국", size=None, cagr=-0.042, share=None, kr_export=7.4e8),
        ]
        result = scores(entries)
        self.assertIsNone(result["미국"], "측정 불가 국가는 점수를 받지 않는다")
        self.assertIsNotNone(result["일본"])
        self.assertIsNotNone(result["베트남"])
        us = next(e for e in entries if e["name"] == "미국")
        self.assertEqual(us["score_basis"], "unscored")
        self.assertIn("순위에서 제외", us["score_note"])

    def test_data_poor_country_cannot_win_on_one_lucky_axis(self):
        """Libya, measured on growth alone, took first place at 100.0 over real
        markets scored on all three axes."""
        entries = [
            entry("미국", size=7.47e9, cagr=0.131, share=24.8),
            entry("베트남", size=3.11e8, cagr=-0.125, share=40.9),
            entry("리비아", size=None, cagr=0.328, share=None, kr_export=3.6e6),
        ]
        result = scores(entries)
        self.assertIsNone(result["리비아"])
        ranked = sorted((e for e in entries if e["attractiveness_score"] is not None),
                        key=lambda e: e["attractiveness_score"], reverse=True)
        self.assertEqual(ranked[0]["name"], "미국")

    def test_all_countries_unmeasurable_yields_no_scores_and_no_crash(self):
        entries = [entry("리비아", size=None, cagr=0.3),
                   entry("시리아", size=None, cagr=0.1)]
        self.assertEqual(set(scores(entries).values()), {None})


class TestComparabilityWarnings(unittest.TestCase):
    def test_small_comparison_sets_carry_a_warning(self):
        """With three countries the axes stretch across the full 0-100 range,
        making a narrow real gap look decisive."""
        entries = [entry("A", size=1e9, cagr=0.1, share=10.0),
                   entry("B", size=9e8, cagr=0.09, share=11.0),
                   entry("C", size=8e8, cagr=0.08, share=12.0)]
        analyze.score_markets(entries)
        self.assertTrue(all(e.get("score_note") for e in entries))
        self.assertIn("3개국", entries[0]["score_note"])

    def test_large_comparison_sets_drop_the_small_set_warning(self):
        entries = [entry(f"C{i}", size=1e9 - i * 1e7, cagr=0.1, share=10.0)
                   for i in range(6)]
        analyze.score_markets(entries)
        self.assertFalse(any("개국뿐이라" in (e.get("score_note") or "") for e in entries))

    def test_rank_instability_is_disclosed_at_every_set_size(self):
        """Dropping one unrelated country from a real ten-country run flipped
        four pairwise orderings. Min-max normalization makes that inherent, so
        the caveat belongs on every result, not just small ones."""
        entries = [entry(f"C{i}", size=1e9 - i * 1e7, cagr=0.1 * i, share=5.0 * i)
                   for i in range(6)]
        analyze.score_markets(entries)
        scored = [e for e in entries if e["attractiveness_score"] is not None]
        self.assertTrue(scored)
        for e in scored:
            self.assertIn("순위 자체가 뒤집힐 수 있습니다", e["score_note"])


class TestAxisBehaviour(unittest.TestCase):
    def test_bigger_market_scores_higher_all_else_equal(self):
        entries = [entry("큰시장", size=1e10, cagr=0.1, share=10.0),
                   entry("작은시장", size=1e7, cagr=0.1, share=10.0)]
        r = scores(entries)
        self.assertGreater(r["큰시장"], r["작은시장"])

    def test_faster_growth_scores_higher_all_else_equal(self):
        entries = [entry("성장", size=1e9, cagr=0.30, share=10.0),
                   entry("정체", size=1e9, cagr=-0.10, share=10.0)]
        r = scores(entries)
        self.assertGreater(r["성장"], r["정체"])

    def test_more_headroom_scores_higher_all_else_equal(self):
        entries = [entry("여유있음", size=1e9, cagr=0.1, share=2.0),
                   entry("포화", size=1e9, cagr=0.1, share=80.0)]
        r = scores(entries)
        self.assertGreater(r["여유있음"], r["포화"])

    def test_weights_are_documented_on_every_entry(self):
        entries = [entry("A", size=1e9, cagr=0.1, share=10.0),
                   entry("B", size=5e8, cagr=0.2, share=20.0)]
        analyze.score_markets(entries)
        w = entries[0]["score_components"]["weights"]
        self.assertEqual((w["size"], w["growth"], w["headroom"]), (0.40, 0.35, 0.25))
        self.assertAlmostEqual(sum(w.values()), 1.0)

    def test_missing_growth_axis_excludes_rather_than_renormalizing(self):
        """Renormalizing over the surviving axes rewards absent data.

        Measured on a real HS8507 run: India scored 49.7 (5th) carrying a
        -29.3% CAGR, and 68.9 (3rd) with that same CAGR merely missing. A bad
        number was punished; no number was not. Any entry short of all three
        axes is excluded instead.
        """
        entries = [entry("A", size=1e9, cagr=None, share=10.0),
                   entry("B", size=5e8, cagr=0.2, share=20.0),
                   entry("C", size=7e8, cagr=0.1, share=15.0)]
        analyze.score_markets(entries)
        a = next(e for e in entries if e["name"] == "A")
        self.assertIsNone(a["attractiveness_score"])
        self.assertEqual(a["score_basis"], "unscored")
        self.assertIn("성장률", a["score_note"])

    def test_missing_data_can_never_outrank_a_measured_bad_value(self):
        """The invariant behind the fix, stated directly."""
        def rank_of(target, cagr):
            entries = [entry("타깃", size=4.95e9, cagr=cagr, share=1.4),
                       entry("큰시장", size=27.2e9, cagr=-0.125, share=13.7),
                       entry("성장시장", size=1.14e9, cagr=0.464, share=2.1),
                       entry("보통", size=3.67e9, cagr=-0.106, share=13.7)]
            analyze.score_markets(entries)
            scored = sorted((e for e in entries if e["attractiveness_score"] is not None),
                            key=lambda e: -e["attractiveness_score"])
            names = [e["name"] for e in scored]
            return names.index(target) if target in names else None

        self.assertIsNotNone(rank_of("타깃", -0.293), "실측 CAGR이면 순위에 들어야 한다")
        self.assertIsNone(rank_of("타깃", None), "결측 CAGR은 순위를 받을 수 없다")

    def test_realized_influence_is_reported_alongside_nominal_weights(self):
        """Nominal 25% on headroom meant 5.9% of actual rank movement when every
        country's Korea share sat between 1% and 15%. Publishing only the
        nominal split overstates what that axis did."""
        entries = [entry("A", size=1e10, cagr=0.5, share=10.0),
                   entry("B", size=1e7, cagr=-0.3, share=11.0),
                   entry("C", size=1e9, cagr=0.1, share=10.5)]
        analyze.score_markets(entries)
        infl = entries[0]["score_components"]["realized_influence"]
        self.assertAlmostEqual(sum(infl.values()), 1.0, places=2)
        self.assertLess(infl["headroom"], 0.25,
                        "점유율이 거의 같은 비교군에서 여유 축은 명목 25%보다 작게 작동해야 한다")


class TestDerivedMetrics(unittest.TestCase):
    def test_cagr(self):
        self.assertAlmostEqual(analyze.cagr(100, 121, 2), 0.1, places=6)
        self.assertIsNone(analyze.cagr(0, 100, 2))
        self.assertIsNone(analyze.cagr(100, None, 2))
        self.assertIsNone(analyze.cagr(100, 121, 0))

    def test_unit_price_guards_against_missing_weight(self):
        self.assertAlmostEqual(analyze.unit_price(100.0, 50.0), 2.0)
        for value, weight in ((100.0, 0), (100.0, None), (None, 50.0)):
            with self.subTest(value=value, weight=weight):
                self.assertIsNone(analyze.unit_price(value, weight))


if __name__ == "__main__":
    unittest.main()
