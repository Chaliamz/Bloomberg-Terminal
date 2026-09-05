"""Scanner, schema and freshness tests.

The property that matters most: when a source is unreachable the previous value
must survive **with its original timestamp**. A snapshot that silently restamps
stale data is the single most dangerous failure this pipeline can have.
"""

import json
import os
import tempfile
import threading
import unittest
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer

from macro import live, seed
from macro.live import (
    Headline, Quote, Snapshot, Source, age_seconds, dedupe, load, merge,
    parse_rss, parse_treasury_csv, save, scan,
)

NOW = datetime(2026, 9, 5, 13, 0, 0, tzinfo=timezone.utc)

RSS = """<?xml version="1.0"?><rss version="2.0"><channel>
<item><title><![CDATA[Fed holds rates at 3.50-3.75%]]></title>
<link>https://example.gov/a</link><pubDate>Fri, 04 Sep 2026 18:00:00 GMT</pubDate></item>
<item><title>Payrolls beat expectations</title><link>https://example.gov/b</link>
<pubDate>Fri, 04 Sep 2026 12:30:00 +0000</pubDate></item>
<item><title>No date item</title><link>https://example.gov/c</link></item>
</channel></rss>"""

ATOM = """<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom">
<entry><title>ECB decision published</title><link href="https://example.eu/x"/>
<published>2026-09-04T12:15:00Z</published></entry></feed>"""

CSV = """Date,"1 Mo","2 Yr","5 Yr","10 Yr","30 Yr"
09/02/2026,4.10,4.30,4.50,4.70,5.10
09/04/2026,4.12,4.42,4.55,4.76,5.18
09/03/2026,4.11,4.34,4.52,4.78,5.15
"""


class TestQuoteContract(unittest.TestCase):
    def test_source_is_mandatory(self):
        with self.assertRaises(ValueError):
            Quote(key="X", value=1.0, unit="pct", as_of="2026-09-04T20:00:00Z",
                  source="  ", tier=1)

    def test_unit_is_mandatory(self):
        with self.assertRaises(ValueError):
            Quote(key="X", value=1.0, unit="", as_of="2026-09-04T20:00:00Z",
                  source="S", tier=1)

    def test_timestamp_must_parse(self):
        with self.assertRaises(ValueError):
            Quote(key="X", value=1.0, unit="pct", as_of="last tuesday",
                  source="S", tier=1)

    def test_tier_must_be_one_to_four(self):
        for bad in (0, 5, 9, -1):
            with self.assertRaises(ValueError):
                Quote(key="X", value=1.0, unit="pct", as_of="2026-09-04T20:00:00Z",
                      source="S", tier=bad)

    def test_confidence_bounds(self):
        with self.assertRaises(ValueError):
            Quote(key="X", value=1.0, unit="pct", as_of="2026-09-04T20:00:00Z",
                  source="S", tier=1, confidence=1.5)

    def test_headline_tier_and_impact_validated(self):
        with self.assertRaises(ValueError):
            Headline(title="t", source="s", tier=7, published="2026-09-04T20:00:00Z")
        with self.assertRaises(ValueError):
            Headline(title="t", source="s", tier=1, published="2026-09-04T20:00:00Z",
                     impact=140)


class TestParsers(unittest.TestCase):
    def test_rss_cdata_and_dates(self):
        items = parse_rss(RSS, "Test", 1)
        self.assertEqual(len(items), 3)
        self.assertEqual(items[0].title, "Fed holds rates at 3.50-3.75%")
        self.assertEqual(items[0].published, "2026-09-04T18:00:00Z")
        self.assertTrue(items[0].primary_confirmed)

    def test_atom_entries(self):
        items = parse_rss(ATOM, "ECB", 1)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].published, "2026-09-04T12:15:00Z")
        self.assertEqual(items[0].url, "https://example.eu/x")

    def test_undated_item_still_parses(self):
        items = parse_rss(RSS, "Test", 2)
        self.assertEqual(items[2].title, "No date item")
        self.assertTrue(items[2].published.endswith("Z"))

    def test_garbage_feed_returns_empty_not_raise(self):
        for junk in ("", "<html>not a feed</html>", "{}", "<rss><channel></channel></rss>"):
            self.assertEqual(parse_rss(junk, "X", 2), [])

    def test_treasury_csv_picks_the_latest_date_not_the_last_row(self):
        got = parse_treasury_csv(CSV)
        self.assertEqual(got["US2Y"][0], 4.42)
        self.assertEqual(got["US10Y"][0], 4.76)
        self.assertEqual(got["US2Y"][1], "2026-09-04T00:00:00Z")

    def test_csv_skips_na_cells(self):
        text = 'Date,"2 Yr","10 Yr"\n09/04/2026,N/A,4.76\n'
        got = parse_treasury_csv(text)
        self.assertNotIn("US2Y", got)
        self.assertIn("US10Y", got)

    def test_malformed_csv_returns_empty(self):
        for junk in ("", "not,a,curve\n1,2,3", "Date\n"):
            self.assertEqual(parse_treasury_csv(junk), {})


