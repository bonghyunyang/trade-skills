"""End-to-end runs of `analyze.py market` against recorded fixtures.

These assert the contract the skill promises the calling agent: a JSON summary
it can narrate from, CSVs a salesperson can open, and a Korean report that never
presents an unmeasured country as a bad one.
"""

from __future__ import annotations

import contextlib
import csv
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

import context
from context import ct


def run_market(*args) -> dict:
    """Invoke the CLI in-process and return its JSON summary."""
    context.block_network()
    argv = ["analyze.py", "market", *args, "--quiet"]
    buf = io.StringIO()
    old = sys.argv
    try:
        sys.argv = argv
        with contextlib.redirect_stdout(buf):
            from context import analyze
            rc = analyze.main()
    finally:
        sys.argv = old
    payload = json.loads(buf.getvalue())
    payload["_rc"] = rc
    return payload


class TestMarketRun(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="trade-e2e-")
        cls.result = run_market("--hs", "3907", "--countries", "VN,US,JP",
                                "--years", "3", "--latest-year", "2025",
                                "--outdir", cls.tmp)
        # CSV is opt-in: the skill only passes --csv when the user asks for raw
        # data. The default run above must therefore stay CSV-free, so the CSV
        # contract is asserted against a second run in its own directory.
        cls.csv_tmp = tempfile.mkdtemp(prefix="trade-e2e-csv-")
        cls.csv_result = run_market("--hs", "3907", "--countries", "VN,US,JP",
                                    "--years", "3", "--latest-year", "2025",
                                    "--csv", "--outdir", cls.csv_tmp)

    def test_exits_clean(self):
        self.assertEqual(self.result["_rc"], 0)

    def test_reports_which_hs_and_years_were_used(self):
        self.assertEqual(self.result["hs"], "3907")
        self.assertIn("Polyacetals", self.result["hs_desc"])
        self.assertEqual(self.result["years"], [2023, 2024, 2025])

    def test_default_run_writes_the_report_and_no_unrequested_csv(self):
        names = set(self.result["files"])
        self.assertIn("hs3907_report.md", names)
        self.assertEqual([n for n in names if n.endswith(".csv")], [])

    def test_csv_flag_writes_the_files_a_salesperson_opens(self):
        names = set(self.csv_result["files"])
        self.assertIn("hs3907_markets.csv", names)
        self.assertIn("hs3907_annual_series.csv", names)
        self.assertIn("hs3907_columns.md", names)

    def test_csv_opens_in_excel_without_mojibake(self):
        """UTF-8 BOM is what makes Excel render Korean headers correctly."""
        raw = (Path(self.csv_tmp) / "hs3907_markets.csv").read_bytes()
        self.assertTrue(raw.startswith(b"\xef\xbb\xbf"))

    def test_every_country_is_ranked_with_a_stated_basis(self):
        for row in self.result["ranking"]:
            with self.subTest(country=row["country"]):
                self.assertIn(row["score_basis"],
                              {"full", "unscored", "below_floor"})

    def test_country_names_are_korean(self):
        names = {r["country"] for r in self.result["ranking"]}
        self.assertEqual(names, {"베트남", "미국", "일본"})

    def test_scored_countries_sort_above_unscored_ones(self):
        seen_unscored = False
        for row in self.result["ranking"]:
            if row["score"] is None:
                seen_unscored = True
            elif seen_unscored:
                self.fail("순위 있는 국가가 순위제외 국가 뒤에 왔다")

    def test_korea_share_is_a_percentage_not_a_fraction(self):
        for row in self.result["ranking"]:
            if row["korea_share_pct"] is not None:
                self.assertGreaterEqual(row["korea_share_pct"], 0)
                self.assertLessEqual(row["korea_share_pct"], 100)

    def test_stale_mirror_years_are_disclosed(self):
        """Vietnam has no 2025 or 2024 mirror for this code; the run must fall
        back to 2023 and say which year it actually used."""
        vn = next(r for r in self.result["ranking"] if r["country"] == "베트남")
        self.assertIsNotNone(vn["top_competitors"])
        report = (Path(self.tmp) / "hs3907_report.md").read_text(encoding="utf-8")
        self.assertIn("2023년 공급국 점유율", report)

    def test_report_states_the_data_limits(self):
        report = (Path(self.tmp) / "hs3907_report.md").read_text(encoding="utf-8")
        for phrase in ("기업 단위 데이터는 여기에 없다", "HS 6단위", "FOB", "CIF"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, report)

    def test_report_warns_that_share_excludes_domestic_producers(self):
        """The easiest way to misread this report: treating '한국 점유율 53%,
        1위' as market share when it only covers imports. In Vietnam's instant
        noodle market the domestic makers that actually dominate are absent from
        the data entirely. Readers rarely open the reference docs, so the report
        itself has to say it."""
        report = (Path(self.tmp) / "hs3907_report.md").read_text(encoding="utf-8")
        self.assertIn("시장 점유율", report)
        self.assertIn("현지 제조사", report)

    def test_report_publishes_the_absolute_bands_behind_the_score(self):
        """The score is an absolute grade now, so the report has to say what
        scale it is on — otherwise '70점' is unreadable."""
        report = (Path(self.tmp) / "hs3907_report.md").read_text(encoding="utf-8")
        self.assertIn("두 축 모두 절대 기준", report)
        self.assertIn("다른 조회에서 나온 점수와도 비교", report)

    def test_ranking_table_names_the_incumbent_supplier(self):
        """A 1.4% Korean share reads as headroom until you see China holds 87%.
        The incumbent belongs in the ranking table, not three sections down —
        a bold score always beats a footnote."""
        report = (Path(self.tmp) / "hs3907_report.md").read_text(encoding="utf-8")
        self.assertIn("1위 공급국", report)
        for row in self.result["ranking"]:
            if row["korea_share_pct"] is not None:
                with self.subTest(country=row["country"]):
                    self.assertIsNotNone(row["top_supplier"])

    def test_dominated_markets_are_flagged(self):
        for row in self.result["ranking"]:
            share = row.get("top_supplier_share_pct")
            if share is not None and row["top_supplier"] != "한국":
                with self.subTest(country=row["country"]):
                    self.assertEqual(row["dominated"], share >= 60)

    def test_growth_axis_measures_the_market_not_korea(self):
        """The growth axis once carried Korea's own export CAGR. A shrinking
        market where Korea rebounded off a low base then scored a perfect 1.0 —
        that is what ranked Hong Kong above the United States on HS8507, with
        Hong Kong's market contracting 5% while Korean exports rose 86%."""
        for row in self.result["ranking"]:
            if row["score"] is None:
                continue
            with self.subTest(country=row["country"]):
                self.assertIsNotNone(row["market_cagr"],
                                     "점수를 받은 국가는 시장 CAGR이 있어야 한다")

    def test_report_shows_both_cagrs_side_by_side(self):
        """Market growth and Korea's growth answer different questions, and the
        gap between them is the interesting part."""
        report = (Path(self.tmp) / "hs3907_report.md").read_text(encoding="utf-8")
        self.assertIn("시장 CAGR", report)
        self.assertIn("한국 수출 CAGR", report)

    def test_mirror_discrepancy_is_detected(self):
        """Both sides of the same trade are already fetched, so comparing them
        costs nothing. They should agree within the FOB/CIF margin. Korea's
        HS3304 exports to Kyrgyzstan are 9.3x what Kyrgyzstan reports importing
        from Korea — that gap made its market look flat when its statistics were
        simply missing the volume. Major partners sit at 0.8-1.1, so the 2x
        threshold separates cleanly and does not fire on normal trade."""
        for row in self.result["ranking"]:
            ratio = row.get("mirror_ratio")
            if ratio is None:
                continue
            with self.subTest(country=row["country"]):
                flagged = row.get("mirror_gap_note") is not None
                self.assertEqual(flagged, ratio >= 2 or ratio <= 0.5)

    def test_major_partners_do_not_trip_the_mirror_check(self):
        ratios = [r["mirror_ratio"] for r in self.result["ranking"]
                  if r.get("mirror_ratio") is not None]
        self.assertTrue(ratios, "미러 비율이 하나도 계산되지 않았다")
        for r in ratios:
            self.assertGreater(r, 0.5)
            self.assertLess(r, 2.0)

    def test_report_publishes_realized_axis_influence(self):
        """The nominal 50/50 split states intent. What actually moved this
        ranking can be far from it — countries pinned at the untapped ceiling
        make that axis near-constant — so both numbers have to appear."""
        report = (Path(self.tmp) / "hs3907_report.md").read_text(encoding="utf-8")
        self.assertIn("실제로 순위를 움직인 비중", report)

    def test_annual_series_csv_has_one_row_per_country_year(self):
        with (Path(self.csv_tmp) / "hs3907_annual_series.csv").open(encoding="utf-8-sig") as fh:
            rows = list(csv.DictReader(fh))
        self.assertEqual(len(rows), 9)  # 3 countries x 3 years


