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
        """The two pages must remain distinct type systems, whatever the families."""
        from macro import board

        def stacks(css):
            return {re.sub(r'\s+', '', m) for m in
                    re.findall(r'--(?:mono|body|disp|sans):([^;]+);', css)}
        a, b = stacks(terminal.CSS), stacks(board.CSS)
        self.assertTrue(a and b, "font stacks not declared as tokens")
        self.assertFalse(a & b, f"the two pages share a font stack: {a & b}")


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
        # count only inside the tape: the derived cell is grid-only
        tape = re.search(r'<div class="tape-run">(.*?)</div></div>', self.doc, re.S)
        self.assertIsNotNone(tape)
        self.assertEqual(tape.group(1).count('class="tk"'), 2 * len(self.snap.quotes))

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

    def _payload(self):
        import json
        m = re.search(r"window\.__TERM__=(\{.*?\});", self.doc, re.S)
        self.assertIsNotNone(m, "payload missing")
        return json.loads(m.group(1).replace("<\\/", "</"))

    def test_heatmap_canvas_is_rendered(self):
        cv = re.search(r'id="hm-canvas" width="(\d+)" height="(\d+)"', self.doc)
        self.assertIsNotNone(cv, "heatmap canvas not rendered")
        self.assertGreaterEqual(int(cv.group(1)), 400)
        self.assertGreaterEqual(int(cv.group(2)), 300)

    def test_heatmap_anchors_are_only_observed_prices(self):
        data = self._payload()
        observed = {round(a.price, 2) for a in self.snap.price_anchors}
        self.assertEqual({round(a["price"], 2) for a in data["anchors"]}, observed)
        self.assertEqual(len(data["anchors"]), len(self.snap.price_anchors))
        for a in data["anchors"]:
            self.assertTrue(a["source"].strip(), "anchor shipped without a source")

    def test_all_ramps_shipped_match_the_module(self):
        from macro.live import HEAT_RAMPS
        data = self._payload()
        self.assertEqual({k: list(v) for k, v in HEAT_RAMPS.items()}, data["ramps"])

    def test_no_precomputed_grid_is_shipped(self):
        """The browser recomputes from anchors, so a stale grid must not ride along."""
        self.assertNotIn('"grid"', self.doc)

    def test_heatmap_states_its_method_and_its_limits(self):
        flat = " ".join(self.doc.split())
        self.assertIn("Computed by the published method, on real prices", flat)
        self.assertIn("no price is ever interpolated", flat)
        self.assertIn("not</b> open-interest weighted", flat)

    def test_heatmap_axis_bounds_come_from_the_sourced_window(self):
        """Axes are drawn client-side, so the sourced bounds must reach the payload."""
        w = self.snap.btc_window
        data = self._payload()
        self.assertAlmostEqual(data["window"]["lo"], w["lo"], places=6)
        self.assertAlmostEqual(data["window"]["hi"], w["hi"], places=6)
        for a in self.snap.price_anchors:
            self.assertGreaterEqual(a.price, data["window"]["lo"])
            self.assertLessEqual(a.price, data["window"]["hi"])

    def test_heatmap_controls_are_present_and_wired(self):
        for attr in ("data-tf", "data-lrange", "data-res", "data-scheme"):
            self.assertIn(attr, self.doc, attr)
            self.assertIn(f'[{attr}]', terminal.JS, f"{attr} is rendered but never bound")
        for el in ("hm-thr", "hm-zin", "hm-zout", "hm-reset", "hm-fit", "hm-zv",
                   "hm-lmin", "hm-lmax", "hm-peak", "hm-price", "hm-time", "hm-meta"):
            self.assertIn(f'id="{el}"', self.doc, el)
        self.assertIn("heatmapCompute", terminal.JS)

    def test_the_control_bar_offers_a_coinglass_grade_range_of_views(self):
        """One timeframe and two resolutions is not 'plenty of options'."""
        self.assertGreaterEqual(len(re.findall(r'data-tf="(-?\d+)"', self.doc)), 6)
        self.assertGreaterEqual(len(re.findall(r'data-res="(\d+x\d+)"', self.doc)), 4)
        self.assertGreaterEqual(len(re.findall(r'data-lrange="(\d+-\d+)"', self.doc)), 5)
        # exactly one default per pill group, or the initial paint disagrees with the bar
        for group in ("data-tf", "data-res", "data-scheme"):
            row = re.findall(rf'{group}="[^"]*"[^>]*data-on', self.doc)
            self.assertEqual(len(row), 1, group)

    def test_price_is_a_chart_series_not_a_dashed_annotation(self):
        """The old overlay was a 9px dashed polyline with 8px hollow circles."""
        js = terminal.JS
        self.assertIn('ST.chart', js)
        for k in ("candle", "bar", "area", "line", "off"):
            self.assertIn(f'data-ct="{k}"', self.doc, k)
            self.assertIn(f'"{k}"', js, k)
        self.assertIn("[data-ct]", js, "chart-type pills rendered but never bound")
        # exactly one default, and it is not the line
        on = re.findall(r'data-ct="([a-z]+)"[^>]*data-on', self.doc)
        self.assertEqual(on, ["candle"])
        # the dashed-polyline overlay must be gone
        self.assertNotIn("g.setLineDash([16,11])", js)
        self.assertNotIn("g.arc(p[0],p[1],8", js)

    def test_candles_never_invent_an_intrabar_range(self):
        """Wicks may not extend past the two observations that form the body."""
        js = terminal.JS
        self.assertIn("var top=Math.min(a.y,b.y), bot=Math.max(a.y,b.y)", js)
        self.assertIn("no invented range", js)
        # the wick is drawn between top and bot and nowhere else: no term may
        # push a drawn extreme outside the observed pair
        wick = re.findall(r"g\.moveTo\(cx,(\w+)\); g\.lineTo\(cx,(\w+)\)", js)
        self.assertTrue(wick, "no wick drawn")
        for a, b in wick:
            self.assertEqual({a, b}, {"top", "bot"}, f"wick drawn to {a}..{b}")

    def test_series_positions_come_from_timestamps_not_grid_cells(self):
        """Quantising to a cell put the track hours away from the observation."""
        self.assertIn("function px(iso)", terminal.JS)
        self.assertIn("function py(v)", terminal.JS)
        self.assertNotIn("(a.col+0.5)*CW", terminal.JS)

    def test_candle_width_uses_the_median_gap(self):
        """The minimum gap is one 3h21m intraday pair; sizing to it made hairlines."""
        self.assertIn("gaps[Math.floor(gaps.length/2)]", terminal.JS)
        self.assertNotIn("gap=Math.min(gap, LAST[i].x", terminal.JS)

    def test_page_copy_matches_what_is_actually_drawn(self):
        """Copy described a dashed line and 'no candle is drawn' after candles shipped."""
        low = self.doc.lower()
        for stale in ("price line is drawn dashed", "no candle is drawn",
                      "four dated btc closes"):
            self.assertNotIn(stale, low, f"stale copy on the page: {stale!r}")
        self.assertIn("no wick is", low)

    def test_price_axis_is_a_zoom_control(self):
        for ev in ("mousedown", "wheel"):
            self.assertIn(ev, terminal.JS)
        self.assertIn('var axis=q("hm-price")', terminal.JS)
        self.assertIn("ns-resize", terminal.CSS)

    def test_crosshair_clears_when_the_view_refuses(self):
        """A stale LAST would report positions from a view no longer on screen."""
        js = terminal.JS
        self.assertIn('id="hm-hair"', self.doc)
        self.assertIn('id="hm-tip"', self.doc)
        self.assertEqual(js.count("LAST=[];"), 3,
                         "LAST must be cleared on both refusal paths and initialised")

    def test_data_age_is_measured_from_the_newest_observation(self):
        """Age from `captured` resets to zero on a scan that fetched nothing."""
        self.assertIn('"newest"', self.doc)
        self.assertIn("D.newest||D.captured", terminal.JS)

    def test_capture_time_is_never_in_the_future(self):
        from datetime import datetime, timezone
        cap = datetime.fromisoformat(self.snap.captured.replace("Z", "+00:00"))
        self.assertLessEqual(cap, datetime.now(timezone.utc),
                             "capture stamped in the future: age would read zero")

    def test_zoom_can_widen_the_window_not_only_narrow_it(self):
        """The old clamp was max(1, ...), which made every zoom-out a silent no-op."""
        m = re.search(r"function zoom\(f\)\{([^}]*)\}", terminal.JS)
        self.assertIsNotNone(m, "zoom() missing")
        floor = re.search(r"Math\.max\(([0-9.]+)", m.group(1))
        self.assertIsNotNone(floor, "zoom() has no lower clamp")
        self.assertLess(float(floor.group(1)), 1.0,
                        "zoom-out is clamped at or above 1x: the chart cannot widen")

    def test_the_chart_can_be_panned(self):
        for ev in ("mousedown", "mousemove", "mouseup"):
            self.assertIn(f'"{ev}"', terminal.JS, ev)
        self.assertIn("ST.pan", terminal.JS)

    def test_embedded_anchors_are_chronological(self):
        """windowed() and anchorsIn() both take the last anchor as the latest."""
        m = re.search(r'"anchors":\s*(\[.*?\])\s*,?\s*\}', self.doc, re.S)
        self.assertIsNotNone(m, "anchor payload not found")
        dates = re.findall(r'"date":\s*"([^"]+)"', m.group(1))
        self.assertEqual(len(dates), len(self.snap.price_anchors))
        self.assertEqual(dates, sorted(dates), "anchors emitted out of order")

    def test_windows_the_data_cannot_support_are_gated_not_shipped_dead(self):
        """A window with <2 anchors, or the same anchors as a narrower one,
        renders identically. Offering it as a live button is a lie about the data."""
        self.assertIn("gateWindows", terminal.JS)
        self.assertIn("a heatmap needs two", terminal.JS)
        self.assertIn("no observation between them", terminal.JS)
        self.assertIn("b.disabled=true", terminal.JS.replace(" ", ""))
        self.assertIn("[data-off]", terminal.CSS)
        # the gate must run before the default view is drawn, or the bar and the
        # canvas disagree on the first paint
        self.assertLess(terminal.JS.index("gateWindows"),
                        terminal.JS.rindex("syncLev(); draw();"))
        # ALL is the widest window and can never be gated off, so a default
        # always survives
        self.assertIn('data-tf="0" data-on=1', self.doc)

    def test_leverage_control_cannot_empty_the_model(self):
        """An inverted min/max would render tiers(a,b) empty and blank the field."""
        self.assertIn("an inverted range is an empty model", terminal.JS)
        self.assertIn("if(ST.lmin>ST.lmax)", terminal.JS.replace(" ", ""))
        self.assertIn("Math.min(125,Math.max(2,v))", terminal.JS.replace(" ", ""))

    def test_equity_ticker_does_not_reuse_the_tape_class(self):
        """.tk is the ticker-tape item: reusing it puts flex and padding on equities."""
        self.assertNotIn('class="tk">', re.sub(r'<div class="tape-run">.*?</div>\s*</div>',
                                               "", self.doc, flags=re.S)
                         .split('class="eq"')[-1])
        self.assertIn('class="eqt"', self.doc)

    def test_every_equity_and_earning_renders_with_provenance(self):
        import html as _h
        self.assertEqual(self.doc.count('class="eqc"'), len(self.snap.equities))
        self.assertEqual(self.doc.count('class="er"'), len(self.snap.earnings))
        for x in self.snap.equities:
            self.assertIn(_h.escape(x.source, quote=True), self.doc)
        for x in self.snap.earnings:
            self.assertIn(_h.escape(x.source, quote=True), self.doc)

    def test_earnings_countdown_precision_matches_the_source(self):
        """A date-only source must render a day countdown, never a clock."""
        for x in self.snap.earnings:
            if x.status == "REPORTED":
                continue
            if x.when and not x.time_confirmed:
                self.assertIn(f'data-days="{x.when}"', self.doc)
                self.assertNotIn(f'data-when="{x.when}"', self.doc)
            elif x.when:
                self.assertIn(f'data-when="{x.when}"', self.doc)
            else:
                self.assertIn(x.window, self.doc)

    def test_every_geo_event_shows_when_it_happened(self):
        stamps = re.findall(r'data-ago="([^"]+)"', self.doc)
        self.assertEqual(len(stamps), len(self.snap.geo))
        for st in stamps:
            datetime.strptime(st, "%Y-%m-%dT%H:%M:%SZ")
        self.assertEqual({s for s in stamps}, {g.as_of for g in self.snap.geo})

    def test_terminal_chrome_present(self):
        self.assertIn('class="cmdbar"', self.doc)
        self.assertIn('class="statusbar"', self.doc)
        self.assertGreaterEqual(self.doc.count('class="fk"'), 5)

    def test_status_bar_counts_match_the_snapshot(self):
        self.assertIn(f'<span>QUOTES <b>{len(self.snap.quotes)}</b></span>', self.doc)
        self.assertIn(f'<span>WIRE <b>{len(self.snap.headlines)}</b></span>', self.doc)
        self.assertIn(f'<span>GEO <b>{len(self.snap.geo)}</b></span>', self.doc)
        self.assertIn(f'<span>CONFLICTS <b>{len(self.snap.conflicts)}</b></span>', self.doc)

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
        w = self.snap.btc_window
        if w:
            for i in range(5):
                known.add(f'{w["lo"] + (w["hi"] - w["lo"]) * i / 4:,.0f}')
            known |= {f'{w["lo"]:,.0f}', f'{w["hi"]:,.0f}'}
        for a in self.snap.price_anchors:
            known |= {f"{a.price:,.2f}", f"{a.price:,.0f}"}
        liq = self.snap.liquidations
        if liq:
            known |= {f"{liq.short_pct:.1f}", f"{liq.long_pct:.1f}",
                      f"{liq.short_pct:.2f}", f"{liq.long_pct:.2f}",
                      f"{liq.total_usd / 1e6:,.1f}", f"{liq.short_usd / 1e6:,.0f}",
                      f"{liq.long_usd / 1e6:,.1f}",
                      f"{(liq.asset_usd or 0) / 1e6:,.1f}"}
        # A conflict record quotes the superseded figure on purpose: the contract
        # is that a correction is RECORDED, not erased. Those numerals are part
        # of the snapshot, so they count as sourced.
        conflict_text = " ".join(self.snap.conflicts or ())
        known |= set(re.findall(r"\b\d[\d,]{2,}\.\d{2}\b", conflict_text))
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
