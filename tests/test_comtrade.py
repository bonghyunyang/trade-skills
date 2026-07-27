"""Client-layer tests: code resolution, HS validation, response normalization.

Each test here corresponds to a defect that shipped silently at least once.
"""

from __future__ import annotations

import unittest

import context
from context import ct


class TestAreaResolution(unittest.TestCase):
    """Comtrade lists dissolved states next to current ones, sharing ISO3.

    '독일' resolved to 280 (West Germany, dissolved 1990) and '베트남' to 868
    (Republic of Vietnam, dissolved 1974). Both return zero rows forever, which
    reads as "this country buys nothing from Korea".
    """

    def test_current_state_wins_over_dissolved(self):
        for token, expected, label in [
            ("베트남", 704, "Viet Nam vs Rep. of Vietnam (...1974)"),
            ("vietnam", 704, "영문 입력"),
            ("VNM", 704, "ISO3 충돌"),
            ("독일", 276, "Germany vs Fed. Rep. of Germany (...1990)"),
            ("germany", 276, "영문 입력"),
            ("인도", 699, "India vs India (...1974)"),
            ("IND", 699, "ISO3 충돌"),
            ("벨기에", 56, "Belgium vs Belgium-Luxembourg (...1998)"),
            ("수단", 729, "Sudan vs Sudan (...2011)"),
            ("파키스탄", 586, "Pakistan vs East and West Pakistan (...1971)"),
            ("예멘", 887, "Yemen vs Arab Rep. of Yemen (...1990)"),
            ("파나마", 591, "Panama vs Panama, excl.Canal Zone (...1977)"),
            ("에티오피아", 231, "Ethiopia vs Ethiopia (...1992)"),
        ]:
            with self.subTest(token=token, why=label):
                area = ct.resolve_area(token)
                self.assertEqual(area["code"], expected)
                self.assertFalse(area.get("historical"))

    def test_reporter_wins_over_non_reporting_variant(self):
        """'USA'(842) carries the data; 'United States of America'(840) does not.
        Same for Metropolitan France, the space-suffixed Switzerland, and the
        Svalbard-excluding Norway."""
        for token, expected in [("미국", 842), ("usa", 842), ("프랑스", 251),
                                ("france", 251), ("스위스", 757), ("노르웨이", 579)]:
            with self.subTest(token=token):
                self.assertEqual(ct.resolve_area(token)["code"], expected)

    def test_taiwan_redirects_to_the_code_that_holds_data(self):
        """Taiwan is listed as 158 but every transaction is booked under 490
        'Other Asia, nes'. Resolving to 158 returns zero rows silently."""
        for token in ("대만", "taiwan", "TW", "TWN", "158"):
            with self.subTest(token=token):
                self.assertEqual(ct.resolve_area(token)["code"], 490)

    def test_display_names_are_korean(self):
        self.assertEqual(ct.resolve_area("VN")["name"], "베트남")
        self.assertEqual(ct.area_name(842), "미국")
        self.assertIn("대만", ct.area_name(490))

    def test_genuinely_ambiguous_input_raises_rather_than_guessing(self):
        with self.assertRaises(ct.ComtradeError) as cm:
            ct.resolve_area("United")
        self.assertIn("여러 국가", str(cm.exception))

    def test_unknown_country_names_the_recovery_command(self):
        with self.assertRaises(ct.ComtradeError) as cm:
            ct.resolve_area("엘프왕국")
        self.assertIn("country-search", str(cm.exception))

    def test_numeric_and_world_tokens(self):
        self.assertEqual(ct.resolve_area(398)["code"], 398)
        self.assertEqual(ct.resolve_area("398")["code"], 398)
        self.assertEqual(ct.resolve_area("전세계")["code"], ct.WORLD)


