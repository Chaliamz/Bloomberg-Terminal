# Bloomberg-Terminal — operating rules

## Delivery gate (standing instruction, set by the user)

**Never send output until it has been tested.** Before any deliverable reaches the
user, in this order:

1. **Test** — run the full unit suite (`python3 -m unittest discover -s tests -t .`)
   AND all three browser harnesses (`tools/verify_terminal.py`,
   `tools/verify_board.py`, `tools/verify_live.py`).
2. **Sample** — actually look at the rendered result. Screenshot the panel that
   changed and inspect it. A passing assertion is not a substitute for seeing it.
3. **Scan** — re-read the diff adversarially and hunt for bugs that no test covers:
   null writes, unbounded growth, negative radii, off-by-one, stale state,
   cross-language rounding, ordering assumptions, clamps that silently no-op.
4. **Eliminate** — fix everything found. Do not flag-and-ship. If a fix opens a
   new problem, fix and retest until stable.
5. **Only then send.** If something genuinely cannot be verified, say exactly what
   and why — never let an unverified thing pass as verified.

Mutation-test the probes that guard user-reported bugs: reintroduce the bug and
confirm the check fails. A probe that cannot fail is decoration.

## No-fabrication contract

This is the core invariant of the codebase and it is enforced in code, not by
convention:

- Every number carries **source, tier, unit and timestamp**. `Quote` and
  `Observation` reject construction without them.
- Engines return `Insufficient(reason, missing)` rather than a plausible number.
- Adapters return `Unavailable` rather than substituting a cached value. An
  unreachable source **never** restamps stale data.
- Never interpolate price between observations. Gaps are shown, not filled.
- Never offer a control whose view the data cannot support — gate it and state why.
- Label claims **Confirmed / Inferred / Unknown**. Never blur them.

## Environment constraints (verified, not assumed)

- **No outbound egress** to any market-data or news host: the proxy gateway answers
  403 to CONNECT. `curl`, and `WebFetch` both fail. **WebSearch is the only
  channel**, and it returns model-synthesised summaries, so attribute every number
  to a named carrier and record conflicts rather than silently picking one.
- A **published artifact cannot fetch** — CSP blocks fetch/XHR/WebSocket. The page
  therefore ships an honestly-stamped snapshot whose age counter climbs, and the
  real 24/7 scanner (`python -m macro live 60`) lives in the repo.
- Chromium for the harnesses: `tools/verify_terminal.py:find_chromium()`.
  Do not run `playwright install`.

## House conventions

- Accent is teal `#2EC5CF`. **Not** amber-on-black — that is Bloomberg's protected
  brand identity. Borrow the functional conventions (density, monospace grids,
  hard panels, F-key command bar, status line), never the trade dress.
- Cross-language numerics use `floor(x + 0.5)` on **both** sides. Python `round()`
  is banker's rounding and JS `Math.round` mishandles `0.49999999999999994`.
- The shipped JS heatmap engine is a port of `macro.live.liquidation_heatmap` and a
  cross-implementation test runs them against each other in `node`. Any change to
  one is a change to both.
- Regenerate with `python3 -m macro terminal` after touching `macro/`; a test
  asserts the committed HTML matches the render.

## Live data: what is and is not possible (verified)

- **Which assets can be live at all, and why the rest cannot.** The registry is
  `macro.live.BROWSER_FEEDS`; the JS feed table and the status table on the page
  are both rendered from it, so the page's claims and the sockets it opens cannot
  drift apart. Real time: **BTC, ETH** (Binance combined stream, T1) and **GOLD**
  via **PAXGUSDT** — a 1:1 LBMA-backed token that holds ~±0.3% to spot, so it is
  a **proxy at T2**, marked `data-proxy` in amber, never dressed as spot XAU.
  Daily: **DXY**, derived from the ECB's published reference rates via the ICE
  weights (`dxy_from_usd_rates`), marked `data-fix` in violet, Tier 3, and it
  **never advances `D.newest`** — a daily fixing is real but is not evidence the
  board is current. Unreachable, and the page says so with the reason: SPX,
  DJIA, NDX, VIX, 2Y, 10Y, Brent, WTI. Yahoo sends no ACAO header, stooq the
  same, and every other vendor needs an API key — which shipped inside this page
  would be a leaked credential.
- **The formatters are a cross-language pair.** `fmt()` in the page mirrors
  `macro.terminal._fmt` unit for unit, both rounding `floor(x+0.5)` via
  `_half_up` — Python's format spec alone rounds half to even. A node test runs
  80 value/unit combinations through both and requires exact agreement, because
  a live tick replaces a rendered snapshot value in the same cell.
