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


class TestAbsoluteScale(unittest.TestCase):
    """Both axes are absolute. The old score min-max normalized size and growth
    across whichever countries happened to be in the run, so adding one
    unrelated country moved everyone's score — measured at up to 17.9pt, with
    the top pick changing in 7.1% of random subsets. Nothing here may depend on
    the comparison set."""

    def test_one_country_still_gets_a_score(self):
        entries = [entry("베트남", size=1e9, cagr=0.2, share=25.0)]
        self.assertIsNotNone(scores(entries)["베트남"])
        self.assertEqual(entries[0]["score_basis"], "full")

    def test_one_country_still_keeps_its_raw_metrics(self):
        entries = [entry("베트남", size=1e9, cagr=0.2, share=25.0)]
        analyze.score_markets(entries)
        self.assertEqual(entries[0]["market_size_usd"], 1e9)
        self.assertEqual(entries[0]["korea_share_pct"], 25.0)

    def test_score_does_not_move_when_other_countries_join_the_run(self):
        alone = [entry("베트남", size=1e9, cagr=0.05, share=25.0)]
        crowd = [entry("베트남", size=1e9, cagr=0.05, share=25.0),
                 entry("거대시장", size=5e10, cagr=0.45, share=1.0),
                 entry("죽은시장", size=2e8, cagr=-0.60, share=90.0)]
        self.assertEqual(scores(alone)["베트남"], scores(crowd)["베트남"])

    def test_score_is_comparable_across_separate_runs(self):
        """Same inputs, different runs, same number — that is what lets a user
        say '이 시장 70점' and have it mean one thing."""
        a = scores([entry("A", size=2e9, cagr=0.10, share=30.0),
                    entry("B", size=1e8, cagr=-0.30, share=5.0)])
        b = scores([entry("A", size=2e9, cagr=0.10, share=30.0),
                    entry("C", size=9e9, cagr=0.02, share=50.0)])
        self.assertEqual(a["A"], b["A"])

    def test_growth_saturates_at_the_published_band(self):
        r = scores([entry("폭발", size=1e9, cagr=5.0, share=10.0),
                    entry("상한", size=1e9, cagr=analyze.GROWTH_CEIL, share=10.0),
                    entry("붕괴", size=1e9, cagr=-0.9, share=10.0),
                    entry("하한", size=1e9, cagr=analyze.GROWTH_FLOOR, share=10.0)])
        self.assertEqual(r["폭발"], r["상한"])
        self.assertEqual(r["붕괴"], r["하한"])


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


class TestScoreNote(unittest.TestCase):
    def test_every_scored_entry_states_the_bands_it_was_measured_against(self):
        """An absolute score is only readable if its scale is published."""
        entries = [entry("A", size=1e9, cagr=0.1, share=10.0),
                   entry("B", size=9e8, cagr=0.09, share=11.0)]
        analyze.score_markets(entries)
        for e in entries:
            self.assertIn("절대 기준", e["score_note"])

    def test_note_does_not_tell_users_to_rerun_with_a_different_set(self):
        """The old note told users to rerun two or three times with different
        comparison sets. That advice was correct then and is noise now — the
        score cannot move. Leaving it in trains users to distrust a stable
        number."""
        entries = [entry(f"C{i}", size=1e9 - i * 1e7, cagr=0.1 * i, share=5.0 * i)
                   for i in range(6)]
        analyze.score_markets(entries)
        for e in entries:
            self.assertNotIn("뒤집", e["score_note"])


class TestAxisBehaviour(unittest.TestCase):
    def test_bigger_market_scores_higher_all_else_equal(self):
        entries = [entry("큰시장", size=1e9, cagr=0.1, share=10.0),
                   entry("작은시장", size=1e8, cagr=0.1, share=10.0)]
        r = scores(entries)
        self.assertGreater(r["큰시장"], r["작은시장"])

    def test_size_stops_deciding_the_ranking_above_the_ceiling(self):
        """The whole point of the ceiling. The old score tracked market size at
        Spearman +0.891 across a real ten-country run — four minutes of waiting
        to be told that big markets are big. Past the ceiling, growth decides."""
        entries = [entry("거대·정체", size=6e10, cagr=0.0, share=10.0),
                   entry("충분히큰·성장", size=2e10, cagr=0.18, share=10.0)]
        r = scores(entries)
        self.assertGreater(r["충분히큰·성장"], r["거대·정체"])

    def test_tiny_market_is_excluded_as_small_not_as_unmeasured(self):
        """'모른다'와 '안다, 작다'는 정반대다. 한 칸에 뭉뚱그리면 데이터 공백이
        나쁜 시장으로 읽힌다."""
        entries = [entry("초소형", size=5e6, cagr=0.5, share=10.0),
                   entry("정상", size=1e9, cagr=0.1, share=10.0)]
        analyze.score_markets(entries)
        tiny = next(e for e in entries if e["name"] == "초소형")
        self.assertIsNone(tiny["attractiveness_score"])
        self.assertEqual(tiny["score_basis"], "below_floor")
        self.assertIn("실제로 작은 시장", tiny["score_note"])

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

    def test_untapped_folds_size_and_headroom_into_one_dollar_figure(self):
        """A $10B market where Korea already holds 95% has less left on the
        table than a $1B market where Korea holds nothing. Adding size and
        headroom as separate axes let those two cancel; multiplying does not."""
        entries = [entry("큰데_포화", size=1e10, cagr=0.1, share=95.0),
                   entry("작은데_빈곳", size=1e9, cagr=0.1, share=0.0)]
        analyze.score_markets(entries)
        big, open_ = (next(e for e in entries if e["name"] == n)
                      for n in ("큰데_포화", "작은데_빈곳"))
        self.assertAlmostEqual(big["untapped_usd"], 5e8, delta=1.0)
        self.assertAlmostEqual(open_["untapped_usd"], 1e9, delta=1.0)
        self.assertGreater(open_["attractiveness_score"], big["attractiveness_score"])

    def test_weights_are_documented_on_every_entry(self):
        entries = [entry("A", size=1e9, cagr=0.1, share=10.0),
                   entry("B", size=5e8, cagr=0.2, share=20.0)]
        analyze.score_markets(entries)
        w = entries[0]["score_components"]["weights"]
        self.assertEqual((w["untapped"], w["growth"]), (0.5, 0.5))
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
        """Nominal weights state intent. An axis whose values barely differ in
        this run moves the ranking hardly at all — several countries pinned at
        the untapped ceiling put that axis in exactly that state."""
        entries = [entry("A", size=4e10, cagr=0.5, share=10.0),
                   entry("B", size=5e10, cagr=-0.3, share=10.0),
                   entry("C", size=6e10, cagr=0.1, share=10.0)]
        analyze.score_markets(entries)
        infl = entries[0]["score_components"]["realized_influence"]
        self.assertAlmostEqual(sum(infl.values()), 1.0, places=2)
        self.assertLess(infl["untapped"], 0.5,
                        "전부 상한에 걸린 비교군에서 여유 축은 명목 50%보다 작게 작동해야 한다")


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