class TestHsValidation(unittest.TestCase):
    def test_accepts_2_4_6_digits(self):
        for code in ("39", "3907", "390710"):
            with self.subTest(code=code):
                self.assertEqual(ct.validate_hs(code), code)

    def test_rejects_national_subdivisions_with_a_usable_suggestion(self):
        """HSK 10-digit input is the single most likely thing a Korean exporter
        will paste, and Comtrade only carries 6."""
        with self.assertRaises(ct.ComtradeError) as cm:
            ct.validate_hs("3907101000")
        msg = str(cm.exception)
        self.assertIn("390710", msg)
        self.assertIn("관세청", msg)

    def test_rejects_nonexistent_codes_instead_of_reporting_zero_exports(self):
        """A typo used to sail through and return empty rows from every call,
        indistinguishable from a real zero."""
        with self.assertRaises(ct.ComtradeError) as cm:
            ct.validate_hs("1234")
        self.assertIn("존재하지 않는", str(cm.exception))

    def test_suggests_the_parent_chapter_when_one_exists(self):
        with self.assertRaises(ct.ComtradeError) as cm:
            ct.validate_hs("3999")
        self.assertIn("'39'", str(cm.exception))

    def test_rejects_odd_lengths_and_non_numeric(self):
        for bad in ("390", "39071", "abc"):
            with self.subTest(bad=bad):
                with self.assertRaises(ct.ComtradeError):
                    ct.validate_hs(bad)


class TestBreakdownCollapse(unittest.TestCase):
    """Some reporters return a partner total *and* its mode-of-transport
    breakdown. Counting those as separate suppliers inflated Vietnam's import
    total and halved Korea's measured share (40.9% reported as 20.4%)."""

    def test_keeps_only_the_aggregate_row(self):
        rows = [
            {"period": "2023", "partnerCode": 410, "cmdCode": "3304", "flowCode": "M",
             "motCode": 0, "partner2Code": 0, "customsCode": "C00", "mosCode": "0",
             "primaryValue": 127145600.973},
            {"period": "2023", "partnerCode": 410, "cmdCode": "3304", "flowCode": "M",
             "motCode": 2100, "partner2Code": 0, "customsCode": "C00", "mosCode": "0",
             "primaryValue": 110185142.042},
            {"period": "2023", "partnerCode": 410, "cmdCode": "3304", "flowCode": "M",
             "motCode": 1000, "partner2Code": 0, "customsCode": "C00", "mosCode": "0",
             "primaryValue": 16942330.466},
        ]
        out = ct._collapse_breakdowns(rows)
        self.assertEqual(len(out), 1)
        self.assertAlmostEqual(out[0]["primaryValue"], 127145600.973)

    def test_sums_breakdowns_when_no_aggregate_row_is_present(self):
        rows = [
            {"period": "2023", "partnerCode": 410, "cmdCode": "3304", "flowCode": "M",
             "motCode": 2100, "primaryValue": 100.0, "netWgt": 10.0},
            {"period": "2023", "partnerCode": 410, "cmdCode": "3304", "flowCode": "M",
             "motCode": 1000, "primaryValue": 25.0, "netWgt": 4.0},
        ]
        out = ct._collapse_breakdowns(rows)
        self.assertEqual(len(out), 1)
        self.assertAlmostEqual(out[0]["primaryValue"], 125.0)
        self.assertAlmostEqual(out[0]["netWgt"], 14.0)
        self.assertEqual(out[0]["_summed_breakdown"], 2)

    def test_distinct_partners_are_never_merged(self):
        rows = [
            {"period": "2023", "partnerCode": 410, "cmdCode": "3304", "flowCode": "M",
             "motCode": 0, "primaryValue": 10.0},
            {"period": "2023", "partnerCode": 156, "cmdCode": "3304", "flowCode": "M",
             "motCode": 0, "primaryValue": 20.0},
        ]
        self.assertEqual(len(ct._collapse_breakdowns(rows)), 2)

    def test_vietnam_fixture_has_no_duplicate_partners(self):
        context.block_network()
        rows = ct.fetch(freq="A", period=2023, reporter=704, partner=None,
                        hs="3304", flow="M")
        codes = [r["partner_code"] for r in rows]
        self.assertEqual(len(codes), len(set(codes)), "상대국이 중복되면 점유율이 틀어진다")

    def test_korea_share_of_vietnam_matches_the_verified_value(self):
        context.block_network()
        rows = [r for r in ct.fetch(freq="A", period=2023, reporter=704, partner=None,
                                    hs="3304", flow="M")
                if r["partner_code"] not in (ct.WORLD, None)]
        world = ct.fetch(freq="A", period=2023, reporter=704, partner=0,
                         hs="3304", flow="M")
        total = world[0]["value_usd"]
        kr = next(r for r in rows if r["partner_code"] == ct.KOREA)
        self.assertAlmostEqual(100 * kr["value_usd"] / total, 40.86, places=1)

    def test_partner_sum_reconciles_with_the_reporters_world_row(self):
        """The cross-check that makes the 500-row cap measurable rather than
        merely suspected.

        Coverage is deliberately asserted as a range, not a constant. The same
        India request returns a *different* 500-row subset each time — measured
        at 97.04% and 100.00% on identical calls — because truncation can drop a
        partner's aggregate row and leave its transport breakdowns behind. The
        contract is "we detect and report the shortfall", not "the shortfall is
        always the same size".
        """
        context.block_network()
        rows = [r for r in ct.fetch(freq="A", period=2024, reporter=699, partner=None,
                                    hs="3907", flow="M")
                if r["partner_code"] not in (ct.WORLD, None)]
        world = ct.fetch(freq="A", period=2024, reporter=699, partner=0,
                         hs="3907", flow="M")
        coverage = sum(r["value_usd"] or 0 for r in rows) / world[0]["value_usd"]
        self.assertGreater(coverage, 0.90)
        self.assertLessEqual(coverage, 1.001)
        self.assertTrue(any(r.get("_truncated") for r in rows),
                        "인도 응답은 500행 상한에 걸려야 한다 (픽스처가 오래됐을 수 있음)")

    def test_undercounted_partners_are_flagged_not_silently_trusted(self):
        """When truncation removes a partner's aggregate row, the summed
        breakdowns understate that partner. The row must say so."""
        rows = [
            {"period": "2024", "partnerCode": 156, "cmdCode": "3907", "flowCode": "M",
             "motCode": 2100, "primaryValue": 100.0},
            {"period": "2024", "partnerCode": 156, "cmdCode": "3907", "flowCode": "M",
             "motCode": 1000, "primaryValue": 25.0},
        ]
        out = ct._collapse_breakdowns(rows)
        self.assertTrue(out[0].get("_summed_breakdown"))