- **The page carries a live client and it works from `file://`.** Confirmed in
  Chromium by `tools/verify_live.py`, which stands up venue-shaped local servers
  and drives the real page against them. Two transports, each blocked in a
  different place:
  - **Binance combined stream `wss://stream.binance.com:9443/stream?streams=…`.**
    One socket carries every subscribed symbol; each event arrives wrapped as
    `{stream, data}` and is routed by `data.s` through the symbol map, so an
    event for a symbol nobody subscribed to lands nowhere. WebSockets are
    exempt from CORS, so a browser may open one to any host. Binance's REST API
    sends **no** `Access-Control-Allow-Origin` at all — that is why the stream is
    used and `/api/v3` is not.
  - **`https://api.coinbase.com/v2/prices/BTC-USD/spot`, polled**, as the fallback
    where websockets are blocked. Coinbase supports CORS on unauthenticated price
    endpoints; Kraken does not.
  The stream **outranks** the poll for 30s after any tick (`STREAM_OWNS`), checked
  both before the fetch and after it — otherwise a request in flight when a tick
  lands still wins and the venue label flickers every 20s.
- The JS gate `ok()` **mirrors `parse_binance_ticker` field for field**. A tick
  that fails it changes *nothing*: no price, no timestamp, no LIVE. Ten bad
  payloads are driven through a real browser every gate run and the page must be
  unchanged after each — mutation-tested, because a probe that passes for the
  wrong reason is worse than no probe. One of them did: the negative-price case
  was being caught by the `hi<lo` range check rather than by the gate it guarded.
- A silent half-open socket never fires `close`. A 60s watchdog re-renders the
  badge every 5s so it cannot keep claiming LIVE off an hour-old tick.
- `D.newest` **only ever advances** — it drives the age counter and a transport
  reporting an older event time must not wind it back. `LIVE.at` is a different
  quantity, the last tick's own stamp, and is written unconditionally so the
  badge's clock always belongs to the price beside it. A shared monotonic guard
  desynchronised the two; a per-source guard is worse, because the transports
  read different clocks (Binance server time vs the local one) and one local read
  running ahead would silently reject every later stream tick.
- `ok()` parses its own copy of the stamp, so `apply()` re-parses before
  `new Date()`. A venue that JSON-encodes the event time as a **string** would
  otherwise produce an Invalid Date that throws *after* the price is written.

- **A published artifact can never be live** — but the file can. The viewer sandbox blocks fetch,
  XHR and WebSocket — this is in the Artifact tool contract, not a guess. The
  page is a snapshot with an age counter measured from the newest observation.
- **WebSearch is not a live feed either.** One query for the BTC price returned
  79,824.65 / 79,571.82 / 79,735.00 / 79,917.67 from four carriers, all cached
  page summaries, none matching the operator's live ticker at 79,170. Any loop
  built on WebSearch inherits that lag. That is why the hourly Routine was
  deleted rather than tuned: no schedule fixes a stale input.
- **`python -m macro live 30` IS live**, run anywhere with egress. Binance
  `/api/v3/ticker/24hr` is Tier 1 for its own last trade. The adapter is
  `parse_binance_ticker`; it returns None rather than guess on a malformed body,
  missing or non-numeric field, wrong symbol, non-positive price, future stamp,
  high-below-low, or a seconds-epoch sent where milliseconds belong.
- Price anchors from a live poll are throttled by `ANCHOR_MIN_GAP` (900s). A 30s
  poll would otherwise append 2,880 anchors a day and the liquidity map
  recomputes over all of them; a test polls 40 times and asserts the series does
  not grow.

## Refresh policy (standing, set by the user — revised 13 September)

The user asked for continuous refresh: "Data should refresh 24/7. Anything new
happens, you update them immediately." The first implementation of that was an
hourly Routine. **It has been deleted at the user's instruction** — it burned a
full model context every hour and left the session unable to do other work.

What replaced it, and why this is not a downgrade:

- **The live client IS the 24/7 refresh, and it always was the only real one.**
  BTC, ETH and the PAXG gold proxy stream from Binance in the viewer's own
  browser; DXY recomputes from the ECB fixing. That path costs nothing, needs no
  schedule, and is real time to the second. An hourly WebSearch loop could never
  beat it — WebSearch returns cached page summaries and inherits their lag.
