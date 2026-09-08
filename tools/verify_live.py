#!/usr/bin/env python3
"""Live-feed verification: does the in-browser client actually work, and does
it stay silent when it cannot?

The terminal ships a live client that opens a Binance `btcusdt@ticker`
websocket and falls back to polling Coinbase spot. Static tests can prove the
code is present; only a browser can prove it runs, updates the right cells, and
- the part that matters most - leaves the page completely untouched when the
feed is unreachable or sends something that fails validation.

This harness stands up two local servers shaped like those venues, rewrites the
two endpoint URLs in a COPY of the page, and drives it in Chromium. A separate
check asserts the shipped page still carries the real endpoints, so the rewrite
cannot leak into what the user gets.

    python3 tools/verify_live.py [path-to-html]
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import os
import re
import shutil
import socket
import struct
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools.verify_terminal import find_chromium  # noqa: E402

GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"


# --------------------------------------------------------------------------
# A websocket server small enough to read. RFC 6455 handshake, server->client
# text frames only, unmasked, payloads under 65,536 bytes.
# --------------------------------------------------------------------------
class TickerWS(threading.Thread):
    def __init__(self, frames):
        super().__init__(daemon=True)
        self.frames = frames          # list of str payloads to send, in order
        self.sock = socket.socket()
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(("127.0.0.1", 0))
        self.sock.listen(4)
        self.port = self.sock.getsockname()[1]
        self.connections = 0
        self.stop = threading.Event()

    def run(self):
        self.sock.settimeout(0.4)
        while not self.stop.is_set():
            try:
                conn, _ = self.sock.accept()
            except socket.timeout:
                continue
            except OSError:
                return
            threading.Thread(target=self._serve, args=(conn,), daemon=True).start()

    def _serve(self, conn):
        try:
            conn.settimeout(3)
            req = b""
            while b"\r\n\r\n" not in req:
                chunk = conn.recv(4096)
                if not chunk:
                    return
                req += chunk
            m = re.search(rb"Sec-WebSocket-Key:\s*(\S+)", req, re.I)
            if not m:
                conn.close()
                return
            accept = base64.b64encode(
                hashlib.sha1(m.group(1) + GUID.encode()).digest()).decode()
            conn.sendall(
                b"HTTP/1.1 101 Switching Protocols\r\n"
                b"Upgrade: websocket\r\nConnection: Upgrade\r\n"
                b"Sec-WebSocket-Accept: " + accept.encode() + b"\r\n\r\n")
            self.connections += 1
            for payload in self.frames:
                if self.stop.is_set():
                    break
                conn.sendall(self._frame(payload))
                time.sleep(0.12)
            # hold the socket open: a close would trigger the client's reconnect
            while not self.stop.is_set():
                time.sleep(0.1)
        except OSError:
            pass
        finally:
            try:
                conn.close()
            except OSError:
                pass

    @staticmethod
    def _frame(text: str) -> bytes:
        data = text.encode()
        if len(data) < 126:
            head = struct.pack("!BB", 0x81, len(data))
        else:
            head = struct.pack("!BBH", 0x81, 126, len(data))
        return head + data

    def shutdown(self):
        self.stop.set()
        try:
            self.sock.close()
        except OSError:
            pass


class SpotHTTP(threading.Thread):
    """Coinbase-shaped, CORS-open, and it counts what was asked of it."""

    def __init__(self, body: str | None, status: int = 200):
        super().__init__(daemon=True)
        outer = self

        class H(BaseHTTPRequestHandler):
            def do_GET(self):
                outer.hits += 1
                if body is None:
                    self.send_response(500)
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.end_headers()
                    return
                raw = body.encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

            def log_message(self, *a):
                pass

        self.hits = 0
        self.srv = HTTPServer(("127.0.0.1", 0), H)
        self.port = self.srv.server_port

    def run(self):
        self.srv.serve_forever(poll_interval=0.2)

    def shutdown(self):
        self.srv.shutdown()


WSS = "wss://stream.binance.com:9443/ws/btcusdt@ticker"
SPOT = "https://api.coinbase.com/v2/prices/BTC-USD/spot"


def stage(html: str, tmp: str, ws_port: int | None, spot_port: int | None) -> str:
    """A copy of the page pointed at the local mocks. Never the shipped file."""
    ws = (f"ws://127.0.0.1:{ws_port}/ws/btcusdt@ticker" if ws_port
          else "ws://127.0.0.1:1/dead")          # port 1: refused, instantly
    spot = (f"http://127.0.0.1:{spot_port}/spot" if spot_port
            else "http://127.0.0.1:1/dead")
    assert WSS in html and SPOT in html, "endpoint anchors missing from the page"
    out = html.replace(WSS, ws).replace(SPOT, spot)
    path = os.path.join(tmp, f"stage-{ws_port}-{spot_port}.html")
    with open(path, "w") as fh:
        fh.write(out)
    return path


READ = """() => {
  const cell = document.querySelector('.q[data-k="BTC"]');
  const st = document.getElementById("lv-state");
  return {
    val: cell ? cell.querySelector(".val").textContent : null,
    src: cell ? cell.querySelector(".src").textContent : null,
    live: cell ? cell.getAttribute("data-live") : null,
    state: st ? st.textContent : null,
    on: st ? st.getAttribute("data-on") : null,
    px: (document.getElementById("lv-px") || {}).textContent,
    age: (document.getElementById("age") || {}).textContent,
    tape: (document.querySelector('.tk[data-tk="BTC"] .v') || {}).textContent,
  };
}"""


def ticker(price, *, sym="BTCUSDT", pct=1.25, hi=None, lo=None, ms=None):
    now = int(time.time() * 1000)
    return json.dumps({
        "e": "24hrTicker", "E": now if ms is None else ms, "s": sym,
        "c": f"{price}", "P": f"{pct}",
        "h": f"{hi if hi is not None else price * 1.02}",
        "l": f"{lo if lo is not None else price * 0.98}",
        "o": f"{price}",
    })


async def run(path: str) -> int:
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        print("SKIP: playwright not installed")
        return 0
    binary = find_chromium()
    if not binary:
        print("SKIP: no chromium")
        return 0

    html = open(path).read()
    bad, notes = [], []
    tmp = tempfile.mkdtemp(prefix="verify-live-")

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(executable_path=binary,
                                           args=["--no-sandbox"])

        async def load(p, ms=2600):
            page = await browser.new_page(viewport={"width": 1400, "height": 900})
            await page.goto("file://" + p, wait_until="load")
            await page.wait_for_timeout(ms)
            out = await page.evaluate(READ)
            await page.close()
            return out

        # -- baseline: what the untouched snapshot says -----------------------
        base = await load(stage(html, tmp, None, None), 1200)
        if base["val"] is None:
            bad.append("no BTC quote cell to update")
        notes.append(f"snapshot BTC {base['val']}  state={base['state']!r}")

        # -- 1. no feed at all: the page must be byte-identical in what it shows
        dead = await load(stage(html, tmp, None, None), 3000)
        if dead["val"] != base["val"]:
            bad.append(f"dead feed changed the price {base['val']} -> {dead['val']}")
        if dead["live"] == "1" or dead["on"] == "1":
            bad.append("dead feed still claims LIVE")
        if "NO FEED" not in (dead["state"] or ""):
            bad.append(f"dead feed badge reads {dead['state']!r}")
        notes.append(f"no feed      -> {dead['state']!r}, price held at {dead['val']}")

        # -- 2. a good stream tick must land ----------------------------------
        ws = TickerWS([ticker(81234.5), ticker(81250.0)])
        ws.start()
        good = await load(stage(html, tmp, ws.port, None), 2600)
        ws.shutdown()
        if good["val"] != "81,250":
            bad.append(f"stream tick not applied: val={good['val']!r}")
        if good["on"] != "1" or "Binance stream" not in (good["state"] or ""):
            bad.append(f"stream tick did not light the badge: {good['state']!r}")
        if good["live"] != "1":
            bad.append("quote cell not marked live")
        if not re.search(r"conf \d", good["src"] or ""):
            bad.append(f"live cell lost its provenance line: {good['src']!r}")
        if good["tape"] != "81,250":
            bad.append(f"ticker tape not updated: {good['tape']!r}")
        if good["age"] not in ("00h 00m",):
            bad.append(f"age counter did not reset on a live tick: {good['age']!r}")
        notes.append(f"stream tick  -> {good['val']} · {good['state']!r} · age {good['age']}")

        # -- 2b. a venue that JSON-encodes the event time as a STRING ---------
        # The gate parses its own copy of ms; if the raw argument reaches
        # new Date() the result is an Invalid Date whose toISOString() throws,
        # and it throws after the price has already been written to the cell.
        now = int(time.time() * 1000)
        ws = TickerWS(['{"e":"24hrTicker","E":"%d","s":"BTCUSDT","c":"81111",'
                       '"P":"1","h":"99999","l":"1"}' % now])
        ws.start()
        sv = await load(stage(html, tmp, ws.port, None), 2600)
        ws.shutdown()
        if sv["val"] != "81,111":
            bad.append(f"string stamp broke the tick: val={sv['val']!r}")
        if sv["on"] != "1":
            bad.append(f"string stamp left the badge dark: {sv['state']!r}")
        if not re.match(r"^81,111\s+·\s+\d{2}:\d{2}:\d{2}Z$", sv["px"] or ""):
            bad.append(f"string stamp produced a bad clock: {sv['px']!r}")
        notes.append(f"string stamp -> {sv['val']} · {sv['px']}")

        # -- 3. every rejection case must leave the snapshot alone ------------
        cases = [
            ("wrong symbol", [ticker(90000, sym="ETHUSDT")]),
            ("high below low", [ticker(90000, hi=1.0, lo=99999.0)]),
            # hi/lo are pinned sane on purpose: ticker() derives them from the
            # price, so a negative price would produce hi<lo and be caught by the
            # range check instead of the gate. Mutation testing found that - the
            # probe passed while the gate it was meant to guard was deleted.
            ("negative price", [ticker(-5.0, hi=99999.0, lo=1.0)]),
            ("zero price", [ticker(0, hi=99999.0, lo=1.0)]),
            ("infinite price", ['{"e":"24hrTicker","E":%d,"s":"BTCUSDT",'
                                '"c":"Infinity","P":"1","h":"99999","l":"1"}' % now]),
            ("non-numeric price", ['{"e":"24hrTicker","E":%d,"s":"BTCUSDT","c":"abc","P":"1","h":"9","l":"1"}' % now]),
            ("seconds epoch as ms", [ticker(90000, ms=int(time.time()))]),
            ("future stamp", [ticker(90000, ms=now + 3600_000)]),
            ("malformed json", ["{not json"]),
            ("empty object", ["{}"]),
        ]
        for name, frames in cases:
            s = TickerWS(frames)
            s.start()
            got = await load(stage(html, tmp, s.port, None), 2200)
            s.shutdown()
            if got["val"] != base["val"]:
                bad.append(f"REJECTION FAILED [{name}]: price moved "
                           f"{base['val']} -> {got['val']}")
            if got["live"] == "1":
                bad.append(f"REJECTION FAILED [{name}]: cell marked live")
            if got["age"] == "00h 00m":
                bad.append(f"REJECTION FAILED [{name}]: age counter reset")
        notes.append(f"rejected     -> {len(cases)} bad payloads, page unchanged in all")

        # -- 4. Coinbase fallback carries the page when websockets are gone ---
        spot = SpotHTTP(json.dumps(
            {"data": {"base": "BTC", "currency": "USD", "amount": "80777.19"}}))
        spot.start()
        fb = await load(stage(html, tmp, None, spot.port), 2600)
        hits = spot.hits
        spot.shutdown()
        if fb["val"] != "80,777":
            bad.append(f"coinbase fallback not applied: {fb['val']!r}")
        if "Coinbase spot" not in (fb["state"] or ""):
            bad.append(f"fallback badge reads {fb['state']!r}")
        if hits < 1:
            bad.append("fallback never polled")
        notes.append(f"rest fallback-> {fb['val']} · {fb['state']!r} · {hits} poll(s)")

        # -- 5. the stream owns the price: REST must stand down ---------------
        ws = TickerWS([ticker(81999.0)])
        ws.start()
        spot = SpotHTTP(json.dumps({"data": {"amount": "70000.00"}}))
        spot.start()
        both = await load(stage(html, tmp, ws.port, spot.port), 2600)
        ws.shutdown()
        spot.shutdown()
        if both["val"] != "81,999":
            bad.append(f"REST overwrote the stream: {both['val']!r} (expected 81,999)")
        if "Binance stream" not in (both["state"] or ""):
            bad.append(f"venue flicker: badge reads {both['state']!r}")
        notes.append(f"both feeds   -> {both['val']} · {both['state']!r} (stream wins)")

        # -- 6. a 500 from the fallback must change nothing -------------------
        spot = SpotHTTP(None)
        spot.start()
        err = await load(stage(html, tmp, None, spot.port), 2400)
        spot.shutdown()
        if err["val"] != base["val"]:
            bad.append(f"HTTP 500 moved the price to {err['val']!r}")
        notes.append(f"rest 500     -> price held at {err['val']}")

        await browser.close()

    shutil.rmtree(tmp, ignore_errors=True)

    # -- 7. the shipped page must still point at the real venues -------------
    if WSS not in html:
        bad.append("shipped page lost the Binance websocket endpoint")
    if SPOT not in html:
        bad.append("shipped page lost the Coinbase fallback endpoint")
    if "127.0.0.1" in html:
        bad.append("a test endpoint leaked into the shipped page")

    for n in notes:
        print("  " + n)
    if bad:
        print("\nFAIL")
        for b in bad:
            print("  - " + b)
        return 1
    print("\nPASS: live client updates on a good tick, and changes nothing on a bad one.")
    return 0


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "board/macro-desk-live.html"
    sys.exit(asyncio.run(run(target)))
