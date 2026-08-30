"""Failure-path tests.

A tool that makes twenty-odd network calls per run fails partway through
sometimes. What matters is that a salesperson gets the eight countries that did
work, plus an honest note about the one that didn't — not an empty terminal.
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import socket
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path

import context
from context import analyze, ct


class TestPerCountryFailureIsolation(unittest.TestCase):
    """A mid-run failure used to discard every country already collected."""

    def setUp(self):
        self.original = analyze.collect_competitors
        self.tmp = tempfile.mkdtemp(prefix="trade-fail-")
        context.block_network()

    def tearDown(self):
        analyze.collect_competitors = self.original

    def _run(self, fail_on_call: int) -> dict:
        calls = {"n": 0}
        original = self.original

        def flaky(hs, area, year, log):
            calls["n"] += 1
            if calls["n"] == fail_on_call:
                raise ct.ComtradeError("시뮬레이션: upstream 500")
            return original(hs, area, year, log)

        analyze.collect_competitors = flaky
        buf = io.StringIO()
        argv = sys.argv
        try:
            sys.argv = ["analyze.py", "market", "--hs", "3907", "--hs4-ok",
                        "--countries", "VN,US,JP", "--years", "3",
                        "--latest-year", "2025", "--outdir", self.tmp, "--quiet"]
            with contextlib.redirect_stdout(buf):
                rc = analyze.main()
        finally:
            sys.argv = argv
        payload = json.loads(buf.getvalue())
        payload["_rc"] = rc
        return payload

    def test_report_is_still_produced(self):
        result = self._run(fail_on_call=2)
        self.assertEqual(result["_rc"], 0)
        self.assertTrue((Path(self.tmp) / "hs3907_report.md").exists())

    def test_surviving_countries_keep_their_full_scores(self):
        result = self._run(fail_on_call=2)
        scored = [r for r in result["ranking"] if r["score"] is not None]
        self.assertEqual(len(scored), 2)
        self.assertTrue(all(r["score_basis"] == "full" for r in scored))

    def test_failed_country_is_excluded_and_names_the_failure(self):
        result = self._run(fail_on_call=2)
        failed = [r for r in result["ranking"] if r["score"] is None]
        self.assertEqual(len(failed), 1)
        self.assertIn("조회 실패", failed[0]["competitor_note"])

    def test_failure_on_the_first_country_still_yields_a_report(self):
        result = self._run(fail_on_call=1)
        self.assertEqual(result["_rc"], 0)
        self.assertEqual(len([r for r in result["ranking"] if r["score"] is not None]), 2)


class TestNetworkFailFast(unittest.TestCase):
    """DNS failure retried five times with backoff cost 61s per call — long
    enough that a user assumes the tool hung."""

    def setUp(self):
        self.base = ct.BASE_URL
        self.cache = ct.CACHE_DIR
        ct.CACHE_DIR = Path(tempfile.mkdtemp()) / "empty"

    def tearDown(self):
        ct.BASE_URL = self.base
        ct.CACHE_DIR = self.cache

    def test_name_resolution_failure_aborts_immediately(self):
        def refuse(url, *a, **kw):
            raise urllib.error.URLError(socket.gaierror(8, "nodename nor servname provided"))

        original = ct.urllib.request.urlopen
        ct.urllib.request.urlopen = refuse
        try:
            with self.assertRaises(ct.ComtradeError) as cm:
                ct.fetch(freq="A", period=2024, reporter=410, partner=0,
                         hs="3907", flow="X")
            self.assertIn("인터넷 연결", str(cm.exception))
        finally:
            ct.urllib.request.urlopen = original

    def test_transient_server_errors_are_retried_then_reported(self):
        attempts = {"n": 0}

        def flaky(url, *a, **kw):
            attempts["n"] += 1
            raise urllib.error.HTTPError(url, 503, "Service Unavailable", {}, None)

        original = ct.urllib.request.urlopen
        ct.urllib.request.urlopen = flaky
        old_retries, ct.MAX_RETRIES = ct.MAX_RETRIES, 2
        try:
            with self.assertRaises(ct.ComtradeError):
                ct.fetch(freq="A", period=2024, reporter=410, partner=0,
                         hs="3907", flow="X")
            self.assertEqual(attempts["n"], 2, "5xx는 재시도되어야 한다")
        finally:
            ct.urllib.request.urlopen = original
            ct.MAX_RETRIES = old_retries

    def test_client_errors_are_not_retried(self):
        attempts = {"n": 0}

        def bad_request(url, *a, **kw):
            attempts["n"] += 1
            raise urllib.error.HTTPError(url, 400, "Bad Request", {}, io.BytesIO(b"nope"))

        original = ct.urllib.request.urlopen
        ct.urllib.request.urlopen = bad_request
        try:
            with self.assertRaises(ct.ComtradeError):
                ct.fetch(freq="A", period=2024, reporter=410, partner=0,
                         hs="3907", flow="X")
            self.assertEqual(attempts["n"], 1, "400은 재시도할 이유가 없다")
        finally:
            ct.urllib.request.urlopen = original


class TestRateLimitCourtesy(unittest.TestCase):
    """This runs against an unauthenticated public tier. Backing off on our own
    schedule while ignoring what the server asked for is the difference between
    respecting a limit and working around one."""

    def test_retry_after_header_is_honored(self):
        slept, attempts = [], {"n": 0}

        def limited(url, *a, **kw):
            attempts["n"] += 1
            raise urllib.error.HTTPError(url, 429, "Too Many Requests",
                                         {"Retry-After": "7"}, None)

        original_open = ct.urllib.request.urlopen
        original_sleep = ct.time.sleep
        old_retries, ct.MAX_RETRIES = ct.MAX_RETRIES, 2
        ct.urllib.request.urlopen = limited
        ct.time.sleep = lambda s: slept.append(s)
        try:
            with self.assertRaises(ct.ComtradeError):
                ct.fetch(freq="A", period=2024, reporter=410, partner=0,
                         hs="3907", flow="X", use_cache=False)
            self.assertTrue(any(s >= 7 for s in slept),
                            f"Retry-After 7초를 존중해야 한다 (실제 대기: {slept})")
        finally:
            ct.urllib.request.urlopen = original_open
            ct.time.sleep = original_sleep
            ct.MAX_RETRIES = old_retries

    def test_repeated_429_slows_the_rest_of_the_run(self):
        """Retrying at the cadence that triggered the limit walks straight back
        into it — a 5-country, 4-year run burned all five retries at the default
        2s pacing and still failed. A 429 is about sustained rate, so the pacing
        itself has to change for the remaining calls."""
        intervals = []

        def limited(url, *a, **kw):
            intervals.append(ct.MIN_INTERVAL)
            raise urllib.error.HTTPError(url, 429, "Too Many Requests", {}, None)

        original_open = ct.urllib.request.urlopen
        original_sleep = ct.time.sleep
        original_interval = ct.MIN_INTERVAL
        old_retries, ct.MAX_RETRIES = ct.MAX_RETRIES, 4
        ct.MIN_INTERVAL = 2.0
        ct.urllib.request.urlopen = limited
        ct.time.sleep = lambda s: None
        ct.CACHE_DIR = Path(tempfile.mkdtemp())
        try:
            with self.assertRaises(ct.ComtradeError):
                ct.fetch(freq="A", period=2024, reporter=410, partner=0,
                         hs="3907", flow="X", use_cache=False)
            self.assertEqual(intervals[0], 2.0)
            self.assertGreater(intervals[-1], intervals[0], f"간격이 올라가야 한다: {intervals}")
            self.assertLessEqual(max(intervals), ct.MAX_INTERVAL)
        finally:
            ct.urllib.request.urlopen = original_open
            ct.time.sleep = original_sleep
            ct.MAX_RETRIES = old_retries
            ct.MIN_INTERVAL = original_interval
            ct.CACHE_DIR = context.FIXTURES

    def test_pacing_interval_has_a_floor(self):
        """The env var is there to slow down on a shared IP, not to remove the
        delay entirely."""
        import importlib
        old = os.environ.get("TRADE_STATS_MIN_INTERVAL")
        os.environ["TRADE_STATS_MIN_INTERVAL"] = "0"
        try:
            reloaded = importlib.reload(ct)
            self.assertGreaterEqual(reloaded.MIN_INTERVAL, 1.0)
        finally:
            if old is None:
                os.environ.pop("TRADE_STATS_MIN_INTERVAL", None)
            else:
                os.environ["TRADE_STATS_MIN_INTERVAL"] = old
            importlib.reload(ct)
            context.ct.CACHE_DIR = context.FIXTURES
            context.ct.CACHE_TTL_SECONDS = 10 ** 9
            context.ct.MIN_INTERVAL = 0.0


class TestDenominatorIntegrity(unittest.TestCase):
    """`world_total` divides every supplier share. A truncated World row that
    got summed from its partner2 breakdowns is exactly double the real total —
    India's 2024 HS3907 World request returns 88 such rows — and using it would
    halve every share on the report without any visible symptom."""

    def test_summed_world_row_is_refused_as_a_denominator(self):
        area = {"code": 699, "name": "인도", "reporter": True}
        real_fetch = ct.fetch

        def fake_fetch(**kw):
            rows = real_fetch(**kw)
            if kw.get("partner") == ct.WORLD and rows:
                rows = [dict(rows[0], value_usd=rows[0]["value_usd"] * 2,
                             is_partial_sum=True)]
            return rows

        analyze.ct.fetch = fake_fetch
        try:
            result = analyze.collect_competitors("3907", area, 2024, context.quiet_log)
        finally:
            analyze.ct.fetch = real_fetch

        self.assertTrue(result["available"])
        korea = next(s for s in result["suppliers"] if s["supplier_code"] == ct.KOREA)
        # Falling back to the partner sum keeps Korea near its true ~15%; using
        # the doubled World row would have reported roughly half that.
        self.assertGreater(korea["share_pct"], 10.0)

    def test_clean_world_row_is_used_as_the_denominator(self):
        context.block_network()
        area = {"code": 699, "name": "인도", "reporter": True}
        result = analyze.collect_competitors("3907", area, 2024, context.quiet_log)
        world = ct.fetch(freq="A", period=2024, reporter=699, partner=ct.WORLD,
                         hs="3907", flow="M")
        self.assertAlmostEqual(result["total_imports_usd"], world[0]["value_usd"], places=2)


class TestCacheDegradation(unittest.TestCase):
    """The cache is an optimization. An unwritable directory must not stop a run."""

    def test_unwritable_cache_does_not_raise(self):
        original = ct.CACHE_DIR
        ct.CACHE_DIR = Path("/proc/nonexistent-and-unwritable")
        try:
            ct._write_cache("https://example.invalid/x", {"data": []})
        finally:
            ct.CACHE_DIR = original

    def test_corrupt_cache_entry_is_ignored_rather_than_crashing(self):
        tmp = Path(tempfile.mkdtemp())
        original = ct.CACHE_DIR
        ct.CACHE_DIR = tmp
        try:
            url = "https://example.invalid/corrupt"
            ct._cache_path(url).write_text("{not json", encoding="utf-8")
            self.assertIsNone(ct._read_cache(url))
        finally:
            ct.CACHE_DIR = original


class TestFixtureIntegrity(unittest.TestCase):
    """Guards the test suite itself: a deleted fixture must fail loudly rather
    than silently turning the suite into a live, non-deterministic run."""

    def test_missing_fixture_raises_instead_of_calling_the_network(self):
        context.block_network()
        with self.assertRaises(context.NetworkAccessError):
            ct.fetch(freq="A", period=1999, reporter=410, partner=0,
                     hs="3907", flow="X")


if __name__ == "__main__":
    unittest.main()
