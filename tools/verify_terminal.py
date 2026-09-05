#!/usr/bin/env python3
"""Live browser verification for the macro terminal.

Static tests prove the document is honest and well-formed. This proves the
parts that only exist at runtime actually run: the clock advances, countdowns
decrement, the data-age counter climbs, the session state is computed, the
ticker animates, the canvas paints, and nothing overflows at any viewport.

    python3 tools/verify_terminal.py [path-to-html]
"""

from __future__ import annotations

import asyncio
import glob
import os
import sys

VIEWPORTS = [("mobile", 390, 844), ("tablet", 900, 1180), ("desktop", 1720, 1050)]


def find_chromium() -> str | None:
    for pat in ("/opt/pw-browsers/chromium-*/chrome-linux/chrome",
                "/usr/bin/chromium", "/usr/bin/chromium-browser"):
        hits = sorted(glob.glob(pat))
        if hits:
            return hits[-1]
    return None


STATIC = """() => {
  const bad = [], n = s => document.querySelectorAll(s).length;
  const txt = id => (document.getElementById(id) || {}).textContent || "";

  if (n(".q") < 8) bad.push("quote grid thin: " + n(".q"));
  if (n(".sqr") < 8) bad.push("squawk thin: " + n(".sqr"));
  if (n(".gg") < 2) bad.push("sentiment gauges missing: " + n(".gg"));
  if (n(".ge") < 4) bad.push("geopolitical board thin: " + n(".ge"));
  if (n(".fl") < 3) bad.push("flows thin: " + n(".fl"));
  if (n(".lr") < 5) bad.push("liquidation ladder thin: " + n(".lr"));
  if (n("[data-when]") < 3) bad.push("too few countdowns");
  if (n(".tk") < 10) bad.push("ticker thin");

  // ticker must be doubled so the -50% marquee loops seamlessly
  const run = document.querySelector(".tape-run");
  if (!run) bad.push("no ticker track");
  else if (n(".tk") % 2 !== 0) bad.push("ticker not doubled: " + n(".tk"));

  // every quote cell must show a source line
  document.querySelectorAll(".q").forEach((q, i) => {
    const s = q.querySelector(".src");
    if (!s || !/conf \\d/.test(s.textContent)) bad.push("quote " + i + " lacks provenance");
    if (q.getBoundingClientRect().height < 40) bad.push("quote cell collapsed");
  });

  // every squawk row must carry a tier badge and a timestamp
  document.querySelectorAll(".sqr").forEach((a, i) => {
    if (!a.querySelector(".t")) bad.push("squawk " + i + " lacks a tier badge");
    if (!/\\d{2}:\\d{2}Z/.test(a.textContent)) bad.push("squawk " + i + " lacks a time");
    if (a.getBoundingClientRect().height < 30) bad.push("squawk row collapsed");
  });

  // gauges: the needle must sit inside its own arc, and the value must render
  document.querySelectorAll(".gg").forEach((g, i) => {
    const svg = g.querySelector("svg"), val = g.querySelector(".gv");
    if (!svg) { bad.push("gauge " + i + " has no svg"); return; }
    if (!val || !/^\\d+$/.test(val.textContent.trim()))
      bad.push("gauge " + i + " value not rendered");
    const vb = svg.viewBox.baseVal, needle = svg.querySelector(".needle");
    if (!needle) { bad.push("gauge " + i + " has no needle"); return; }
    const x = +needle.getAttribute("x2"), y = +needle.getAttribute("y2");
    if (x < 0 || x > vb.width || y < 0 || y > vb.height)
      bad.push("gauge " + i + " needle outside viewBox: " + x + "," + y);
    if (svg.getBoundingClientRect().width < 60) bad.push("gauge " + i + " svg collapsed");
  });

  // the quote grid must tile exactly: no dead slots on the final row
  (() => {
    const cells = [...document.querySelectorAll(".q:not(.derived)")];
    if (!cells.length) return;
    const grid = cells[0].parentElement.getBoundingClientRect();
    const last = cells[cells.length - 1].getBoundingClientRect();
    if (last.right < grid.right - 2)
      bad.push("quote grid leaves a gap on its last row (" +
               Math.round(grid.right - last.right) + "px)");
    const cols = new Set(cells.map(c => Math.round(c.getBoundingClientRect().left))).size;
    if (cells.length % cols !== 0)
      bad.push(cells.length + " quote cells do not tile " + cols + " columns");
  })();

  // liquidation split bar must total the full width
  const segs = [...document.querySelectorAll(".liqbar span")];
  if (segs.length !== 2) bad.push("liquidation split bar malformed");
  else {
    const w = segs[0].parentElement.clientWidth;
    const sum = segs[0].getBoundingClientRect().width + segs[1].getBoundingClientRect().width;
    if (Math.abs(sum - w) > 6) bad.push("liquidation bar does not fill: " + sum + " vs " + w);
  }

  // ladder segments must stay inside their track
  document.querySelectorAll(".lr .rng").forEach((rng, i) => {
    const rb = rng.getBoundingClientRect();
    rng.querySelectorAll(".seg").forEach(sg => {
      const sb = sg.getBoundingClientRect();
      if (sb.left < rb.left - 1 || sb.right > rb.right + 1)
        bad.push("ladder segment " + i + " escapes its track");
    });
  });

  // geopolitical rows must state a channel
  document.querySelectorAll(".ge").forEach((g, i) => {
    if (!g.querySelector(".ch") || g.querySelector(".ch").textContent.trim().length < 20)
      bad.push("geo " + i + " lacks a transmission channel");
  });

  // panels must rest visible
  document.querySelectorAll("main .card").forEach(c => {
    if (parseFloat(getComputedStyle(c).opacity) < 0.99) bad.push("card resting transparent");
    if (c.getBoundingClientRect().height < 40) bad.push("card collapsed");
  });

  // canvas painted
  const cv = document.getElementById("fx");
  if (!cv || cv.width < 1) bad.push("canvas not sized");
  else {
    const d = cv.getContext("2d").getImageData(0, 0,
      Math.min(cv.width, 360), Math.min(cv.height, 360)).data;
    let painted = 0;
    for (let i = 0; i < d.length; i += 4)
      if (d[i] !== 6 || d[i+1] !== 7 || d[i+2] !== 11) painted++;
    if (painted < 100) bad.push("canvas unpainted (" + painted + ")");
  }

  // scrollable containers must actually scroll, never clip
  document.querySelectorAll(".scroll, .news, .tape").forEach(el => {
    if (el.scrollWidth > el.clientWidth + 1) {
      const ov = getComputedStyle(el).overflowX;
      if (ov !== "auto" && ov !== "scroll" && ov !== "hidden")
        bad.push("overflowing container not scrollable: " + el.className);
    }
  });

  if (document.documentElement.scrollWidth > window.innerWidth + 1)
    bad.push("h-overflow " + document.documentElement.scrollWidth + " > " + window.innerWidth);

  return {bad, quotes: n(".q"), news: n(".sqr"), gauges: n(".gg"), geo: n(".ge"),
          cds: n("[data-when]"),
          state: txt("state"), age: txt("age"), sess: txt("sess"), clk: txt("clk")};
}"""

