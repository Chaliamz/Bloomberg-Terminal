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

- **The page carries a live client and it works from `file://`.** Confirmed in
  Chromium by `tools/verify_live.py`, which stands up venue-shaped local servers
  and drives the real page against them. Two transports, each blocked in a
  different place:
  - **Binance `wss://stream.binance.com:9443/ws/btcusdt@ticker`.** WebSockets are
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
  built on WebSearch inherits that lag — this is the ceiling on the scheduled
  Routine and no amount of scheduling fixes it.
- **`python -m macro live 30` IS live**, run anywhere with egress. Binance
  `/api/v3/ticker/24hr` is Tier 1 for its own last trade. The adapter is
  `parse_binance_ticker`; it returns None rather than guess on a malformed body,
  missing or non-numeric field, wrong symbol, non-positive price, future stamp,
  high-below-low, or a seconds-epoch sent where milliseconds belong.
- Price anchors from a live poll are throttled by `ANCHOR_MIN_GAP` (900s). A 30s
  poll would otherwise append 2,880 anchors a day and the liquidity map
  recomputes over all of them; a test polls 40 times and asserts the series does
  not grow.

## Unattended refresh (standing, set by the user)

The user asked for continuous refresh: "Data should refresh 24/7. Anything new
happens, you update them immediately."

- The runbook is `REFRESH.md`. A scheduled session follows it; it must not
  re-derive the environment's limits each run.
- A scheduled run **appends to `state/observations.json` through
  `python3 -m macro observe`** and never edits `macro/seed.py`. The store
  validates through `PriceAnchor` and refuses a missing source or tier, a
  malformed or future stamp, a duplicate, and a non-finite or non-positive price.
- **A scan that finds nothing must change nothing** — no republish, no commit.
  An unchanged page is the correct output of a quiet hour, and it is the only
  thing that keeps the age counter honest.
- **The loop is not yet verified end to end.** Three manual runs each finished in
  ~40s having pushed nothing, which is the signature of a session with no
  checkout (the Routine has no `sources`). The prompt now clones if the repo is
  absent. Confirm by checking whether `state/refresh-log.jsonl` gains lines.
- The hourly Routine is `trig_011kkfqqtmtakBbQ7SxPB8oU`. It republishes to the
  existing artifact URL so the user's link keeps working.
- A scheduled run has **nobody to answer a permission prompt**. Any command
  outside the runbook can block it for ever - the first verification run stalled
  on `env | sort`. The Routine prompt therefore forbids environment probing and
  exploration, and REFRESH.md repeats it.
- Every run appends to `state/refresh-log.jsonl` via `python3 -m macro
  heartbeat`, including quiet ones, and pushes it. A quiet run leaves the
  page alone but must still leave a trace: a dead loop and a quiet loop are
  otherwise indistinguishable.
- `state/observations.json` **must stay tracked in git**. It was caught by
  `state/*.json` and un-ignoring it is what makes accumulation survive a fresh
  clone; two tests guard that and the derived `snapshot.json` staying ignored.