- **Everything WebSearch is actually good for changes slowly**: a CPI print, a
  central-bank decision, a geopolitical development, a sentiment gauge. Those
  move on a daily cadence at most, so they are refreshed **on demand, in a
  session with a checkout**, which is the only kind of run that can push.
- **Scan on demand like this**, and do it in one pass:
  `python3 -m macro observe --date … --price … --source … --tier …` for each
  new price observation, edit `macro/seed.py` for everything else, then
  `python3 -m macro terminal`, run the gate, commit, push, republish.
- A scan that **finds nothing must change nothing** — no republish, no commit.
  An unchanged page is the correct output of a quiet day, and it is the only
  thing that keeps the age counter honest.
- `state/observations.json` **must stay tracked in git**. It was caught by
  `state/*.json` and un-ignoring it is what makes accumulation survive a fresh
  clone; two tests guard that and the derived `snapshot.json` staying ignored.
- `state/refresh-log.jsonl` and `python3 -m macro heartbeat` remain. They now
  record manual scans rather than scheduled ones — same purpose, which is that a
  quiet scan and a scan that never happened must not look alike.
- **Do not recreate a scheduled Routine** without the user asking for it by
  name. If one is ever wanted again, the blocker to fix first is the trigger's
  `allowed_push_branches: []`: without a push its finds die with the container.

## Release prints (actual vs expected)

`macro/release.py` holds the expectation engine and it refuses three things on
purpose: an `Expectation` cannot be built without a carrier for **both** the
actual and the consensus; a print declares **exactly one** transmission channel
(`hawkish_sign` or `growth_sign`, never both); and the market verdict is
**regime-conditional** and returns `Insufficient` when the regime is unknown.

It does **not** own the impulse-to-direction mapping. That lives in
`macro.reaction`, and `assess()` reads the `S&P 500` cell out of `build_matrix`
and translates its `Direction`. A second copy here disagreed with the existing
engine on whether weak growth under an inflation-dominant regime is bought;
`TestOneReactionFunction` now pins them together. Reusing those cells also
exposed a real defect in `reaction.py`: several `mechanism` strings described
the hot/strong case while their `Direction` flipped with the sign, so a bullish
cell carried bearish prose. Fixed for USD, S&P, HY and VIX in `_inflation` and
USD and S&P in `_growth`, plus the sign-laden chain sentences.

Figures live in `RELEASE_CLOCK[...]["prints"]` in `macro/live.py`. The
released/pending split is decided against the snapshot's own `captured` stamp,
never the renderer's wall clock, so a snapshot renders identically whenever it
is regenerated. Tolerance is zero by default; a non-zero band (weekly claims,
5k) is a stated design choice carried in that print's own note.

## The release calendar, and why it does not need a schedule

`RELEASE_CLOCK` runs to **17 December 2026** — eighteen pending events. That
depth is the answer to "we need more pending data", and it is also the answer
to whether a weekly Routine is needed: **scheduled release dates are published
in advance and do not move**, so a whole quarter loads in one pass and the
countdown panel cannot run dry. Before this it held two events, both on the
same Wednesday. What genuinely needs a session is the **actuals**, and those
exist only on the days they print — two or three that matter per month. A
weekly loop would spend a context re-reading a calendar that had not changed.

Three things the calendar enforces, each with a probe and a mutant:

- **Pending rows never carry a verdict.** A release that has not printed may
  show `forecasts` — what the market is carrying — rendered by
  `render_forecasts()` under an `AWAITING` header with `NOT PRINTED` in the
  risk column. `Forecast` is a *separate type* from `Expectation` with no
  `actual` field at all, so no caller can forget to check for one.
- **Ordering is pending-ascending then released-descending**, via `_order()`
  and `_invert_stamp()`. Source order buried the imminent FOMC under last
  week's CPI the moment the list grew past four rows.
- **A carrier that published a date but no time gets `"day": True`**, a
  midnight stamp and a day-only countdown (`data-day` in the DOM). The BoJ
  publishes no decision time; an invented hour on it is exactly the false
  precision the earnings panel already refuses.

**UTC conversions are the sharp edge here and are done by hand.** US clocks go
back 1 November 2026 and European clocks 25 October, so 08:30 ET is 12:30Z
through October and 13:30Z from November, and the ECB's 14:15 CET is 12:15Z in
September but 13:15Z in October. Getting one wrong is a one-hour error on the
most market-moving print of the month.

**When a release prints**, move its row from `forecasts` to `prints`, add the
`actual` and its carrier, and regenerate. The countdown flips to RELEASED on
its own; the verdict only appears because a human sourced the number.
