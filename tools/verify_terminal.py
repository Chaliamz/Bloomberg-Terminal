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

  // heatmap must actually paint, and its price line must sit inside the canvas
  (() => {
    const cv = document.getElementById("hm-canvas");
    if (!cv) { bad.push("heatmap canvas missing"); return; }
    if (cv.getBoundingClientRect().width < 80) bad.push("heatmap canvas collapsed");
    const g = cv.getContext("2d");
    if (!g) { bad.push("heatmap 2d context unavailable"); return; }
    const d = g.getImageData(0, 0, cv.width, cv.height).data;
    let lit = 0, distinct = new Set();
    for (let i = 0; i < d.length; i += 4) {
      const key = d[i] + "," + d[i+1] + "," + d[i+2];
      distinct.add(key);
      if (d[i] + d[i+1] + d[i+2] > 40) lit++;
    }
    if (lit < 20) bad.push("heatmap appears unpainted (" + lit + " lit px)");
    if (distinct.size < 6)
      bad.push("heatmap uses only " + distinct.size + " colours - ramp not applied");
    if (d[3] !== 255) bad.push("heatmap pixels not opaque");
  })();

  // stocks + earnings
  if (n(".eqc") < 4) bad.push("mega-cap board thin: " + n(".eqc"));
  if (n(".er") < 3) bad.push("earnings board thin: " + n(".er"));
  document.querySelectorAll(".er .ecd").forEach((el, i) => {
    const t = el.textContent.trim();
    if (!t || t === "\u2014") bad.push("earnings countdown " + i + " unresolved");
    if (/^\d+d \d{2}:/.test(t))
      bad.push("earnings " + i + " shows a clock for a date-only source: " + t);
  });

  // heatmap controls must exist
  ["hm-thr","hm-zin","hm-zout","hm-reset","hm-fit","hm-zv","hm-lmin","hm-lmax","hm-peak","hm-price","hm-time","hm-meta"]
    .forEach(id => { if (!document.getElementById(id)) bad.push("control " + id + " missing"); });
  if (n("[data-tf]") < 6) bad.push("too few timeframes");
  if (n("[data-lrange]") < 5) bad.push("leverage range presets missing");
  if (n("[data-res]") < 4) bad.push("too few grid resolutions");
  if (!document.getElementById("hm-lmin") || !document.getElementById("hm-lmax"))
    bad.push("leverage min/max inputs missing");
  if (n("[data-scheme]") < 3) bad.push("scheme controls missing");
  if (!document.getElementById("hm-meta").textContent.trim() ||
      document.getElementById("hm-meta").textContent.indexOf("\u2014") === 0)
    bad.push("heatmap meta line never resolved");
  if (document.querySelectorAll("#hm-price span").length < 3)
    bad.push("price axis not drawn");
  if (document.querySelectorAll("#hm-time span").length < 3)
    bad.push("time axis not drawn");

  // geo events must each show a resolved relative time
  document.querySelectorAll("[data-ago]").forEach((el, i) => {
    const t = el.textContent.trim();
    if (!/^(\\d+m|\\d+h|\\d+d \\d+h) ago$/.test(t))
      bad.push("geo time " + i + " unresolved: " + JSON.stringify(t));
  });

  // terminal chrome
  if (!document.querySelector(".cmdbar")) bad.push("command bar missing");
  if (!document.querySelector(".statusbar")) bad.push("status bar missing");

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
          heat: !!document.getElementById("hm-canvas"), cds: n("[data-when]"),
          state: txt("state"), age: txt("age"), sess: txt("sess"), clk: txt("clk")};
}"""

FXSAMPLE = """() => {
  const cv = document.getElementById("fx");
  if (!cv) return null;
  const g = cv.getContext("2d");
  if (!g) return null;
  const w = Math.min(cv.width, 300), h = Math.min(cv.height, 300);
  const d = g.getImageData(0, 0, w, h).data;
  let sum = 0;
  for (let i = 0; i < d.length; i += 4) sum += d[i] + d[i+1] * 3 + d[i+2] * 7;
  return sum;
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
                          f"gauges={res['gauges']} geo={res['geo']} "
                          f"heat={'y' if res['heat'] else 'n'} cds={res['cds']} "
                          f"state={res['state']}")
                await page.close()
            await ctx.close()

        # ---- controls: clicking must recompute, not restyle -----------------
        page = await browser.new_page()
        await page.set_viewport_size({"width": 1720, "height": 1050})
        cerr: list[str] = []
        page.on("pageerror", lambda ex: cerr.append(f"pageerror: {ex}"))
        await page.goto(url, wait_until="load")
        await page.wait_for_timeout(1500)

        async def canvas_sig() -> int:
            # Sample the WHOLE canvas with a stride. A corner crop lands in the
            # region before the first anchor, which is uniform base colour and
            # therefore identical across configurations - it would hide real
            # changes and report false failures.
            return await page.evaluate("""() => {
              const c = document.getElementById("hm-canvas");
              const d = c.getContext("2d").getImageData(0, 0, c.width, c.height).data;
              let s = 0;
              for (let i = 0; i < d.length; i += 16)
                s = (s + d[i] + d[i+1]*3 + d[i+2]*7) % 2147483647;
              return s;
            }""")

        async def meta() -> str:
            return await page.evaluate(
                "() => document.getElementById('hm-meta').textContent")

        ctl_bad = []
        base_sig, base_meta = await canvas_sig(), await meta()
        async def band() -> tuple[float, float]:
            """The price band the field currently spans, read off the axis."""
            v = await page.evaluate("""() => {
              const s = document.querySelectorAll("#hm-price span");
              const num = t => parseFloat(t.replace(/[^0-9.]/g, ""));
              return [num(s[s.length-1].textContent), num(s[0].textContent)];
            }""")
            return float(v[0]), float(v[1])

        checks = [
            ("scheme magma", '[data-scheme="magma"]'),
            ("scheme ember", '[data-scheme="ember"]'),
            ("grid COARSE", '[data-res="60x40"]'),
            ("grid ULTRA", '[data-res="240x130"]'),
            ("grid FINE", '[data-res="160x90"]'),
            ("leverage LOW", '[data-lrange="2-10"]'),
            ("leverage HIGH", '[data-lrange="50-125"]'),
            ("leverage EXTREME", '[data-lrange="100-125"]'),
            ("leverage ALL", '[data-lrange="2-125"]'),
            ("zoom in", "#hm-zin"),
            ("pan up", "#hm-pan-up"),
            ("reset", "#hm-reset"),
        ]
        # A window holding <2 anchors, or the same anchors as a narrower one,
        # renders identically - it must be gated off with a stated reason rather
        # than shipped as a button that does nothing.
        tfs = await page.evaluate("""() => [...document.querySelectorAll("[data-tf]")]
          .map(b => ({d: b.getAttribute("data-tf"),
                      off: b.hasAttribute("data-off"),
                      why: b.title || ""}))""")
        live = [t for t in tfs if not t["off"]]
        if len(live) < 2:
            ctl_bad.append(f"only {len(live)} usable timeframe(s)")
        for t in tfs:
            if t["off"] and len(t["why"]) < 10:
                ctl_bad.append(f'timeframe {t["d"]} disabled without a reason')
            if not t["off"] and not t["why"]:
                ctl_bad.append(f'timeframe {t["d"]} has no anchor count')
        checks += [(f'window {t["d"] or "ALL"}', f'[data-tf="{t["d"]}"]') for t in live]

        prev = base_sig
        for label, sel in checks:
            await page.click(sel)
            await page.wait_for_timeout(220)
            sig = await canvas_sig()
            if sig == prev:
                ctl_bad.append(f"{label}: canvas unchanged after click")
            prev = sig
        # a window control must change the reported model, not just pixels
        narrow = [t for t in live if t["d"] != "0"]
        if narrow:
            await page.click(f'[data-tf="{narrow[0]["d"]}"]')
            await page.wait_for_timeout(220)
            if await meta() == base_meta:
                ctl_bad.append(
                    f'{narrow[0]["d"]}D window did not change the model description')
        await page.click("#hm-reset")
        await page.wait_for_timeout(220)

        # ---- the two defects the user reported, probed directly ------------
        # 1. zoom OUT must widen the visible band. The old clamp was max(1,..),
        #    which made every zoom-out click a silent no-op.
        lo0, hi0 = await band()
        for _ in range(3):
            await page.click("#hm-zout")
            await page.wait_for_timeout(130)
        lo1, hi1 = await band()
        if not (hi1 - lo1) > (hi0 - lo0) * 1.05:
            ctl_bad.append(
                f"zoom out did not widen the band: {hi0-lo0:.0f} -> {hi1-lo1:.0f}")
        if (await page.inner_text("#hm-zv")).startswith("1.00"):
            ctl_bad.append("zoom readout stuck at 1.00x after zooming out")
        # zoom in must narrow it again
        for _ in range(5):
            await page.click("#hm-zin")
            await page.wait_for_timeout(110)
        lo2, hi2 = await band()
        if not (hi2 - lo2) < (hi1 - lo1):
            ctl_bad.append("zoom in did not narrow the band")
        # 2. FIT must restore the sourced window
        await page.click("#hm-fit")
        await page.wait_for_timeout(250)
        lo3, hi3 = await band()
        if abs((hi3 - lo3) - (hi0 - lo0)) > max(1.0, (hi0 - lo0) * 0.02):
            ctl_bad.append(f"FIT did not restore the sourced band "
                           f"({hi3-lo3:.0f} vs {hi0-lo0:.0f})")
        # 3. the chart must be draggable
        # The field is taller than the viewport, so its geometric centre sits
        # below the fold and mouse.move() there never lands on it. Grab the
        # middle of the part that is actually visible.
        box = await page.eval_on_selector("#hm-canvas", """c => {
            const r = c.getBoundingClientRect();
            const top = Math.max(r.y + 8, 8);
            const bot = Math.min(r.y + r.height - 8, window.innerHeight - 8);
            return [r.x + r.width / 2, (top + bot) / 2, bot - top];
        }""")
        if box[2] < 80:
            ctl_bad.append("heatmap not visible enough in the viewport to drag")
        await page.click("#hm-zin")          # zoomed in, so panning has headroom
        await page.wait_for_timeout(200)
        before = await canvas_sig()
        await page.mouse.move(box[0], box[1])
        await page.mouse.down()
        for dy in (14, 28, 46, 70):
            await page.mouse.move(box[0], box[1] + dy)
            await page.wait_for_timeout(45)
        await page.mouse.up()
        await page.wait_for_timeout(260)
        if await canvas_sig() == before:
            ctl_bad.append("dragging the field did not pan the chart")
        await page.click("#hm-reset")
        await page.wait_for_timeout(200)
        # threshold slider - baseline taken immediately before the change, or
        # the comparison is against unrelated state and passes vacuously
        pre_thr = await canvas_sig()
        await page.evaluate("""() => {
          const r = document.getElementById("hm-thr");
          r.value = 60; r.dispatchEvent(new Event("input", {bubbles:true}));
        }""")
        await page.wait_for_timeout(250)
        if await canvas_sig() == pre_thr:
            ctl_bad.append("threshold slider had no effect")
        await page.evaluate("""() => {
          const r = document.getElementById("hm-thr");
          r.value = 0; r.dispatchEvent(new Event("input", {bubbles:true}));
        }""")
        await page.wait_for_timeout(200)

        # 4. an inverted leverage range would empty the model and blank the
        #    field; it must collapse to at least one tier instead.
        async def set_lev(which: str, val: int) -> None:
            await page.fill(f"#hm-{which}", str(val))
            await page.dispatch_event(f"#hm-{which}", "change")
            await page.wait_for_timeout(200)

        await set_lev("lmin", 90)
        await set_lev("lmax", 10)          # inverted on purpose
        lmin = int(await page.input_value("#hm-lmin"))
        lmax = int(await page.input_value("#hm-lmax"))
        if lmin > lmax:
            ctl_bad.append(f"inverted leverage range survived ({lmin}-{lmax})")
        if "0 leverage tiers" in await meta():
            ctl_bad.append("leverage range emptied the model")
        # out-of-range input must clamp, not propagate
        await set_lev("lmin", -40)
        await set_lev("lmax", 9999)
        lmin = int(await page.input_value("#hm-lmin"))
        lmax = int(await page.input_value("#hm-lmax"))
        if not (2 <= lmin <= 125 and 2 <= lmax <= 125):
            ctl_bad.append(f"leverage inputs did not clamp ({lmin}-{lmax})")
        await page.click('[data-lrange="2-125"]')
        await page.wait_for_timeout(200)
        left = int(await page.input_value("#hm-lmax")) - \
            int(await page.input_value("#hm-lmin")) + 1

        real_cerr = [x for x in cerr if "fonts.g" not in x and "ERR_" not in x]
        if ctl_bad or real_cerr:
            failures += 1
            print("FAIL heatmap controls")
            for x in ctl_bad + real_cerr:
                print(f"       - {x}")
        else:
            print(f"PASS heatmap controls  {len(checks)} controls recompute, "
                  f"zoom/pan/fit live, {left} leverage tiers modelled")
        await page.close()

        # ---- live behaviour: the parts that only exist at runtime ----------
        page = await browser.new_page()
        await page.set_viewport_size({"width": 1600, "height": 1000})
        await page.goto(url, wait_until="load")
        await page.wait_for_timeout(1200)
        a = await page.evaluate(SAMPLE)
        fx_a = await page.evaluate(FXSAMPLE)
        await page.wait_for_timeout(2600)
        b = await page.evaluate(SAMPLE)
        fx_b = await page.evaluate(FXSAMPLE)
        # the ambient loop must still be running seconds in: a thrown frame that
        # fails to re-arm requestAnimationFrame leaves a frozen, painted canvas
        await page.wait_for_timeout(1800)
        fx_c = await page.evaluate(FXSAMPLE)

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
        if fx_a is None:
            live_bad.append("ambient canvas unreadable")
        elif fx_a == fx_b or fx_b == fx_c:
            live_bad.append(
                f"ambient animation frozen (frame signatures {fx_a}, {fx_b}, {fx_c}) "
                "- the rAF loop most likely threw and failed to re-arm")

        if live_bad:
            failures += 1
            print("FAIL live behaviour")
            for x in live_bad:
                print(f"       - {x}")
        else:
            print(f"PASS live behaviour  clock {a['clk']} -> {b['clk']} | "
                  f"state {a['state']} age {a['age']} | session {a['sess']} | "
                  f"{len(future)} countdowns ticking | ambient loop alive")
        await browser.close()

    print("\nALL CHECKS PASSED" if not failures else f"\n{failures} CHECK GROUP(S) FAILED")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "board/macro-desk-live.html"
    raise SystemExit(asyncio.run(run(target)))
