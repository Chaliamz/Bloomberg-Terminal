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


WSS = "wss://stream.binance.com:9443/stream?streams="
SPOT = "https://api.coinbase.com/v2/prices/{pair}/spot"
FX = "https://api.frankfurter.dev/v1/latest"


def endpoints(html: str) -> dict:
    """The URLs the shipped page will actually open, read from its payload."""
    m = re.search(r"window\.__TERM__=(\{.*?\});</script>", html, re.S)
    assert m, "no __TERM__ payload in the page"
    return json.loads(m.group(1))


def stage(html: str, tmp: str, ws_port=None, spot_port=None, fx_port=None) -> str:
    """A copy of the page pointed at the local mocks. Never the shipped file."""
    p = endpoints(html)
    # port 1 is refused instantly, which is the "nothing reachable" case
    ws = (f"ws://127.0.0.1:{ws_port}/stream" if ws_port else "ws://127.0.0.1:1/dead")
    spot = (f"http://127.0.0.1:{spot_port}/spot" if spot_port
            else "http://127.0.0.1:1/dead")
    fx = (f"http://127.0.0.1:{fx_port}/fx" if fx_port else "http://127.0.0.1:1/dead")
    assert p["wsUrl"].startswith(WSS), p["wsUrl"]
    assert p["spotUrl"] == SPOT, p["spotUrl"]
    assert p["fxUrl"].startswith(FX), p["fxUrl"]
    out = (html.replace(p["wsUrl"], ws)
               .replace(p["spotUrl"], spot)
               .replace(p["fxUrl"], fx))
    path = os.path.join(tmp, f"stage-{ws_port}-{spot_port}-{fx_port}.html")
    with open(path, "w") as fh:
        fh.write(out)
    return path


READ = """() => {
  const one = k => {
    const cell = document.querySelector('.q[data-k="' + k + '"]');
    if (!cell) return null;
    return {
      val: cell.querySelector(".val").textContent,
      src: cell.querySelector(".src").textContent,
      live: cell.getAttribute("data-live"),
      fix: cell.getAttribute("data-fix"),
      proxy: cell.getAttribute("data-proxy"),
      tier: (cell.querySelector(".lab .t") || {}).textContent || "",
      tape: (document.querySelector('.tk[data-tk="' + k + '"] .v') || {}).textContent,
    };
  };
  const st = document.getElementById("lv-state");
  const out = {
    state: st ? st.textContent : null,
    on: st ? st.getAttribute("data-on") : null,
    px: (document.getElementById("lv-px") || {}).textContent,
    age: (document.getElementById("age") || {}).textContent,
  };
  ["BTC", "ETH", "GOLD", "DXY"].forEach(k => { out[k] = one(k); });
  // flat aliases keep the BTC assertions readable
  const b = out.BTC || {};
  out.val = b.val; out.src = b.src; out.live = b.live; out.tier = b.tier;
  out.tape = b.tape;
  return out;
}"""


def ticker(price, *, sym="BTCUSDT", pct=1.25, hi=None, lo=None, ms=None,
           combined=True):
    """A Binance @ticker event, wrapped the way a COMBINED stream wraps it."""
    now = int(time.time() * 1000)
    data = {
        "e": "24hrTicker", "E": now if ms is None else ms, "s": sym,
        "c": f"{price}", "P": f"{pct}",
        "h": f"{hi if hi is not None else abs(price) * 1.02}",
        "l": f"{lo if lo is not None else abs(price) * 0.98}",
        "o": f"{price}",
    }
    if not combined:
        return json.dumps(data)
    return json.dumps({"stream": sym.lower() + "@ticker", "data": data})


