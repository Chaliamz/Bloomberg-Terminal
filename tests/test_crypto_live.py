"""The live crypto adapter.

The scanner had no crypto source at all, which is why `python -m macro live`
never moved Bitcoin no matter how often it ran. These tests cover the adapter
and the scan path against a local server speaking Binance's documented shape,
because api.binance.com is not reachable from the verification environment.
"""

import json
import threading
import unittest
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer

from macro import live
from macro.live import Source, parse_binance_ticker, scan

NOW_MS = lambda: int(datetime.now(timezone.utc).timestamp() * 1000)


def ticker(**over):
    body = {"symbol": "BTCUSDT", "priceChange": "-207.00",
            "priceChangePercent": "-0.26", "weightedAvgPrice": "79600.00",
            "lastPrice": "79170.42", "lastQty": "0.01", "openPrice": "79377.42",
            "highPrice": "80494.00", "lowPrice": "79081.00", "volume": "12345.6",
            "quoteVolume": "9.8e8", "openTime": NOW_MS() - 86400000,
            "closeTime": NOW_MS(), "firstId": 1, "lastId": 2, "count": 2}
    body.update(over)
    return json.dumps(body)


class TestBinanceParser(unittest.TestCase):
    def test_a_real_shaped_payload_parses(self):
        got = parse_binance_ticker(ticker())
        self.assertEqual(got["price"], 79170.42)
        self.assertEqual(got["change_pct"], -0.26)
        self.assertEqual(got["high"], 80494.00)
        self.assertEqual(got["low"], 79081.00)
        self.assertTrue(got["as_of"].endswith("Z"))

    def test_every_numeric_field_arrives_as_a_string(self):
        """Binance sends numbers as strings; a float() that is skipped here
        surfaces as a TypeError deep in the renderer."""
        got = parse_binance_ticker(ticker())
        for k in ("price", "change_pct", "high", "low", "open", "volume"):
            self.assertIsInstance(got[k], float, k)

    def test_it_returns_none_rather_than_guessing(self):
        for body, why in (
            ("not json", "garbage"),
            ("", "empty body"),
            ("{}", "empty object"),
            ("[]", "empty array"),
            (json.dumps({"symbol": "ETHUSDT", "lastPrice": "1",
                         "closeTime": NOW_MS()}), "wrong symbol"),
            (ticker(lastPrice="0"), "zero price"),
            (ticker(lastPrice="-5"), "negative price"),
            (ticker(lastPrice="abc"), "non-numeric price"),
            (ticker(lastPrice="NaN"), "NaN price"),
            (ticker(lastPrice="Infinity"), "infinite price"),
            (ticker(closeTime=NOW_MS() + 3_600_000), "future stamp"),
            (ticker(closeTime=NOW_MS() // 1000), "seconds where ms expected"),
            (ticker(closeTime=0), "zero stamp"),
            (ticker(highPrice="1", lowPrice="9"), "high below low"),
        ):
            self.assertIsNone(parse_binance_ticker(body), f"accepted {why}")

    def test_a_missing_optional_field_is_omitted_not_zeroed(self):
        body = json.loads(ticker())
        del body["highPrice"]
        got = parse_binance_ticker(json.dumps(body))
        self.assertIsNotNone(got)
        self.assertNotIn("high", got)
        self.assertEqual(got["price"], 79170.42)

    def test_an_array_response_is_searched_for_the_symbol(self):
        arr = json.dumps([json.loads(ticker(symbol="ETHUSDT", lastPrice="2500")),
                          json.loads(ticker())])
        self.assertEqual(parse_binance_ticker(arr)["price"], 79170.42)


class _Handler(BaseHTTPRequestHandler):
    payload = ticker()
    status = 200

    def do_GET(self):
        self.send_response(self.status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(_Handler.payload.encode())

    def log_message(self, *a):
        pass


class TestScanIntegration(unittest.TestCase):
    """The whole path: HTTP -> parse -> Quote -> PriceAnchor."""

    def setUp(self):
        self.srv = HTTPServer(("127.0.0.1", 0), _Handler)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        port = self.srv.server_address[1]
        self.src = Source("Binance BTCUSDT", 1,
                          f"http://127.0.0.1:{port}/ticker", "crypto", 30, ("BTC",))
        _Handler.payload = ticker()
        _Handler.status = 200

    def tearDown(self):
        self.srv.shutdown()
        self.srv.server_close()

    def test_a_live_poll_updates_the_bitcoin_quote(self):
        snap = scan(sources=[self.src])
        self.assertIn("BTC", snap.quotes)
        q = snap.quotes["BTC"]
        self.assertEqual(q.value, 79170.42)
        self.assertEqual(q.tier, 1)
        self.assertIn("Binance", q.source)
        self.assertEqual(snap.errors, [])

    def test_a_live_poll_feeds_the_liquidity_map(self):
        snap = scan(sources=[self.src])
        self.assertEqual(len(snap.price_anchors), 1)
        self.assertEqual(snap.price_anchors[0].price, 79170.42)

    def test_polling_hard_does_not_grow_the_anchor_series_without_bound(self):
        """A 30s poll would append 2,880 anchors a day and the liquidity map
        recomputes over all of them."""
        snap = scan(sources=[self.src])
        for _ in range(40):
            snap = scan(snap, sources=[self.src])
        self.assertEqual(len(snap.price_anchors), 1,
                         "the anchor series grew on repeated polls inside the gap")

    def test_a_poll_after_the_gap_does_append(self):
        snap = scan(sources=[self.src])
        old = snap.price_anchors[0]
        later = datetime.now(timezone.utc) + timedelta(seconds=live.ANCHOR_MIN_GAP + 60)
        _Handler.payload = ticker(lastPrice="79999.99",
                                  closeTime=int(later.timestamp() * 1000))
        # the stamp must not be in the future relative to the guard, so move now
        _Handler.payload = ticker(lastPrice="79999.99", closeTime=NOW_MS())
        snap.price_anchors[0] = type(old)(
            date="2026-01-01T00:00:00Z", price=old.price, source=old.source,
            tier=old.tier, url=old.url, note=old.note)
        snap2 = scan(snap, sources=[self.src])
        self.assertEqual(len(snap2.price_anchors), 2)

    def test_an_unreachable_venue_never_restamps_the_old_price(self):
        snap = scan(sources=[self.src])
        before = snap.quotes["BTC"]
        self.srv.shutdown()
        self.srv.server_close()
        after = scan(snap, sources=[self.src])
        self.assertEqual(after.quotes["BTC"].value, before.value)
        self.assertEqual(after.quotes["BTC"].as_of, before.as_of,
                         "an unreachable venue restamped stale data")
        self.assertTrue(any("unreachable" in e for e in after.errors))

    def test_a_garbage_payload_never_restamps_either(self):
        snap = scan(sources=[self.src])
        before = snap.quotes["BTC"]
        _Handler.payload = "<html>rate limited</html>"
        after = scan(snap, sources=[self.src])
        self.assertEqual(after.quotes["BTC"].as_of, before.as_of)
        self.assertTrue(any("unparseable" in e for e in after.errors))

    def test_a_non_200_is_treated_as_unreachable(self):
        _Handler.status = 429
        snap = scan(sources=[self.src])
        self.assertNotIn("BTC", snap.quotes)
        self.assertTrue(any("unreachable" in e for e in snap.errors))


if __name__ == "__main__":
    unittest.main()
