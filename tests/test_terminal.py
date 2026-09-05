"""Terminal render tests.

The page is allowed to *look* live. It is not allowed to *be* dishonest: every
number must trace to a sourced Quote, and every element that animates as live
must be computed from the clock rather than faked.
"""

import re
import unittest
from datetime import datetime, timezone

from macro import seed, terminal
from macro.live import Snapshot
from tests.test_board import Balance


class TestDocument(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.snap = seed.build()
        cls.doc = terminal.render(cls.snap)

    def test_complete_document(self):
        self.assertTrue(self.doc.startswith("<!doctype html>"))
        for n in ('<html lang="en">', "</head>", "<body>", "</body>", "</html>",
                  "<title>Macro Desk Live</title>", '<meta charset="utf-8">',
                  'name="viewport"'):
            self.assertIn(n, self.doc, n)

    def test_tags_balance(self):
        b = Balance()
        b.feed(self.doc)
        self.assertEqual(b.errors, [], "; ".join(b.errors[:3]))
        self.assertEqual([t for t, _ in b.stack], [])

    def test_fragment_has_no_document_skeleton(self):
        frag = terminal.render(self.snap, standalone=False)
        for tag in ("<!doctype", "<html", "<body>", "</body>", "</head>"):
            self.assertNotIn(tag, frag.lower(), tag)
        for keep in ("<title>", "<style>", "<script>"):
            self.assertIn(keep, frag, keep)

    def test_every_scripted_id_exists(self):
        ids = set(re.findall(r'q\("([A-Za-z0-9_-]+)"\)', terminal.JS))
        ids |= set(re.findall(r'setText\("([A-Za-z0-9_-]+)"', terminal.JS))
        self.assertGreater(len(ids), 4)
        for i in sorted(ids):
            self.assertIn(f'id="{i}"', self.doc, f"script addresses #{i}, absent from page")

    def test_dom_writes_are_null_safe(self):
        self.assertNotRegex(
            terminal.JS, r'q\("[A-Za-z0-9_-]+"\)\.(textContent|innerHTML)\s*=',
            "direct write to a possibly-missing node")

    def test_reduced_motion_honoured(self):
        self.assertIn("prefers-reduced-motion:reduce", terminal.CSS)
        self.assertIn("prefers-reduced-motion: reduce", terminal.JS)

    def test_body_paints_its_own_background(self):
        self.assertRegex(terminal.CSS, r"body\{[^}]*background:var\(--void\)")

    def test_grid_rows_are_full(self):
        spans = [int(x) for x in re.findall(r'class="card c(\d+)"', self.doc)]
        self.assertTrue(spans)
        rows, row = [], 0
        for s in spans:
            if row + s > 12:
                rows.append(row)
                row = s
            else:
                row += s
        rows.append(row)
        self.assertTrue(all(r == 12 for r in rows), f"row sums: {rows}")

    def test_typography_differs_from_the_architecture_board(self):
        from macro import board
        self.assertIn("Barlow", terminal.CSS)
        self.assertIn("JetBrains Mono", terminal.CSS)
        self.assertNotIn("Archivo", terminal.CSS)
        self.assertIn("Archivo", board.CSS)     # the two pages are distinct systems


class TestDataIntegrity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.snap = seed.build()
        cls.doc = terminal.render(cls.snap)

    def test_every_quote_renders_with_source_tier_and_time(self):
        cells = re.findall(r'<div class="q"[^>]*>(.*?)</div>\s*(?=<div class="q"|</div>)',
                           self.doc, re.S)
        self.assertGreaterEqual(len(self.snap.quotes), 10)
        for q in self.snap.quotes.values():
            self.assertIn(q.source, self.doc, f"{q.key} source missing from page")
        # one extra cell: the derived 2s10s, explicitly marked DERIVED
        self.assertEqual(self.doc.count('class="conf"'), len(self.snap.quotes) + 1)
        self.assertIn('class="q derived"', self.doc)
        self.assertIn(">DERIVED<", self.doc)

    def test_ticker_is_doubled_for_a_seamless_loop(self):
        # the ticker carries quoted values only; the derived cell is grid-only
        self.assertEqual(self.doc.count('class="tk"'), 2 * len(self.snap.quotes))

    def test_derived_cell_inherits_the_weaker_legs_confidence(self):
        two, ten = self.snap.q("US2Y"), self.snap.q("US10Y")
        weaker = min(two.confidence, ten.confidence)
        self.assertIn(f"conf {weaker:.2f}", self.doc)

    def test_every_countdown_target_is_a_valid_timestamp(self):
        stamps = re.findall(r'data-when="([^"]+)"', self.doc)
        self.assertEqual(len(stamps), len(self.snap.releases))
        for s in stamps:
            datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ")

    def test_every_headline_is_tiered_and_timestamped(self):
        import html as _h
        self.assertEqual(self.doc.count('class="sqr"'), len(self.snap.headlines))
        for h in self.snap.headlines:
            self.assertIn(_h.escape(h.source, quote=True), self.doc)

    def test_squawk_is_ordered_newest_first(self):
        stamps = re.findall(r'<span class="sqt">(\d{2}-\d{2})<br>(\d{2}:\d{2})Z</span>',
                            self.doc)
        self.assertEqual(len(stamps), len(self.snap.headlines))
        keys = [a + b for a, b in stamps]
        self.assertEqual(keys, sorted(keys, reverse=True))

    def test_every_gauge_renders_with_a_band_and_provenance(self):
        import html as _h
        self.assertEqual(self.doc.count('class="gg"'), len(self.snap.gauges))
        for g in self.snap.gauges.values():
            self.assertIn(g.band, self.doc)
            self.assertIn(_h.escape(g.source, quote=True), self.doc)

    def test_gauge_needle_stays_inside_the_arc(self):
        import math
        from macro.terminal import _arc_point
        for f in (0.0, 0.25, 0.5, 0.75, 1.0):
            x, y = _arc_point(f, 62.0)
            self.assertAlmostEqual(math.hypot(x - 100, y - 100), 62.0, places=6)
            self.assertGreaterEqual(x, 100 - 62 - 1e-9)
            self.assertLessEqual(x, 100 + 62 + 1e-9)
            self.assertLessEqual(y, 100 + 1e-9)

    def test_gauge_svg_viewbox_contains_every_drawn_point(self):
        for m in re.finditer(r'<svg viewBox="0 0 (\d+) (\d+)"(.*?)</svg>', self.doc, re.S):
            w, h, body = int(m.group(1)), int(m.group(2)), m.group(3)
            for cx, cy in re.findall(r'[cxy]1?="(-?[\d.]+)" [cy]y?1?="(-?[\d.]+)"', body):
                pass
            for val in re.findall(r'(?:cx|x|x1|x2)="(-?[\d.]+)"', body):
                self.assertGreaterEqual(float(val), -1)
                self.assertLessEqual(float(val), w + 1)
            for val in re.findall(r'(?:cy|y|y1|y2)="(-?[\d.]+)"', body):
                self.assertGreaterEqual(float(val), -1)
                self.assertLessEqual(float(val), h + 1)

    def test_liquidation_split_bar_sums_to_one_hundred(self):
        flexes = [float(x) for x in re.findall(r'flex:0 0 ([\d.]+)%', self.doc)]
        self.assertEqual(len(flexes), 2)
        self.assertAlmostEqual(sum(flexes), 100.0, places=2)

    def test_liquidation_ladder_matches_the_carried_spot(self):
        from macro.live import liquidation_ladder
        btc = self.snap.q("BTC")
        self.assertIsNotNone(btc)
        for r in liquidation_ladder(btc.value):
            self.assertIn(f'{r["long_liq"]:,.0f}', self.doc)
            self.assertIn(f'{r["short_liq"]:,.0f}', self.doc)

    def test_ladder_is_labelled_computed_not_observed(self):
        flat = " ".join(self.doc.split())
        self.assertIn("Computed, not observed", flat)
        self.assertIn("not</b> a heatmap of where open interest", flat)

    def test_ladder_segments_never_exceed_the_track(self):
        for left, width in re.findall(r'left:([\d.]+)%;\s*width:([\d.]+)%', self.doc):
            self.assertGreaterEqual(float(left), 0.0)
            self.assertLessEqual(float(left) + float(width), 100.0 + 1e-6)

    def test_every_geo_event_states_a_transmission_channel(self):
        import html as _h
        self.assertEqual(self.doc.count('class="ge"'), len(self.snap.geo))
        for g in self.snap.geo:
            self.assertTrue(g.channel.strip(), g.headline)
            self.assertIn(_h.escape(g.channel[:50], quote=True), self.doc)

    def test_geo_sorted_by_severity(self):
        sev = [int(x) for x in re.findall(r'<div class="sev" style="color:[^"]+">(\d+)',
                                          self.doc)]
        self.assertEqual(sev, sorted(sev, reverse=True))

    def test_every_flow_carries_a_source(self):
        self.assertEqual(self.doc.count('class="fl"'), len(self.snap.flows))
        import html as _h
        for f in self.snap.flows:
            self.assertIn(_h.escape(f["source"], quote=True), self.doc)

    def test_audit_table_lists_every_field(self):
        rows = re.search(r"<tbody>(.*?)</tbody>", self.doc.split("Source &amp; freshness")[1],
                         re.S)
        self.assertIsNotNone(rows)
        self.assertEqual(rows.group(1).count("<tr>"), len(self.snap.quotes))

    def test_conflicts_are_printed(self):
        import html as _h
        for c in self.snap.conflicts:
            # compare against the escaped form: quotes in the source text are
            # correctly entity-encoded on the page
            self.assertIn(_h.escape(c[:60], quote=True), self.doc)

    def test_page_states_it_is_a_snapshot_not_a_live_feed(self):
        flat = " ".join(self.doc.split())
        self.assertIn("captured snapshot", flat)
        self.assertIn("can never look fresher than it is", flat)
        self.assertIn("SNAPSHOT", self.doc)

    def test_no_number_appears_that_is_not_in_the_snapshot(self):
        """Every large decimal on the page must be a value we actually hold."""
        body = re.sub(r"<style>.*?</style>", "", self.doc, flags=re.S)
        body = re.sub(r"<script>.*?</script>", "", body, flags=re.S)
        body = re.sub(r"<!--.*?-->", "", body, flags=re.S)
        # SVG path/point coordinates are drawing instructions, not values a reader
        # can misread as data. They are excluded here and the visible SVG text is
        # checked separately by test_svg_text_shows_only_known_values.
        body = re.sub(r"<svg\b.*?</svg>", "", body, flags=re.S)
        known = set()
        for q in self.snap.quotes.values():
            known |= {f"{q.value:,.2f}", f"{q.value:,.0f}", f"{q.value:.2f}",
                      f"{q.value:.2f}%", f"{abs(q.change or 0):.2f}",
                      f"{abs(q.change or 0):.0f}"}
        # declared derivations: the 2s10s spread, the liquidation ladder and the
        # liquidation split. Each is arithmetic on a carried value and is labelled
        # as computed on the page, so it is admissible - anything else is not.
        two, ten = self.snap.q("US2Y"), self.snap.q("US10Y")
        if two and ten:
            known.add(f"{(ten.value - two.value) * 100:+.0f}")
            known.add(f"{abs((ten.value - two.value) * 100):.0f}")
        btc = self.snap.q("BTC")
        if btc:
            from macro.live import liquidation_ladder
            for r in liquidation_ladder(btc.value):
                known |= {f'{r["long_liq"]:,.0f}', f'{r["short_liq"]:,.0f}',
                          f'{r["move_pct"]:.0f}'}
        liq = self.snap.liquidations
        if liq:
            known |= {f"{liq.short_pct:.1f}", f"{liq.long_pct:.1f}",
                      f"{liq.short_pct:.2f}", f"{liq.long_pct:.2f}",
                      f"{liq.total_usd / 1e6:,.1f}", f"{liq.short_usd / 1e6:,.0f}",
                      f"{liq.long_usd / 1e6:,.1f}",
                      f"{(liq.asset_usd or 0) / 1e6:,.1f}"}
        for tok in re.findall(r"\b\d[\d,]{2,}\.\d{2}\b", body):
            self.assertIn(tok, known, f"unsourced number on the page: {tok}")

    def test_svg_text_shows_only_known_values(self):
        """Whatever a reader can actually read inside a chart must be real."""
        allowed = {"0", "50", "100"}                      # gauge scale ticks
        for g in self.snap.gauges.values():
            allowed |= {f"{g.value:.0f}", g.band}
        for svg in re.findall(r"<svg\b.*?</svg>", self.doc, re.S):
            for txt in re.findall(r"<text[^>]*>(.*?)</text>", svg, re.S):
                self.assertIn(txt.strip(), allowed, f"unexplained chart label: {txt!r}")

    def test_regime_basis_is_shown_with_the_regime(self):
        self.assertIn(self.snap.regime, self.doc)
        self.assertIn(self.snap.regime_basis[:80], self.doc)

    def test_html_is_escaped(self):
        snap = seed.build()
        h = snap.headlines[0]
        snap.headlines = [type(h)(title="<script>alert(1)</script>", source="X", tier=4,
                                  published="2026-09-04T12:00:00Z", impact=10)]
        doc = terminal.render(snap)
        self.assertNotIn("<script>alert(1)</script>", doc)
        self.assertIn("&lt;script&gt;", doc)

    def test_empty_snapshot_renders_without_crashing(self):
        empty = Snapshot(captured="2026-09-05T00:00:00Z")
        doc = terminal.render(empty)
        self.assertIn("<!doctype html>", doc)
        self.assertIn("UNAVAILABLE", doc)
        self.assertIn("No headlines", doc)

    def test_snapshot_missing_one_curve_leg_degrades(self):
        snap = seed.build()
        del snap.quotes["US2Y"]
        doc = terminal.render(snap)
        self.assertIn("UNAVAILABLE", doc)


class TestGeneratedFileIsCurrent(unittest.TestCase):
    def test_committed_terminal_matches_the_snapshot(self):
        import os

        from macro import live
        root = os.path.dirname(os.path.dirname(os.path.abspath(terminal.__file__)))
        html_path = os.path.join(root, "board/macro-desk-live.html")
        snap_path = os.path.join(root, "state/snapshot.json")
        if not (os.path.exists(html_path) and os.path.exists(snap_path)):
            self.skipTest("terminal not generated yet")
        snap = live.load(snap_path)
        self.assertIsNotNone(snap)
        with open(html_path, encoding="utf-8") as fh:
            self.assertEqual(fh.read(), terminal.render(snap),
                             "terminal is stale - run `python -m macro terminal`")


if __name__ == "__main__":
    unittest.main()
