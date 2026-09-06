"""Scanner, schema and freshness tests.

The property that matters most: when a source is unreachable the previous value
must survive **with its original timestamp**. A snapshot that silently restamps
stale data is the single most dangerous failure this pipeline can have.
"""

import json
import os
import re
import tempfile
import threading
import unittest
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer

from macro import live, seed
from macro.live import (
    HEAT_RAMP, Headline, PriceAnchor, Quote, Snapshot, Source, age_seconds,
    dedupe, liquidation_heatmap, liquidation_ladder, load, merge, parse_rss,
    parse_treasury_csv, save, scan,
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


def _oklab_L(hexs):
    def lin(c):
        c /= 255.0
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (lin(int(hexs[i:i + 2], 16)) for i in (1, 3, 5))
    l = 0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b
    m = 0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b
    s_ = 0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b
    l_, m_, s2 = l ** (1 / 3), m ** (1 / 3), s_ ** (1 / 3)
    return 0.2104542553 * l_ + 0.7936177850 * m_ - 0.0040720468 * s2


class TestHeatRamp(unittest.TestCase):
    """A magnitude ramp that is not monotonic in lightness misreports order."""

    def test_ramp_is_monotonic_in_lightness(self):
        Ls = [_oklab_L(c) for c in HEAT_RAMP]
        for i in range(len(Ls) - 1):
            self.assertLess(Ls[i], Ls[i + 1],
                            f"ramp reverses at stop {i}: {HEAT_RAMP[i]}")

    def test_ramp_steps_are_reasonably_even(self):
        Ls = [_oklab_L(c) for c in HEAT_RAMP]
        gaps = [Ls[i + 1] - Ls[i] for i in range(len(Ls) - 1)]
        self.assertGreater(min(gaps), 0.05, "a step this small is invisible")
        self.assertLess(max(gaps) / min(gaps), 2.0, "steps are badly uneven")

    def test_ramp_is_all_valid_hex(self):
        for c in HEAT_RAMP:
            self.assertRegex(c, r"^#[0-9A-Fa-f]{6}$")


class TestHeatmap(unittest.TestCase):
    ANCHORS = [
        PriceAnchor("2026-08-04T20:00:00Z", 63465.20, "YCharts", 3),
        PriceAnchor("2026-08-21T20:00:00Z", 76712.47, "Fortune", 3),
        PriceAnchor("2026-08-24T20:00:00Z", 78976.18, "Fortune", 3),
        PriceAnchor("2026-09-04T11:21:00Z", 81240.29, "Yahoo Finance", 2),
    ]

    def test_anchor_contract(self):
        for bad in (dict(date="2026-08-04T20:00:00Z", price=0, source="s", tier=1),
                    dict(date="2026-08-04T20:00:00Z", price=1, source="", tier=1),
                    dict(date="nope", price=1, source="s", tier=1),
                    dict(date="2026-08-04T20:00:00Z", price=1, source="s", tier=9)):
            with self.assertRaises(ValueError):
                PriceAnchor(**bad)

    def test_grid_shape_and_normalisation(self):
        h = liquidation_heatmap(self.ANCHORS, lo=62553.7, hi=82178.6)
        self.assertTrue(h["ok"])
        self.assertEqual(len(h["grid"]), h["columns"])
        for col in h["grid"]:
            self.assertEqual(len(col), h["rows"])
            for v in col:
                self.assertGreaterEqual(v, 0.0)
                self.assertLessEqual(v, 1.0)
        self.assertEqual(max(max(c) for c in h["grid"]), 1.0, "peak must normalise to 1")

    def test_every_anchor_lands_inside_the_grid(self):
        h = liquidation_heatmap(self.ANCHORS, lo=62553.7, hi=82178.6)
        self.assertEqual(len(h["anchors"]), len(self.ANCHORS))
        for a in h["anchors"]:
            self.assertGreaterEqual(a["col"], 0)
            self.assertLess(a["col"], h["columns"])
            self.assertGreaterEqual(a["row"], 0)
            self.assertLess(a["row"], h["rows"])

    def test_anchors_stay_in_time_order(self):
        cols = [a["col"] for a in
                liquidation_heatmap(self.ANCHORS)["anchors"]]
        self.assertEqual(cols, sorted(cols))

    def test_first_and_last_anchor_pin_the_axis(self):
        h = liquidation_heatmap(self.ANCHORS)
        self.assertEqual(h["anchors"][0]["col"], 0)
        self.assertEqual(h["anchors"][-1]["col"], h["columns"] - 1)

    def test_no_price_is_invented(self):
        """Only observed prices may appear as anchors."""
        h = liquidation_heatmap(self.ANCHORS, lo=62553.7, hi=82178.6)
        observed = {round(a.price, 2) for a in self.ANCHORS}
        self.assertEqual({round(a["price"], 2) for a in h["anchors"]}, observed)

    def test_levels_are_swept_when_price_passes_through(self):
        """A rising series must clear the short levels it trades through."""
        rising = [PriceAnchor(f"2026-08-{d:02d}T20:00:00Z", p, "t", 3)
                  for d, p in ((1, 100.0), (2, 110.0), (3, 130.0))]
        h = liquidation_heatmap(rising, levels=(10,), columns=8, rows=20,
                                lo=80.0, hi=150.0)
        self.assertTrue(h["ok"])
        # the 10x short level from the first anchor is 110, swept by anchor two
        self.assertLess(sum(h["grid"][-1]), sum(h["grid"][0]) * 3,
                        "swept levels are not being cleared")

    def test_degenerate_inputs_refuse_cleanly(self):
        self.assertFalse(liquidation_heatmap([])["ok"])
        self.assertFalse(liquidation_heatmap(self.ANCHORS[:1])["ok"])
        same = [PriceAnchor("2026-08-04T20:00:00Z", 100.0, "s", 3),
                PriceAnchor("2026-08-04T20:00:00Z", 200.0, "s", 3)]
        self.assertFalse(liquidation_heatmap(same)["ok"])
        self.assertFalse(liquidation_heatmap(self.ANCHORS, lo=50, hi=40)["ok"])
        self.assertFalse(liquidation_heatmap(self.ANCHORS, columns=1)["ok"])

    def test_out_of_range_bounds_produce_no_levels_not_a_crash(self):
        h = liquidation_heatmap(self.ANCHORS, lo=1.0, hi=2.0)
        self.assertFalse(h["ok"])
        self.assertIn("no pending levels", h["reason"])

    def test_ladder_and_heatmap_agree_on_the_same_arithmetic(self):
        p = 81240.29
        for r in liquidation_ladder(p, levels=(10, 25)):
            self.assertAlmostEqual(r["long_liq"], p * (1 - 1 / r["leverage"]), places=6)
            self.assertAlmostEqual(r["short_liq"], p * (1 + 1 / r["leverage"]), places=6)


class TestCrossImplementation(unittest.TestCase):
    """The browser recomputes the heatmap live for the controls. If its port
    drifts from the Python reference the page silently shows a different model,
    so the two are compared directly."""

    def test_js_engine_matches_python_exactly(self):
        import json
        import shutil
        import subprocess
        import tempfile

        if shutil.which("node") is None:
            self.skipTest("node not available")
        from macro import seed as seed_mod
        from macro import terminal

        m = re.search(r"(function heatmapCompute\(anchors, opts\)\{.*?\n\})\n",
                      terminal.JS, re.S)
        self.assertIsNotNone(m, "heatmapCompute not found in the shipped JS")
        anchors = [{"date": a.date, "price": a.price, "source": a.source,
                    "tier": a.tier} for a in seed_mod.build().price_anchors]
        cases = [
            dict(lo=62553.7, hi=82178.6, columns=36, rows=34, levels=[10, 25, 50, 100]),
            dict(lo=62553.7, hi=82178.6, columns=90, rows=60, levels=[5, 10, 25, 50, 100]),
            dict(columns=12, rows=8, levels=[25]),
            dict(lo=70000, hi=85000, columns=48, rows=40, levels=[10, 50]),
            dict(lo=1.0, hi=2.0, columns=20, rows=20, levels=[10]),   # refuses
            # the shipped default: levels omitted -> the full 2..125 spectrum,
            # which is what every unmodified page load actually renders
            dict(lo=62553.7, hi=82178.6, columns=160, rows=90),
            dict(columns=240, rows=130),                       # ULTRA, derived range
            dict(lo=62553.7, hi=82178.6, columns=60, rows=40,
                 levels=list(range(50, 126))),                 # the HIGH preset
            dict(lo=62553.7, hi=82178.6, columns=110, rows=64,
                 levels=list(range(2, 11))),                   # the LOW preset
            # small integer peaks are where round()/Math.round diverge on ties
            dict(lo=62553.7, hi=82178.6, columns=8, rows=200, levels=[3, 7]),
            dict(columns=36, rows=34, levels=[]),   # explicitly empty: refuses
        ]
        prog = (m.group(1) + "\nconst A=" + json.dumps(anchors) +
                ";\nconst C=" + json.dumps(cases) +
                ";\nconsole.log(JSON.stringify(C.map(o=>heatmapCompute(A,o))));")
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as fh:
            fh.write(prog)
            path = fh.name
        try:
            out = subprocess.run(["node", path], capture_output=True, text=True,
                                 timeout=60)
        finally:
            os.unlink(path)
        self.assertEqual(out.returncode, 0, out.stderr[:400])
        js = json.loads(out.stdout)

        py_anchors = seed_mod.build().price_anchors
        for i, c in enumerate(cases):
            py = liquidation_heatmap(py_anchors, **c)
            self.assertEqual(py["ok"], js[i]["ok"], f"case {i}: ok differs")
            if not py["ok"]:
                continue
            for k in ("columns", "rows"):
                self.assertEqual(py[k], js[i][k], f"case {i}: {k}")
            for k in ("lo", "hi"):
                self.assertAlmostEqual(py[k], js[i][k], places=9, msg=f"case {i}: {k}")
            for x in range(py["columns"]):
                for y in range(py["rows"]):
                    self.assertAlmostEqual(
                        py["grid"][x][y], js[i]["grid"][x][y], places=9,
                        msg=f"case {i}: grid[{x}][{y}] diverges")
            self.assertEqual([(a["col"], a["row"]) for a in py["anchors"]],
                             [(a["col"], a["row"]) for a in js[i]["anchors"]],
                             f"case {i}: anchor placement differs")


class TestEquitiesAndEarnings(unittest.TestCase):
    def test_equity_contract(self):
        from macro.live import Equity
        for bad in (dict(ticker="", name="n", as_of="2026-09-04T20:00:00Z",
                         source="s", tier=1),
                    dict(ticker="X", name="n", as_of="2026-09-04T20:00:00Z",
                         source=" ", tier=1),
                    dict(ticker="X", name="n", as_of="2026-09-04T20:00:00Z",
                         source="s", tier=7),
                    dict(ticker="X", name="n", as_of="2026-09-04T20:00:00Z",
                         source="s", tier=1, mktcap_usd=0)):
            with self.assertRaises(ValueError):
                Equity(**bad)

    def test_earning_needs_a_time_or_a_window(self):
        from macro.live import Earning
        with self.assertRaises(ValueError):
            Earning(ticker="X", name="n", source="s", tier=1)
        with self.assertRaises(ValueError):
            Earning(ticker="X", name="n", source="s", tier=1,
                    when="2026-09-10T00:00:00Z", session="LUNCHTIME")
        self.assertTrue(Earning(ticker="X", name="n", source="s", tier=1,
                                window="week of 7-11 September").window)

    def test_seed_equities_and_earnings_are_sourced(self):
        snap = seed.build()
        self.assertGreaterEqual(len(snap.equities), 4)
        self.assertGreaterEqual(len(snap.earnings), 3)
        for x in snap.equities:
            self.assertTrue(x.source.strip())
            self.assertTrue(x.url.startswith("https://"))
        for x in snap.earnings:
            self.assertTrue(x.source.strip())
            self.assertTrue(x.url.startswith("https://"))
            self.assertTrue(x.when or x.window)

    def test_no_earning_claims_an_unconfirmed_time(self):
        """A date-only source must never produce an hour-precise countdown."""
        for x in seed.build().earnings:
            if x.time_confirmed:
                self.assertTrue(x.when, f"{x.ticker}: time_confirmed without a datetime")
            elif x.when:
                self.assertTrue(x.when.endswith("T00:00:00Z"),
                                f"{x.ticker}: unconfirmed time must sit at midnight UTC")


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

    def test_price_anchors_are_sourced_and_dated(self):
        for a in seed.build().price_anchors:
            self.assertTrue(a.source.strip())
            self.assertTrue(a.url.startswith("https://"))
            datetime.strptime(a.date, "%Y-%m-%dT%H:%M:%SZ")

    def test_btc_window_bounds_contain_every_anchor(self):
        snap = seed.build()
        w = snap.btc_window
        self.assertTrue(w)
        for a in snap.price_anchors:
            self.assertGreaterEqual(a.price, w["lo"])
            self.assertLessEqual(a.price, w["hi"])

    def test_headlines_sorted_by_impact(self):
        h = seed.build().headlines
        self.assertEqual([x.impact for x in h], sorted([x.impact for x in h], reverse=True))


if __name__ == "__main__":
    unittest.main()