class TestDedupe(unittest.TestCase):
    def _h(self, title, tier, impact=50):
        return Headline(title=title, source=f"src{tier}", tier=tier,
                        published="2026-09-04T18:00:00Z", impact=impact)

    def test_same_story_from_many_outlets_is_one_event(self):
        items = [
            self._h("Fed holds rates at 3.50 to 3.75 percent", 2),
            self._h("Fed holds rates at 3.50 to 3.75 percent today", 3),
            self._h("The Fed holds rates at 3.50 to 3.75 percent", 4),
            self._h("Oil surges on Middle East strikes", 2),
        ]
        out = dedupe(items)
        self.assertEqual(len(out), 2)

    def test_highest_tier_carrier_survives(self):
        items = [
            self._h("Fed holds rates at 3.50 to 3.75 percent", 4),
            self._h("Fed holds rates at 3.50 to 3.75 percent", 1),
        ]
        out = dedupe(items)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0].tier, 1)

    def test_distinct_stories_all_kept(self):
        items = [self._h(f"Distinct headline number {i} about {i*7}", 2) for i in range(5)]
        self.assertEqual(len(dedupe(items)), 5)


class TestPersistence(unittest.TestCase):
    def test_round_trip(self):
        snap = seed.build()
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "s.json")
            save(snap, p)
            back = load(p)
            self.assertIsNotNone(back)
            self.assertEqual(back.captured, snap.captured)
            self.assertEqual(len(back.quotes), len(snap.quotes))
            self.assertEqual(len(back.headlines), len(snap.headlines))
            self.assertEqual(back.quotes["US10Y"].value, snap.quotes["US10Y"].value)
            self.assertEqual(back.quotes["US10Y"].source, snap.quotes["US10Y"].source)

    def test_missing_file_returns_none(self):
        self.assertIsNone(load("/nonexistent/x.json"))

    def test_corrupt_file_returns_none_not_raise(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "s.json")
            with open(p, "w") as fh:
                fh.write("{not json")
            self.assertIsNone(load(p))

    def test_write_is_atomic(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "s.json")
            save(seed.build(), p)
            self.assertFalse(os.path.exists(p + ".tmp"))


class TestFreshness(unittest.TestCase):
    def test_age_is_computed_from_the_stamp(self):
        a = age_seconds("2026-09-05T12:00:00Z", now=NOW)
        self.assertAlmostEqual(a, 3600, delta=1)

    def test_bad_stamp_is_unknown_not_zero(self):
        self.assertIsNone(age_seconds("whenever"))

    def test_unreachable_sources_keep_prior_values_and_timestamps(self):
        """The critical invariant: no silent restamping."""
        prev = seed.build()
        original = prev.quotes["US10Y"]
        dead = (Source("Dead wire", 2, "https://127.0.0.1:1/none", "rss", 60),
                Source("Dead curve", 1, "https://127.0.0.1:1/none.csv", "curve", 60))
        fresh = merge(prev, scan(prev, now=NOW, sources=dead))
        self.assertIn("US10Y", fresh.quotes)
        self.assertEqual(fresh.quotes["US10Y"].as_of, original.as_of)
        self.assertEqual(fresh.quotes["US10Y"].value, original.value)
        self.assertTrue(fresh.errors, "unreachable sources must be reported")
        self.assertNotEqual(fresh.captured, original.as_of)

    def test_headlines_survive_a_failed_scan(self):
        prev = seed.build()
        dead = (Source("Dead", 2, "https://127.0.0.1:1/x", "rss", 60),)
        fresh = merge(prev, scan(prev, now=NOW, sources=dead))
        self.assertEqual(len(fresh.headlines), len(prev.headlines))


