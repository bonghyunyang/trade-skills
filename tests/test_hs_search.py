"""Korean HS-code search.

The target user is a Korean sales rep who types a product name, not an HS code
and not English. If '화장품' returns nothing, the skill is unusable for them no
matter how good the analysis behind it is.
"""

from __future__ import annotations

import unittest

from context import ct


def codes(keyword, **kw):
    return [r["code"] for r in ct.search_hs(keyword, **kw)]


class TestKoreanSearch(unittest.TestCase):
    def test_common_product_words_resolve(self):
        for word, expected in [
            ("화장품", "3304"),
            ("마스크팩", "3304"),
            ("향수", "3303"),
            ("샴푸", "3305"),
            ("이차전지", "8507"),
            ("배터리", "8507"),
            ("반도체", "8542"),
            ("라면", "1902"),
            ("자동차부품", "8708"),
            ("승용차", "8703"),
            ("타이어", "4011"),
            ("기저귀", "4818"),
            ("골프채", "9506"),
            ("스테인리스", "7219"),
            ("의료기기", "9018"),
            ("에어컨", "8415"),
            ("전선", "8544"),
            ("가방", "4202"),
            ("운동화", "6404"),
            ("소주", "2208"),
        ]:
            with self.subTest(word=word):
                self.assertIn(expected, codes(word))

    def test_accessory_does_not_resolve_to_the_device(self):
        """"휴대폰케이스" contains "휴대폰". A first-match rule sent phone cases
        to 8517 (handsets) — the report would then describe a completely
        different product while looking perfectly normal. Cases are 3926
        (plastics) or 4202 (leather)."""
        for word in ("핸드폰케이스", "휴대폰케이스", "폰케이스", "스마트폰케이스"):
            with self.subTest(word=word):
                self.assertEqual(codes(word)[0], "3926")

    def test_the_device_itself_still_resolves_to_the_device(self):
        """The fix for the line above must not invert: a plain "휴대폰" query
        should still land on handsets, not on cases."""
        for word in ("휴대폰", "스마트폰"):
            with self.subTest(word=word):
                self.assertIn(codes(word)[0], {"85", "8517"})
                self.assertNotEqual(codes(word)[0], "3926")

    def test_korean_hits_rank_above_english_coincidences(self):
        results = ct.search_hs("화장품")
        self.assertTrue(results)
        self.assertEqual(results[0]["matched"], "ko")

    def test_matches_report_which_keyword_fired(self):
        """The agent shows this to the user when confirming the code choice."""
        hit = next(r for r in ct.search_hs("이차전지") if r["code"] == "8507")
        self.assertEqual(hit["matched"], "ko")
        self.assertIn("이차전지", hit["ko_keyword"])

    def test_every_chapter_is_reachable_in_korean(self):
        """Chapter coverage is what makes 'which industry' always answerable."""
        index = ct.hs_ko_index()
        chapters = {c for c in index if len(c) == 2}
        self.assertGreaterEqual(len(chapters), 96)

    def test_partial_words_still_match(self):
        self.assertIn("3304", codes("화장"))

    def test_level_filter_still_applies(self):
        self.assertEqual(codes("화장품", level=4), ["3304"])
        self.assertEqual(codes("화장품", level=2), ["33"])


class TestEnglishSearch(unittest.TestCase):
    """The English path must keep working — it covers everything the curated
    Korean index does not."""

    def test_english_descriptions_are_searchable(self):
        self.assertIn("3304", codes("beauty"))
        self.assertIn("330499", codes("cosmetic", level=6))

    def test_multiword_english_narrows_results(self):
        self.assertTrue(codes("optical fibre"))

    def test_nonsense_returns_empty_rather_than_raising(self):
        self.assertEqual(codes("ㅁㄴㅇㄹ존재하지않는단어"), [])


class TestIndexIntegrity(unittest.TestCase):
    def test_every_indexed_code_exists_in_the_hs_table(self):
        """A keyword pointing at a nonexistent code would send the user down a
        dead end that looks like 'no exports'."""
        known = {str(r["code"]) for r in ct.hs_table()}
        unknown = [c for c in ct.hs_ko_index() if c not in known]
        self.assertEqual(unknown, [], f"HS 테이블에 없는 코드: {unknown}")

    def test_index_has_no_empty_keyword_sets(self):
        empty = [c for c, w in ct.hs_ko_index().items() if not w.strip()]
        self.assertEqual(empty, [])


if __name__ == "__main__":
    unittest.main()