SAMPLE = """() => {
  const txt = id => (document.getElementById(id) || {}).textContent || "";
  const cds = [...document.querySelectorAll("[data-when]")].map(e => e.textContent);
  const run = document.querySelector(".tape-run");
  return {clk: txt("clk"), age: txt("age"), sess: txt("sess"), state: txt("state"),
          cds, tx: run ? getComputedStyle(run).transform : "none"};
}"""


async def run(path: str) -> int:
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        print("SKIP: playwright not installed")
        return 3
    binary = find_chromium()
    if not binary:
        print("SKIP: no chromium binary")
        return 3

    url = "file://" + os.path.abspath(path)
    failures = 0
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(executable_path=binary, args=["--no-sandbox"])

        for reduced in (False, True):
            ctx = await browser.new_context(
                reduced_motion="reduce" if reduced else "no-preference")
            for label, w, h in VIEWPORTS:
                page = await ctx.new_page()
                await page.set_viewport_size({"width": w, "height": h})
                errs: list[str] = []
                page.on("pageerror", lambda ex: errs.append(f"pageerror: {ex}"))
                page.on("console", lambda m: errs.append(f"console.{m.type}: {m.text}")
                        if m.type in ("error", "warning") else None)
                await page.goto(url, wait_until="load")
                await page.wait_for_timeout(1600)
                res = await page.evaluate(STATIC)
                real = [x for x in errs if "fonts.g" not in x and "ERR_" not in x]
                tag = f"{label:<8} {w}x{h} {'reduced' if reduced else 'motion':>7}"
                if res["bad"] or real:
                    failures += 1
                    print(f"FAIL {tag}")
                    for b in res["bad"] + real:
                        print(f"       - {b}")
                else:
                    print(f"PASS {tag}  quotes={res['quotes']} squawk={res['news']} "
                          f"gauges={res['gauges']} geo={res['geo']} cds={res['cds']} "
                          f"state={res['state']}")
                await page.close()
            await ctx.close()

        # ---- live behaviour: the parts that only exist at runtime ----------
        page = await browser.new_page()
        await page.set_viewport_size({"width": 1600, "height": 1000})
        await page.goto(url, wait_until="load")
        await page.wait_for_timeout(1200)
        a = await page.evaluate(SAMPLE)
        await page.wait_for_timeout(2600)
        b = await page.evaluate(SAMPLE)

        live_bad = []
        if not a["clk"] or a["clk"] == b["clk"]:
            live_bad.append(f"clock not advancing: {a['clk']!r} -> {b['clk']!r}")
        if not __import__("re").match(r"^\d{2}:\d{2}:\d{2} UTC$", b["clk"] or ""):
            live_bad.append(f"clock format wrong: {b['clk']!r}")
        if not a["age"] or "h" not in a["age"]:
            live_bad.append(f"age counter not rendered: {a['age']!r}")
        if a["state"] not in ("LIVE", "SNAPSHOT", "STALE SNAPSHOT"):
            live_bad.append(f"feed state unexpected: {a['state']!r}")
        if not a["sess"]:
            live_bad.append("session state blank")

        future = [(x, y) for x, y in zip(a["cds"], b["cds"])
                  if x not in ("RELEASED", "—", "\u2014")]
        if not future:
            live_bad.append("no future countdowns to verify")
        for x, y in future:
            if x == y:
                live_bad.append(f"countdown frozen: {x}")
            if not __import__("re").search(r"\d{2}:\d{2}:\d{2}$", y):
                live_bad.append(f"countdown format wrong: {y!r}")
        if a["tx"] == b["tx"] and a["tx"] not in ("none", ""):
            live_bad.append("ticker not animating")

        if live_bad:
            failures += 1
            print("FAIL live behaviour")
            for x in live_bad:
                print(f"       - {x}")
        else:
            print(f"PASS live behaviour  clock {a['clk']} -> {b['clk']} | "
                  f"state {a['state']} age {a['age']} | session {a['sess']} | "
                  f"{len(future)} countdowns ticking")
        await browser.close()

    print("\nALL CHECKS PASSED" if not failures else f"\n{failures} CHECK GROUP(S) FAILED")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "board/macro-desk-live.html"
    raise SystemExit(asyncio.run(run(target)))