class TestPeriodHelpers(unittest.TestCase):
    def test_month_range(self):
        self.assertEqual(ct.months("2024-11", "2025-02"),
                         ["202411", "202412", "202501", "202502"])

    def test_month_range_accepts_compact_form(self):
        self.assertEqual(ct.months("202401", "202401"), ["202401"])

    def test_month_range_rejects_bad_input(self):
        with self.assertRaises(ct.ComtradeError):
            ct.months("2024", "2025")

    def test_month_back_crosses_year_boundaries(self):
        self.assertEqual(analyze_month_back(2025, 1, 1), (2024, 12))
        self.assertEqual(analyze_month_back(2025, 1, 13), (2023, 12))
        self.assertEqual(analyze_month_back(2025, 6, 0), (2025, 6))


def analyze_month_back(y, m, n):
    from context import analyze
    return analyze._month_back(y, m, n)


class TestFetchNormalization(unittest.TestCase):
    def test_rejects_bad_freq_and_flow(self):
        with self.assertRaises(ct.ComtradeError):
            ct.fetch(freq="Q", period=2024, reporter=410, partner=0, hs="3907", flow="X")
        with self.assertRaises(ct.ComtradeError):
            ct.fetch(freq="A", period=2024, reporter=410, partner=0, hs="3907", flow="Z")

    def test_rows_carry_korean_partner_names_and_numeric_fields(self):
        context.block_network()
        rows = ct.fetch(freq="A", period=2025, reporter=410, partner=None,
                        hs="3907", flow="X")
        self.assertTrue(rows)
        row = rows[0]
        for key in ("period", "partner_code", "partner_name", "value_usd", "hs"):
            self.assertIn(key, row)

    def test_empty_response_is_an_empty_list_not_an_error(self):
        """Reporting gaps are normal; they must not look like failures."""
        context.block_network()
        self.assertEqual(ct.fetch(freq="A", period=2026, reporter=410, partner=0,
                                  hs="3907", flow="X"), [])


if __name__ == "__main__":
    unittest.main()
