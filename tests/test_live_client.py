"""The in-browser live client, pinned as source.

`tools/verify_live.py` proves this code runs correctly in Chromium against
venue-shaped servers. These tests are the cheap guard that runs every time: they
pin the invariants that a refactor could quietly delete and that a static render
can still see.

The one that matters most is the validation gate. It exists in two languages -
`macro.live.parse_binance_ticker` in Python and `ok()` in the page - and they
must reject the same things. A divergence means the browser accepts a tick the
scanner would have refused, which is exactly the fabrication the whole codebase
is built to prevent.
"""

import re
import unittest

from macro import seed, terminal


class TestLiveClient(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.snap = seed.build()
        cls.doc = terminal.render(cls.snap)

    # -- the hooks the client writes through ------------------------------
    def test_quote_cells_carry_a_key(self):
        keys = set(re.findall(r'<div class="q" data-k="([^"]+)"', self.doc))
        self.assertIn("BTC", keys)
        self.assertGreaterEqual(len(keys), 10, keys)

    def test_tape_items_carry_a_key(self):
        # doubled marquee: the BTC item appears twice and both must update
        self.assertEqual(self.doc.count('class="tk" data-tk="BTC"'), 2)

    def test_badge_targets_exist(self):
        for i in ('id="lv-state"', 'id="lv-px"'):
            self.assertIn(i, self.doc, i)

    def test_badge_starts_honest(self):
        # Before any tick the page must not imply a feed it does not have.
        m = re.search(r'<b id="lv-state" data-on="0">([^<]+)</b>', self.doc)
        self.assertIsNotNone(m, "badge must ship off and say so")
        self.assertIn("NO FEED", m.group(1))

    # -- both transports, and why each is there ---------------------------
    def test_websocket_transport(self):
        self.assertIn("wss://stream.binance.com:9443/ws/btcusdt@ticker", self.doc)
        # REST is not usable from a browser: Binance sends no ACAO header.
        self.assertNotIn("api.binance.com/api/v3/ticker/24hr\"", self.doc)

    def test_rest_fallback_transport(self):
        self.assertIn("https://api.coinbase.com/v2/prices/BTC-USD/spot", self.doc)

    def test_no_test_endpoint_leaked(self):
        self.assertNotIn("127.0.0.1", self.doc)
        self.assertNotIn("localhost", self.doc)

    # -- the validation gate, mirrored from the Python adapter -------------
    def test_gate_rejects_the_same_things_as_the_python_adapter(self):
        gate = self.doc[self.doc.index("function ok(price, ms)"):]
        gate = gate[:gate.index("function money")]
        for token, why in (
            ("isFinite(price)", "NaN / Infinity price"),
            ("price<=0", "non-positive price"),
            ("isFinite(ms)", "NaN / Infinity stamp"),
            ("ms>now+300000", "future stamp / clock skew"),
            ("ms<now-604800000", "seconds-epoch sent as milliseconds"),
        ):
            self.assertIn(token, gate, f"gate lost its check for {why}")

    def test_stream_checks_symbol_and_range(self):
        self.assertIn('m.s!=="BTCUSDT"', self.doc, "wrong-symbol check")
        self.assertIn("hi<lo", self.doc, "high-below-low check")

    def test_a_rejected_tick_writes_nothing(self):
        # apply() must return before touching the DOM when the gate refuses.
        body = self.doc[self.doc.index("function apply(key, price"):]
        body = body[:body.index("/* ---- 1. Binance stream")]
        head = body[:body.index("var txt=money(price);")]
        self.assertIn("if(!price)", head)
        self.assertIn("return false", head)
        # nothing may be written above that guard
        self.assertNotIn("textContent", head)
        self.assertNotIn("setAttribute(\"data-live\"", head)

    def test_a_live_tick_upgrades_the_tier_badge(self):
        # The cell showed "T3" beside a source line reading "T1" - two
        # provenances for one number. A venue tick is Tier 1 in both places.
        self.assertIn('tb.textContent="T1"; tb.className="t t1";', self.doc)

    def test_live_source_line_does_not_overflow(self):
        # It read "Binance stream · T1 · 18:53Z · LIVE" and clipped mid-word.
        self.assertNotIn('+"Z · LIVE"', self.doc)

    # -- the age counter may only ever move forward ------------------------
    def test_age_stamp_only_advances(self):
        # Only D.newest is monotonic: it drives the age counter. LIVE.at is the
        # last tick's own stamp and must match the price displayed beside it.
        self.assertIn("if(isNaN(prev)||ms>prev) D.newest=", self.doc)
        self.assertIn("LIVE.at=ms;", self.doc)

    def test_unknown_change_is_shown_as_unknown(self):
        # Coinbase spot quotes no 24h change. Leaving the snapshot's delta beside
        # a live price would attribute a stale number to a fresh one.
        self.assertIn('d.textContent="—"; d.className="dlt flat";', self.doc)
        self.assertIn('td.textContent="—"; td.className="d flat";', self.doc)

    def test_age_reads_the_newest_observation(self):
        self.assertIn("Date.parse(D.newest||D.captured)", self.doc)

    # -- a silent socket must not leave the badge claiming LIVE ------------
    def test_stamp_is_reparsed_before_use(self):
        # ok() parses a local copy; apply() must not hand the raw argument to
        # new Date(), or a string stamp yields an Invalid Date that throws
        # AFTER the price has already been written.
        body = self.doc[self.doc.index("function apply(key, price"):]
        body = body[:body.index("var txt=money(price);")]
        self.assertIn("ms=parseFloat(ms);", body)

    def test_bootstrap_cannot_abort_the_script_tag(self):
        # The live client shares a <script> with the ambient-field animation. An
        # uncaught throw here - a CSP SecurityError, say - would take that with it.
        boot = self.doc[self.doc.index("  try{\n    stream();"):]
        boot = boot[:boot.index("})();")]
        self.assertIn("setInterval(rest, 20000)", boot)
        self.assertIn("setInterval(badge, 5000)", boot)
        self.assertIn("}catch(err){}", boot)

    def test_watchdog(self):
        self.assertIn("WATCHDOG=60000", self.doc)
        self.assertIn("(Date.now()-LIVE.rx)<WATCHDOG", self.doc)
        self.assertIn("setInterval(badge, 5000)", self.doc)

    # -- the two transports must not fight over the price ------------------
    def test_stream_outranks_the_rest_fallback(self):
        self.assertIn("STREAM_OWNS=30000", self.doc)
        rest = self.doc[self.doc.index("function rest()"):]
        rest = rest[:rest.index("Under an artifact's CSP")]
        self.assertEqual(rest.count("Date.now()-LIVE.rx < STREAM_OWNS"), 2,
                         "REST must stand down before the fetch AND after it, "
                         "or a request in flight when a tick lands still wins")

    def test_reconnect_is_latched_and_backs_off(self):
        # error-then-close fires both handlers for one socket; without the latch
        # every drop doubles the number of pending reconnects.
        self.assertIn("if(reconnecting) return;", self.doc)
        self.assertIn("Math.min(60000, 2000*retry)", self.doc)

    # -- rounding is the house rule on both sides of the language line -----
    def test_money_uses_floor_half_up(self):
        self.assertIn("Math.floor(v+0.5).toLocaleString", self.doc)
        self.assertNotIn("Math.round(v", self.doc)

    def test_formatting_matches_the_python_renderer(self):
        # _fmt renders usd >= 1000 with thousands separators and no decimals;
        # money() must agree or a live tick would visibly restyle the cell.
        self.assertEqual(terminal._fmt(81250.0, "usd"), "81,250")
        self.assertEqual(terminal._fmt(999.5, "usd"), "999.50")


class TestPanelCopyIsTrue(unittest.TestCase):
    """The panel explains the two modes. It must not overclaim either."""

    @classmethod
    def setUpClass(cls):
        cls.doc = terminal.render(seed.build())

    def test_says_an_artifact_cannot_fetch(self):
        self.assertIn("blocks fetch, XHR and WebSocket", self.doc)

    def test_says_a_local_file_can(self):
        self.assertIn("open it in your own browser", self.doc)

    def test_does_not_promise_live_unconditionally(self):
        # No sentence may claim the page is live without naming the condition.
        self.assertIn("The badge above says which one you have", self.doc)


if __name__ == "__main__":
    unittest.main()
