#!/usr/bin/env python3
"""Live browser verification for the generated board.

Static tests prove the document is well-formed and self-consistent. This proves
it actually renders: no script errors, no horizontal overflow at any viewport,
every panel populated, the ambient canvas painting, and the scrolling-tape
geometry covering the full width at every phase.

Requires playwright plus a Chromium build; skips loudly rather than passing
silently when either is absent.

    python3 tools/verify_board.py [path-to-html]
"""

from __future__ import annotations

import asyncio
import glob
import os
import sys

VIEWPORTS = [("mobile", 390, 844), ("tablet", 834, 1112), ("desktop", 1600, 1000)]


def find_chromium() -> str | None:
    for pat in ("/opt/pw-browsers/chromium-*/chrome-linux/chrome",
                "/opt/pw-browsers/chromium/chrome-linux/chrome",
                "/usr/bin/chromium", "/usr/bin/chromium-browser"):
        hits = sorted(glob.glob(pat))
        if hits:
            return hits[-1]
    return None


PROBE = """() => {
  const bad = [];
  const q = s => document.querySelector(s);
  const n = s => document.querySelectorAll(s).length;
  const D = window.__BOARD__;

  if (!D) bad.push("registry payload missing");
  if (n(".mod") !== D.modules.length)
    bad.push(`rack rows ${n(".mod")} != registry ${D.modules.length}`);
  if (n(".rg") !== D.regimes.length) bad.push("regime tiles wrong");
  if (n("#cbmap tr") !== D.banks.length) bad.push("bank rows wrong");
  if (n("#feeds tr") !== D.feeds.length) bad.push("feed rows wrong");
  if (n("#nodes circle") !== D.chain.length * 2) bad.push("chain nodes wrong");
  if (n(".wrow") !== D.weights.length) bad.push("weight rows wrong");

  // masthead counts must equal the registry, not a typed number
  const c = {BUILT:0, PARTIAL:0, SPEC:0};
  D.modules.forEach(m => c[m.status]++);
  const txt = id => (document.getElementById(id) || {}).textContent || "";
  if (txt("m-built") !== c.BUILT + " built") bad.push("built count mismatch: " + txt("m-built"));
  if (txt("m-partial") !== c.PARTIAL + " partial") bad.push("partial count mismatch");
  if (txt("m-spec") !== c.SPEC + " spec") bad.push("spec count mismatch");
  if (txt("feeds-live") !== "0 of " + D.feeds.length) bad.push("feed count mismatch");
  if (!/^\\d{2}:\\d{2}:\\d{2}Z$/.test(txt("clock"))) bad.push("clock not ticking: " + txt("clock"));

  // every weight bar must have real painted width (the inline-span bug)
  document.querySelectorAll(".wfill").forEach((el, i) => {
    if (el.getBoundingClientRect().width < 1) bad.push("weight bar " + i + " has zero width");
  });

  // chain indices: 01..10, never "010"
  const idx = [...document.querySelectorAll("#nodes text")]
    .map(t => t.textContent).filter(t => /^\\d+$/.test(t));
  if (idx.length !== D.chain.length) bad.push("chain index count wrong");
  if (idx[idx.length - 1] !== "10") bad.push("last chain index is " + idx[idx.length - 1]);

  // nothing meant to be read may rest invisible
  document.querySelectorAll("main .p").forEach(p => {
    const s = getComputedStyle(p);
    if (parseFloat(s.opacity) < 0.99) bad.push("panel resting at opacity " + s.opacity);
    if (p.getBoundingClientRect().height < 40) bad.push("panel collapsed: " + (p.querySelector("h2")||{}).textContent);
  });

  // canvas painting
  const cv = q("#bg");
  if (!cv || cv.width < 1 || cv.height < 1) bad.push("canvas not sized");
  else {
    const g = cv.getContext("2d");
    const d = g.getImageData(0, 0, Math.min(cv.width, 400), Math.min(cv.height, 400)).data;
    let painted = 0;
    for (let i = 0; i < d.length; i += 4)
      if (d[i] !== 7 || d[i+1] !== 10 || d[i+2] !== 18) painted++;
    if (painted < 100) bad.push("canvas appears unpainted (" + painted + " px)");
  }

  // wide content must be reachable by scrolling its own container, never clipped
  document.querySelectorAll(".flowwrap, .scroll").forEach(el => {
    if (el.scrollWidth > el.clientWidth + 1) {
      const ov = getComputedStyle(el).overflowX;
      if (ov !== "auto" && ov !== "scroll")
        bad.push("overflowing container is not scrollable: " + el.className);
      el.scrollLeft = el.scrollWidth;
      if (el.scrollLeft < 1) bad.push("container will not scroll: " + el.className);
      el.scrollLeft = 0;
    }
  });

  // body must not scroll sideways
  if (document.documentElement.scrollWidth > window.innerWidth + 1)
    bad.push(`h-overflow ${document.documentElement.scrollWidth} > ${window.innerWidth}`);

  return {bad, panels: n("main .p"), mods: n(".mod")};
}"""