def fx_body(date="2026-09-08", **over):
    rates = {"EUR": 1 / 1.14, "JPY": 150.0, "GBP": 1 / 1.32,
             "CAD": 1.38, "SEK": 9.50, "CHF": 0.80}
    rates.update(over)
    return json.dumps({"amount": 1, "base": "USD", "date": date, "rates": rates})


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
        base = await load(stage(html, tmp), 1200)
        if base["val"] is None:
            bad.append("no BTC quote cell to update")
        notes.append(f"snapshot BTC {base['val']}  state={base['state']!r}")

        # -- 1. no feed at all: the page must be byte-identical in what it shows
        dead = await load(stage(html, tmp), 3000)
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
        good = await load(stage(html, tmp, ws.port), 2600)
        ws.shutdown()
        if good["val"] != "81,250":
            bad.append(f"stream tick not applied: val={good['val']!r}")
        if good["on"] != "1" or "Binance stream" not in (good["state"] or ""):
            bad.append(f"stream tick did not light the badge: {good['state']!r}")
        if good["live"] != "1":
            bad.append("quote cell not marked live")
        if good["tier"] != "T1":
            bad.append(f"tier badge contradicts the live source line: {good['tier']!r} "
                       "(a venue's own last trade is Tier 1)")
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
        sv = await load(stage(html, tmp, ws.port), 2600)
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
            got = await load(stage(html, tmp, s.port), 2200)
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
        both = await load(stage(html, tmp, ws.port, spot.port), 23000)
        hits = spot.hits
        ws.shutdown()
        spot.shutdown()
        if both["val"] != "81,999":
            bad.append(f"REST overwrote the stream: {both['val']!r} (expected 81,999)")
        if "Binance stream" not in (both["state"] or ""):
            bad.append(f"venue flicker: badge reads {both['state']!r}")
        if hits != 1:
            bad.append(f"REST polled {hits}x while the stream was live; expected the "
                       "one call at load, then silence for STREAM_OWNS")
        notes.append(f"both feeds   -> {both['val']} · {both['state']!r} "
                     f"(stream wins, REST polled {hits}x in 23s)")

        # -- 5b. every streamed asset must land on its OWN cell ---------------
        ws = TickerWS([ticker(81250.0, sym="BTCUSDT"),
                       ticker(2611.4, sym="ETHUSDT", pct=-0.8),
                       ticker(4402.55, sym="PAXGUSDT", pct=0.4)])
        ws.start()
        multi = await load(stage(html, tmp, ws.port), 2800)
        ws.shutdown()
        for key, want, tier in (("BTC", "81,250", "T1"),
                                ("ETH", "2,611", "T1"),
                                ("GOLD", "4,403", "T2")):
            cell = multi.get(key) or {}
            if cell.get("val") != want:
                bad.append(f"{key} not updated by the combined stream: "
                           f"{cell.get('val')!r} (expected {want})")
            if cell.get("tier") != tier:
                bad.append(f"{key} tier badge {cell.get('tier')!r}, expected {tier}")
            if cell.get("tape") != want:
                bad.append(f"{key} ticker tape not updated: {cell.get('tape')!r}")
        # gold is a PROXY: it must not be dressed as a live venue print of XAU
        g = multi.get("GOLD") or {}
        if g.get("proxy") != "1":
            bad.append("gold cell is not marked a proxy")
        if "PAXG" not in (g.get("src") or ""):
            bad.append(f"gold source line hides the proxy: {g.get('src')!r}")
        notes.append("combined     -> BTC %s · ETH %s · GOLD %s (proxy marked)"
                     % (multi["BTC"]["val"], multi["ETH"]["val"], multi["GOLD"]["val"]))

        # -- 5c. an unsubscribed symbol must land nowhere ---------------------
        ws = TickerWS([ticker(999999.0, sym="DOGEUSDT")])
        ws.start()
        stray = await load(stage(html, tmp, ws.port), 2200)
        ws.shutdown()
        for key in ("BTC", "ETH", "GOLD"):
            if (stray.get(key) or {}).get("val") != (base.get(key) or {}).get("val"):
                bad.append(f"a DOGEUSDT event moved {key}")
        notes.append("stray symbol -> routed nowhere, all cells unchanged")

        # -- 5d. the dollar index: derived, dated, and NOT page-fresh ---------
        fxs = SpotHTTP(fx_body())
        fxs.start()
        dxy = await load(stage(html, tmp, None, None, fxs.port), 2600)
        fxs.shutdown()
        d = dxy.get("DXY") or {}
        if d.get("val") != "99.85":
            bad.append(f"DXY not derived from the fixing: {d.get('val')!r} "
                       "(expected 99.85)")
        if d.get("fix") != "1":
            bad.append("DXY not marked as a fixing")
        if d.get("live") == "1":
            bad.append("a daily fixing must not be marked live")
        if "2026-09-08" not in (d.get("src") or ""):
            bad.append(f"DXY does not show the fixing date: {d.get('src')!r}")
        if dxy["age"] == "00h 00m":
            bad.append("a daily ECB fixing reset the page age counter")
        notes.append(f"ecb fixing   -> DXY {d.get('val')} · {d.get('src')}")

        # -- 5e. a fixing missing one leg is not a dollar index ---------------
        for name, body in (
            ("missing CHF", json.dumps({"date": "2026-09-08", "rates":
                {"EUR": 0.87, "JPY": 150.0, "GBP": 0.75, "CAD": 1.38, "SEK": 9.5}})),
            ("zero leg", fx_body(SEK=0)),
            ("negative leg", fx_body(CAD=-1.4)),
            ("string leg", fx_body(JPY="150")),
            ("no date", json.dumps({"rates": json.loads(fx_body())["rates"]})),
            ("no rates", json.dumps({"date": "2026-09-08"})),
        ):
            fxs = SpotHTTP(body)
            fxs.start()
            r = await load(stage(html, tmp, None, None, fxs.port), 2200)
            fxs.shutdown()
            if (r.get("DXY") or {}).get("val") != (base.get("DXY") or {}).get("val"):
                bad.append(f"DXY REJECTION FAILED [{name}]: value moved to "
                           f"{(r.get('DXY') or {}).get('val')!r}")
            if (r.get("DXY") or {}).get("fix") == "1":
                bad.append(f"DXY REJECTION FAILED [{name}]: marked as a fixing")
        notes.append("ecb refused  -> 6 unusable fixings, DXY unchanged in all")

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
    if FX not in html:
        bad.append("shipped page lost the ECB fixing endpoint")
    for st in ("btcusdt@ticker", "ethusdt@ticker", "paxgusdt@ticker"):
        if st not in html:
            bad.append(f"shipped page lost the {st} subscription")
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
