# Bloomberg-Terminal — operating rules

## Delivery gate (standing instruction, set by the user)

**Never send output until it has been tested.** Before any deliverable reaches the
user, in this order:

1. **Test** — run the full unit suite (`python3 -m unittest discover -s tests -t .`)
   AND both browser harnesses (`tools/verify_terminal.py`, `tools/verify_board.py`).
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
- The hourly Routine is `trig_011kkfqqtmtakBbQ7SxPB8oU`. It republishes to the
  existing artifact URL so the user's link keeps working.
- A scheduled run has **nobody to answer a permission prompt**. Any command
  outside the runbook can block it for ever - the first verification run stalled
  on `env | sort`. The Routine prompt therefore forbids environment probing and
  exploration, and REFRESH.md repeats it.
- `state/observations.json` **must stay tracked in git**. It was caught by
  `state/*.json` and un-ignoring it is what makes accumulation survive a fresh
  clone; two tests guard that and the derived `snapshot.json` staying ignored.