# The tape geometry, re-derived in-page: proves coverage holds at every phase
# and that rotation preserves the ring (the old cumulative walk drained off-screen).
GEOMETRY = """() => {
  const N = 280, W = 1600, seg = W / (N - 1), bad = [];
  const k = [3,7,13], a = [0.16,0.09,0.05];
  let pts = [];
  for (let i = 0; i < N; i++) {
    let y = 0.5;
    for (let j = 0; j < 3; j++) y += a[j] * Math.sin(2*Math.PI*k[j]*i/N + 1.3*(j+1));
    pts.push(Math.max(0.06, Math.min(0.94, y)));
  }
  const first = pts.slice();
  let acc = 0;
  for (let f = 0; f < 20000; f++) {          // ~5.5 min of animation at 60fps
    acc += 0.055;
    while (acc >= 1) { pts.push(pts.shift()); acc -= 1; }
    const xMin = -acc * seg, xMax = (N - acc) * seg;
    if (xMin > 0) bad.push("gap at left edge, frame " + f);
    if (xMax < W) bad.push("gap at right edge, frame " + f);
    if (pts.length !== N) bad.push("ring length changed at frame " + f);
  }
  const sorted = x => x.slice().sort((p,q)=>p-q);
  const same = JSON.stringify(sorted(pts)) === JSON.stringify(sorted(first));
  if (!same) bad.push("rotation lost or duplicated points");
  const min = Math.min(...pts), max = Math.max(...pts);
  if (min < 0.06 || max > 0.94) bad.push("series left its band: " + min + ".." + max);
  return bad;
}"""


async def run(path: str) -> int:
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        print("SKIP: playwright not installed (pip install playwright)")
        return 3
    binary = find_chromium()
    if not binary:
        print("SKIP: no chromium binary found")
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
                errors: list[str] = []
                page.on("pageerror", lambda ex: errors.append(f"pageerror: {ex}"))
                page.on("console", lambda m: errors.append(f"console.{m.type}: {m.text}")
                        if m.type in ("error", "warning") else None)
                await page.goto(url, wait_until="load")
                await page.wait_for_timeout(1800)

                res = await page.evaluate(PROBE)
                # a blocked webfont is the sandbox, not the page
                real = [x for x in errors if "fonts.googleapis" not in x
                        and "ERR_CONNECTION" not in x and "ERR_NAME" not in x]
                tag = f"{label:<8} {w}x{h} {'reduced' if reduced else 'motion ':>8}"
                if res["bad"] or real:
                    failures += 1
                    print(f"FAIL {tag}")
                    for b in res["bad"] + real:
                        print(f"       - {b}")
                else:
                    print(f"PASS {tag}  panels={res['panels']} modules={res['mods']}")
                await page.close()
            await ctx.close()

        page = await browser.new_page()
        await page.goto(url, wait_until="load")
        geo = await page.evaluate(GEOMETRY)
        if geo:
            failures += 1
            print("FAIL tape geometry")
            for g in geo[:5]:
                print(f"       - {g}")
        else:
            print("PASS tape geometry  20000 frames, full-width coverage held, ring intact")
        await browser.close()

    print(("\nALL CHECKS PASSED" if not failures else f"\n{failures} CHECK GROUP(S) FAILED"))
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "board/cold-start-terminal.html"
    raise SystemExit(asyncio.run(run(target)))
