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

import json
import re
import shutil
import subprocess
import unittest

from macro import seed, terminal
from macro.live import BROWSER_FEEDS, NOT_LIVE_REASON


def payload(doc: str) -> dict:
    m = re.search(r"window\.__TERM__=(\{.*?\});</script>", doc, re.S)
    assert m, "no __TERM__ payload"
    return json.loads(m.group(1))


class TestFeedRegistry(unittest.TestCase):
    """The page's claims and the sockets it opens come from ONE list."""

    @classmethod
    def setUpClass(cls):
        cls.doc = terminal.render(seed.build())
        cls.p = payload(cls.doc)

    def test_registry_travels_with_the_data(self):
        self.assertEqual(set(self.p["feeds"]), {f["key"] for f in BROWSER_FEEDS})

    def test_every_streaming_feed_is_in_the_socket_url(self):
        want = [f["stream"] for f in BROWSER_FEEDS if f.get("stream")]
        self.assertTrue(want, "no streaming feeds at all")
        for st in want:
            self.assertIn(st, self.p["wsUrl"], st)
        # combined-stream form, not the single-stream /ws/ path
        self.assertIn("/stream?streams=", self.p["wsUrl"])

    def test_socket_url_has_no_extra_subscriptions(self):
        # A stream nothing routes would arrive, match no key and be dropped -
        # silent waste, and a symbol map that no longer describes the socket.
        subs = self.p["wsUrl"].split("streams=", 1)[1].split("/")
        self.assertEqual(sorted(subs),
                         sorted(f["stream"] for f in BROWSER_FEEDS if f.get("stream")))

    def test_status_table_lists_every_feed_and_every_refusal(self):
        for f in BROWSER_FEEDS:
            self.assertIn(f["label"], self.doc, f["label"])
        for asset, _why in NOT_LIVE_REASON:
            self.assertIn(terminal.e(asset), self.doc, asset)

    def test_unreachable_assets_say_why(self):
        # "Never offer a control whose view the data cannot support - gate it
        # and state why." A blank cell invites the reader to assume a bug.
        self.assertIn("SNAPSHOT", self.doc)
        self.assertIn("Access-Control-Allow-Origin", self.doc)
        self.assertIn("API key", self.doc)

    def test_the_board_covers_the_assets_that_can_be_live(self):
        keys = {f["key"] for f in BROWSER_FEEDS}
        self.assertEqual(keys, {"BTC", "ETH", "GOLD", "DXY"})
        rt = {f["key"] for f in BROWSER_FEEDS if f["mode"] == "realtime"}
        self.assertEqual(rt, {"BTC", "ETH", "GOLD"})

    def test_every_feed_key_is_a_real_quote_on_the_board(self):
        snap = seed.build()
        for f in BROWSER_FEEDS:
            self.assertIn(f["key"], snap.quotes, f["key"])
            self.assertEqual(snap.quotes[f["key"]].unit, f["unit"], f["key"])