class _Fixture(BaseHTTPRequestHandler):
    def do_GET(self):                                   # noqa: N802
        if self.path.startswith("/curve"):
            body, ctype = CSV, "text/csv"
        elif self.path.startswith("/atom"):
            body, ctype = ATOM, "application/atom+xml"
        else:
            body, ctype = RSS, "application/rss+xml"
        raw = body.encode()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def log_message(self, *a):                          # silence
        pass


class TestScanEndToEnd(unittest.TestCase):
    """Proves the whole poll -> parse -> snapshot path against a real server."""

    @classmethod
    def setUpClass(cls):
        cls.srv = HTTPServer(("127.0.0.1", 0), _Fixture)
        cls.port = cls.srv.server_address[1]
        cls.th = threading.Thread(target=cls.srv.serve_forever, daemon=True)
        cls.th.start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()

    def _sources(self):
        base = f"http://127.0.0.1:{self.port}"
        return (
            Source("Fixture Treasury", 1, base + "/curve.csv", "curve", 60),
            Source("Fixture wire", 2, base + "/rss", "rss", 60),
            Source("Fixture ECB", 1, base + "/atom", "rss", 60),
        )

    def test_scan_populates_quotes_from_the_curve(self):
        snap = scan(None, now=NOW, sources=self._sources())
        self.assertEqual(snap.quotes["US2Y"].value, 4.42)
        self.assertEqual(snap.quotes["US10Y"].value, 4.76)
        self.assertEqual(snap.quotes["US2Y"].tier, 1)
        self.assertEqual(snap.quotes["US2Y"].as_of, "2026-09-04T00:00:00Z")
        self.assertEqual(snap.errors, [])

    def test_scan_populates_and_dedupes_headlines(self):
        snap = scan(None, now=NOW, sources=self._sources())
        self.assertTrue(snap.headlines)
        titles = [h.title for h in snap.headlines]
        self.assertEqual(len(titles), len(set(titles)))
        self.assertIn("ECB decision published", titles)

    def test_second_pass_computes_change_in_basis_points(self):
        first = scan(None, now=NOW, sources=self._sources())
        first.quotes["US2Y"] = Quote(
            key="US2Y", value=4.30, unit="pct", as_of="2026-09-03T00:00:00Z",
            source="prior", tier=1, label="UST 2Y")
        second = scan(first, now=NOW, sources=self._sources())
        self.assertAlmostEqual(second.quotes["US2Y"].change, 12.0, places=1)
        self.assertEqual(second.quotes["US2Y"].change_unit, "bp")

    def test_releases_always_present(self):
        snap = scan(None, now=NOW, sources=self._sources())
        self.assertTrue(snap.releases)


class TestSeed(unittest.TestCase):
    def test_every_quote_has_a_real_source_and_url_or_note(self):
        snap = seed.build()
        for q in snap.quotes.values():
            self.assertTrue(q.source.strip(), q.key)
            self.assertTrue(q.url or q.note, f"{q.key} has neither a URL nor a note")

    def test_low_tier_quotes_carry_reduced_confidence(self):
        snap = seed.build()
        for q in snap.quotes.values():
            if q.tier >= 4:
                self.assertLessEqual(q.confidence, 0.6, q.key)
            if q.tier == 1:
                self.assertGreaterEqual(q.confidence, 0.8, q.key)

    def test_conflicts_are_recorded_not_resolved_silently(self):
        snap = seed.build()
        self.assertGreaterEqual(len(snap.conflicts), 2)
        self.assertLess(snap.quotes["US2Y"].confidence, 0.85,
                        "the disputed leg must carry reduced confidence")

    def test_regime_has_an_evidential_basis(self):
        snap = seed.build()
        self.assertNotEqual(snap.regime, "UNKNOWN")
        self.assertGreater(len(snap.regime_basis), 120)

    def test_release_clock_timestamps_all_parse(self):
        for r in seed.build().releases:
            datetime.strptime(r["when"], "%Y-%m-%dT%H:%M:%SZ")
            self.assertTrue(r["url"].startswith("https://"), r["code"])

    def test_headlines_sorted_by_impact(self):
        h = seed.build().headlines
        self.assertEqual([x.impact for x in h], sorted([x.impact for x in h], reverse=True))


if __name__ == "__main__":
    unittest.main()