class TestUnmeasurableTarget(unittest.TestCase):
    """Libya reports to Comtrade but has no mirror data for HS3907."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="trade-e2e-ly-")
        cls.result = run_market("--hs", "3907", "--countries", "US,JP,LY",
                                "--years", "3", "--latest-year", "2025",
                                "--outdir", cls.tmp)

    def test_run_succeeds_despite_the_gap(self):
        self.assertEqual(self.result["_rc"], 0)

    def test_libya_is_excluded_from_ranking_with_a_reason(self):
        ly = next(r for r in self.result["ranking"] if "리비아" in r["country"])
        self.assertIsNone(ly["score"])
        self.assertTrue(ly["score_note"] or ly["competitor_note"])

    def test_report_marks_it_as_unmeasured_not_as_worst(self):
        """'측정불가'(모른다)와 '규모 미달'(안다, 작다)은 정반대 뜻이라 표에서
        같은 칸을 쓰면 안 된다."""
        report = (Path(self.tmp) / "hs3907_report.md").read_text(encoding="utf-8")
        self.assertIn("측정불가", report)
        self.assertIn("비교할 수 없다", report)

    def test_the_other_countries_still_get_real_scores(self):
        scored = [r for r in self.result["ranking"] if r["score"] is not None]
        self.assertEqual(len(scored), 2)


class TestInputErrors(unittest.TestCase):
    """A wrong code must not look like an empty market."""

    def test_nonexistent_hs_code_fails_before_spending_calls(self):
        result = run_market("--hs", "1234", "--countries", "VN",
                            "--outdir", tempfile.mkdtemp())
        self.assertEqual(result["_rc"], 1)
        self.assertIn("존재하지 않는", result["message"])

    def test_hsk_ten_digit_input_is_redirected_to_six(self):
        result = run_market("--hs", "3907101000", "--countries", "VN",
                            "--outdir", tempfile.mkdtemp())
        self.assertEqual(result["_rc"], 1)
        self.assertIn("390710", result["message"])

    def test_unknown_country_fails_with_a_next_step(self):
        result = run_market("--hs", "3907", "--countries", "엘프왕국",
                            "--outdir", tempfile.mkdtemp())
        self.assertEqual(result["_rc"], 1)
        self.assertIn("country-search", result["message"])


if __name__ == "__main__":
    unittest.main()