class TestLiveClient(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.snap = seed.build()
        cls.doc = terminal.render(cls.snap)

    # -- the hooks the client writes through ------------------------------
    def test_quote_cells_carry_a_key(self):
        keys = set(re.findall(r'<div class="q" data-k="([^"]+)"', self.doc))
        for f in BROWSER_FEEDS:
            self.assertIn(f["key"], keys, f["key"])
        self.assertGreaterEqual(len(keys), 10, keys)

    def test_tape_items_carry_a_key(self):
        # doubled marquee: each item appears twice and both must update
        for f in BROWSER_FEEDS:
            self.assertEqual(self.doc.count('class="tk" data-tk="%s"' % f["key"]), 2,
                             f["key"])

    def test_badge_targets_exist(self):
        for i in ('id="lv-state"', 'id="lv-px"'):
            self.assertIn(i, self.doc, i)

    def test_badge_starts_honest(self):
        m = re.search(r'<b id="lv-state" data-on="0">([^<]+)</b>', self.doc)
        self.assertIsNotNone(m, "badge must ship off and say so")
        self.assertIn("NO FEED", m.group(1))

    # -- both transports, and why each is there ---------------------------
    def test_websocket_transport(self):
        self.assertIn("wss://stream.binance.com:9443/stream?streams=",
                      payload(self.doc)["wsUrl"])
        # REST is not usable from a browser: Binance sends no ACAO header.
        self.assertNotIn('api.binance.com/api/v3/ticker/24hr"', self.doc)

    def test_rest_fallback_transport(self):
        self.assertIn("api.coinbase.com/v2/prices/{pair}/spot",
                      payload(self.doc)["spotUrl"])

    def test_fx_transport(self):
        self.assertIn("frankfurter.dev", payload(self.doc)["fxUrl"])

    def test_no_test_endpoint_leaked(self):
        self.assertNotIn("127.0.0.1", self.doc)
        self.assertNotIn("localhost", self.doc)

    # -- the validation gate, mirrored from the Python adapter -------------
    def test_gate_rejects_the_same_things_as_the_python_adapter(self):
        gate = self.doc[self.doc.index("function ok(price, ms)"):]
        gate = gate[:gate.index("function grp")]
        for token, why in (
            ("isFinite(price)", "NaN / Infinity price"),
            ("price<=0", "non-positive price"),
            ("isFinite(ms)", "NaN / Infinity stamp"),
            ("ms>now+300000", "future stamp / clock skew"),
            ("ms<now-604800000", "seconds-epoch sent as milliseconds"),
        ):
            self.assertIn(token, gate, f"gate lost its check for {why}")

    def test_stream_checks_symbol_and_range(self):
        # routing by symbol replaces the hard-coded BTCUSDT check: an event for a
        # symbol we did not subscribe to must not land on any cell
        self.assertIn("var key=SYM[t.s];", self.doc)
        self.assertIn("if(!key) return;", self.doc)
        self.assertIn("hi<lo", self.doc, "high-below-low check")

    def test_a_rejected_tick_writes_nothing(self):
        body = self.doc[self.doc.index("function apply(key, price"):]
        body = body[:body.index("/* ---- 1. Binance combined stream")]
        head = body[:body.index("var txt=fmt(price, F.unit);")]
        self.assertIn("if(!price)", head)
        self.assertIn("return false", head)
        self.assertNotIn("textContent", head)
        self.assertNotIn('setAttribute("data-live"', head)

    def test_stamp_is_reparsed_before_use(self):
        body = self.doc[self.doc.index("function apply(key, price"):]
        body = body[:body.index("var txt=fmt(price, F.unit);")]
        self.assertIn("ms=parseFloat(ms);", body)

    # -- the age counter may only ever move forward ------------------------
    def test_age_stamp_only_advances(self):
        self.assertIn("if(isNaN(prev)||ms>prev) D.newest=", self.doc)
        self.assertIn("L.at=ms;", self.doc)

    def test_only_realtime_ticks_touch_the_age_counter(self):
        # A daily ECB fixing is real data but it is NOT evidence that the board
        # as a whole is current, so it must not reset the masthead to zero.
        self.assertIn("if(opts.advance && typeof D!==", self.doc)
        fx = self.doc[self.doc.index("function fx()"):]
        fx = fx[:fx.index("try{")]
        self.assertIn("advance:false", fx)
        stream = self.doc[self.doc.index("sock.onmessage"):]
        stream = stream[:stream.index("sock.onclose")]
        self.assertIn("advance:true", stream)

    def test_age_reads_the_newest_observation(self):
        self.assertIn("Date.parse(D.newest||D.captured)", self.doc)

    # -- a silent socket must not leave the badge claiming LIVE ------------
    def test_watchdog(self):
        self.assertIn("WATCHDOG=60000", self.doc)
        self.assertIn("(Date.now()-L.rx)<WATCHDOG", self.doc)
        self.assertIn("setInterval(badge, 5000)", self.doc)

    # -- the two transports must not fight over the price ------------------
    def test_stream_outranks_the_rest_fallback(self):
        self.assertIn("STREAM_OWNS=30000", self.doc)
        rest = self.doc[self.doc.index("function rest()"):]
        rest = rest[:rest.index("/* ---- 3. Dollar index")]
        self.assertEqual(rest.count("STREAM_OWNS"), 2,
                         "REST must stand down before the fetch AND after it, "
                         "or a request in flight when a tick lands still wins")

    def test_reconnect_is_latched_and_backs_off(self):
        self.assertIn("if(reconnecting) return;", self.doc)
        self.assertIn("Math.min(60000, 2000*retry)", self.doc)

    def test_bootstrap_cannot_abort_the_script_tag(self):
        boot = self.doc[self.doc.index("  try{\n    stream();"):]
        boot = boot[:boot.index("})();")]
        self.assertIn("setInterval(rest, 20000)", boot)
        self.assertIn("setInterval(badge, 5000)", boot)
        self.assertIn("}catch(err){}", boot)

    # -- a proxy and a derived figure are not live venue prints -------------
    def test_proxy_and_derived_are_visually_distinct(self):
        self.assertIn('cell.setAttribute(opts.derived?"data-fix":"data-live","1")',
                      self.doc)
        self.assertIn('.q[data-proxy="1"] .val{color:var(--amber)}', self.doc)
        self.assertIn('.q[data-fix="1"] .val{color:var(--live)}', self.doc)

    def test_gold_is_labelled_a_proxy_not_spot(self):
        gold = next(f for f in BROWSER_FEEDS if f["key"] == "GOLD")
        self.assertTrue(gold["proxy"])
        self.assertEqual(gold["src"], "Binance PAXGUSDT")
        self.assertIn("PROXY, not spot XAU", gold["why"])
        self.assertEqual(gold["tier"], 2, "a proxy is not Tier 1 for the thing quoted")

    def test_dxy_needs_every_leg(self):
        fx = self.doc[self.doc.index("function fx()"):]
        fx = fx[:fx.index("try{")]
        self.assertIn('typeof raw!=="number" || !isFinite(raw) || raw<=0', fx)
        self.assertIn("return;", fx)

    def test_live_cell_keeps_provenance(self):
        self.assertIn('" · conf "+(opts.conf||"0.95")', self.doc)

    def test_a_live_tick_sets_the_feed_tier(self):
        self.assertIn('tb.textContent="T"+tier; tb.className="t t"+tier;', self.doc)

    def test_live_source_line_does_not_overflow(self):
        self.assertNotIn('+"Z · LIVE"', self.doc)


class TestCrossLanguageFormatting(unittest.TestCase):
    """fmt() in the page and _fmt() in Python format the same units.

    A live tick replaces a rendered snapshot value in the same cell, so if the
    two disagree the number visibly restyles itself the moment a feed connects.
    Both sides round floor(x + 0.5); Python's format spec alone rounds half to
    even, which is why _half_up exists.
    """

    def test_python_rounds_half_up_not_half_even(self):
        self.assertEqual(terminal._fmt(2.675, "index"), "2.68")   # half-even: 2.67
        self.assertEqual(terminal._fmt(0.125, "index"), "0.13")   # half-even: 0.12
        self.assertEqual(terminal._fmt(1000.5, "usd"), "1,001")

    @unittest.skipUnless(shutil.which("node"), "node not installed")
    def test_js_and_python_agree(self):
        doc = terminal.render(seed.build())
        js = doc[doc.index("  function grp(v, dp){"):doc.index("  function live(key)")]
        cases = []
        for unit in ("usd", "usd_oz", "usd_bbl", "index", "pct"):
            for v in (0.0049, 0.125, 2.675, 14.32, 99.16, 999.994, 999.995,
                      1000.0, 1000.5, 2507.7, 4429.0, 7707.0, 53414.25,
                      78370.62, 81249.5, 123456.789):
                cases.append((v, unit))
        prog = (js + "\nvar C=" + json.dumps([[v, u] for v, u in cases]) + ";\n"
                "var out=[];for(var i=0;i<C.length;i++){out.push(fmt(C[i][0],C[i][1]));}\n"
                "console.log(JSON.stringify(out));\n")
        r = subprocess.run(["node", "-e", prog], capture_output=True, text=True,
                           timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        got = json.loads(r.stdout)
        want = [terminal._fmt(v, u) for v, u in cases]
        bad = [(cases[i], want[i], got[i]) for i in range(len(cases))
               if want[i] != got[i]]
        self.assertEqual(bad, [], f"{len(bad)} formatting divergences: {bad[:8]}")


if __name__ == "__main__":
    unittest.main()
