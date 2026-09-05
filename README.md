# Institutional Macro Intelligence & News Radar

A macro event-intelligence system: release calendar semantics, surprise
standardisation, central-bank language diffing, yield-curve and funding-regime
classification, derived cross-asset transmission maps, ICT-style market
structure, and an R:R-gated setup engine — behind a Bloomberg-style command
surface.

Python 3.11+, **standard library only**, 284 tests.

## The one design rule

The system reports what it knows, with provenance, and returns `UNKNOWN`
everywhere else. It never fabricates a source, timestamp, consensus figure,
market level or market reaction, and it never claims non-public access.

That rule is enforced in code, not asserted in prose:

- Every number is an `Observation` carrying value, unit, timestamp and source
  tier. There is no default value anywhere in `macro/types.py`.
- Engines return `Insufficient(reason, missing=[...])` instead of a
  plausible-looking number.
- **There is no built-in surprise-volatility table**, so a z-score without
  supplied history is impossible rather than merely discouraged.
- The calendar refuses to derive a date for any agency-scheduled release.
- Data adapters return `Unavailable` and never substitute a cached value.
- The unexplained-move detector emits weighted *candidate* explanations and a
  verification instruction; it structurally cannot name a cause.
- `tests/test_integrity.py` asserts all of the above end to end.

The practical consequence: a freshly started radar tells you almost nothing,
and every blank is labelled. That is the intended behaviour. A dashboard full
of confident numbers you cannot trace is worth less than an honest blank.

## The live terminal

`python -m macro terminal` renders `board/macro-desk-live.html` from
`state/snapshot.json`: a cross-asset board, a tiered and deduplicated news feed,
countdowns to the next primary releases, and a source-and-freshness audit of
every figure on the page.

```bash
python -m macro live            # one scan cycle, then regenerate
python -m macro live 60         # 24/7 daemon, polling every 60s
python3 tools/verify_terminal.py
```

Panels: cross-asset board, timestamped squawk wire, equity and crypto Fear &
Greed gauges, a BTC liquidation heatmap, a geopolitical board that states each
event's transmission channel and when it happened, ETF flows, release
countdowns, curve, policy, cross-asset transmission, and a source-and-freshness
audit of every figure — under a function-key command bar and a status line.

The chrome follows professional-terminal convention (density, monospace grids,
hard panel divisions, a command line) but **not** amber-on-black: that scheme is
Bloomberg's protected brand identity, so the accent here is teal and colour is
spent on encoding magnitude rather than on decoration.

### The liquidation heatmap

Price on the vertical, time on the horizontal, leverage density as colour — the
published form. It is computed, not observed, and the page says so:

1. At each **observed** close, positions opened there liquidate at
   `price x (1 - 1/N)` and `price x (1 + 1/N)`; those levels join a pending set.
2. A pending level is removed when price is later observed to sweep through it.
3. Between two observations nothing is known, so the field is held constant and
   the price line is drawn dashed. **No price is ever interpolated.**

The colour ramp is a sequential magnitude scale verified monotonic in OKLab
lightness (step gaps 0.086–0.110, 15.9:1 contrast at the top) — asserted by
`tests/test_live.py`, not eyeballed. The field is *not* open-interest weighted;
that needs per-exchange position data this terminal does not have, and it is not
guessed. Time resolution is the data's, not the renderer's: feed it a real price
series and the same renderer draws every column.

Alongside it, **observed** 24h liquidation totals with their window stated, and a
**computed** leverage ladder on the carried spot.

The scanner (`macro/live.py`) polls **primary agency endpoints first** and wires
second, because a statistical release is public at the agency URL the instant the
embargo lifts &mdash; typically before wire coverage clears. That is the whole of
the latency edge, it is public, and no privileged access is claimed.

Two invariants make the terminal safe to trust:

- **A quote without a source is not representable.** `Quote` rejects a missing
  source, unit, tier or timestamp at construction.
- **An unreachable source never restamps stale data.** The prior value survives
  with its *original* timestamp and the page's age counter keeps climbing, so it
  can never look fresher than it is.

Where two outlets disagreed, the higher tier is carried at reduced confidence and
the disagreement is printed on the page rather than resolved away.

## The board

`python -m macro board` regenerates two artefacts from one registry in
`macro/board.py`:

| Output | What it is |
|---|---|
| `docs/intelligence-terminal.md` | the architecture document: doctrine, source hierarchy, module registry, feed registry |
| `board/cold-start-terminal.html` | a standalone dark terminal board, no build step, no external assets beyond webfonts |

Both are generated, never hand-edited, so neither can claim more than the package
delivers &mdash; `tests/test_board.py` fails if a committed artefact drifts from the
registry, if the page addresses a DOM node that no longer exists, or if a
market-like number appears on a page whose whole premise is that it holds none.

Live rendering is verified separately with a headless browser:

```bash
python3 tools/verify_board.py       # 3 viewports x 2 motion settings + tape geometry
```

## Quick start

```bash
python -m macro demo                  # full worked example (all values SYNTHETIC)
python -m macro selftest              # run the test suite
python -m macro coverage              # what the calendar models

python -m macro radar                 # highest-priority current developments
python -m macro next                  # rule-derivable upcoming events
python -m macro cpi                   # complete CPI event map
python -m macro pre-event US_NFP      # T-60 / T-30 / T-15 / T-5 framework
python -m macro market --state my_state.json --html out/terminal.html
```

Commands map 1:1 to the spec: `radar`, `next`, `speeches`, `fed`, `ecb`, `cpi`,
`nfp`, `risk`, `liquidity`, `market`, `setup`, `alert`, `pre-event`,
`what-matters`.

### Feeding it real data

Copy `state.example.json`, fill in what you can actually source, delete what
you cannot. Anything absent stays `UNKNOWN`.

```bash
cp state.example.json my_state.json
python -m macro risk --state my_state.json
```

FRED is wired in for US rates, real yields, breakevens, spreads and funding:

```bash
export FRED_API_KEY=...     # free: https://fredaccount.stlouisfed.org/apikeys
python -m macro market --fetch
```

Without the key the adapter reports `DATA UNAVAILABLE` and every field stays
UNKNOWN. It does not fall back to bundled numbers, because a stale value
rendered as current is worse than a blank.

> **Network note.** The US Treasury par-yield adapter (`macro/data/treasury.py`)
> needs outbound access to `home.treasury.gov`. In sandboxed environments whose
> egress policy does not allow that host, the adapter returns
> `network error: Tunnel connection failed: 403 Forbidden` — that is the policy
> refusing the connection, not a defect. The code path is exercised by tests
> either way.

## What each engine does

| Module | Job | The non-obvious part |
|---|---|---|
| `types` | Observations, provenance, `Insufficient` | Unit mismatches raise; they never coerce |
| `surprise` | Actual vs consensus vs previous vs revised | Emits a *macro impulse*, never a market call |
| `scoring` | Urgency, latency, credibility, priority | Credibility is a multiplier, not an addend |
| `calendar_spec` | 58 releases, 11 jurisdictions | Semantics and clocks only — never values |
| `centralbank` | Tone scale, statement diffing | Deleted guidance is treated as a signal in itself |
| `curve` | Bull/bear × steepen/flatten | Refuses to attribute without real yields and breakevens |
| `liquidity` | Funding regime, unexplained moves | Ambiguous-sign inputs are excluded, not assigned a convenient direction |
| `reaction` | Cross-asset maps, second-order | Cells are *derived* from a stated chain, not tabulated |
| `structure` | Swings, BOS/CHoCH, sweeps, FVGs | Pivot confirmation lag is enforced — no lookahead |
| `setups` | R:R-gated setups, whipsaw protocol | Costs enter both legs; five independent refusal gates |
| `sources` | Tiering, confirmation | Independence counted by host, not by citation |
| `noise` | Does this change what was believed? | The only question that decides ranking |
| `preevent` | T-60/30/15/5 | Ships an explicit unresolved-input ledger |
| `brief` | 12-section daily dashboard | Bias defaults to `WAIT` and must be earned |
| `radar` | Event book, command surface | Reports an empty book rather than filling it |

Full section-by-section mapping, including what is deliberately **not**
implemented and why: [`docs/spec-coverage.md`](docs/spec-coverage.md).

## Three design decisions worth arguing with

**Credibility gates priority multiplicatively.**
`priority = core × (0.25 + 0.75 × credibility/100)`. An unverifiable claim
keeps at most 25% of its raw score. Without this, "SOURCES: emergency 100bp cut
imminent" from an anonymous account outranks a confirmed CPI print, because its
notional impact is larger. Tested in `test_integrity.py`.

**The equity sign is a function of the regime, not of the data.**
A weaker-growth surprise maps to S&P *up* in an inflation-dominant regime and
S&P *down* in a growth-dominant one. Under `MacroRegime.UNKNOWN` every cell
returns `AMBIGUOUS` with confidence 0.0. Most macro tooling hardcodes one
regime's correlations and then breaks precisely when the regime turns — which
is when the money moves.

**Structure never looks ahead.**
A fractal pivot is not knowable until `right` bars have printed after it. Every
`Swing` records `confirmed_at`, and a break of structure may only reference a
pivot confirmed strictly before the breaking bar. `test_structure.py` asserts
this invariant across the whole event list. Without it a structure engine
produces a beautiful backtest that cannot be traded.

## Risk-arithmetic guards

The setup engine refuses rather than degrades. Covered by tests:

- Zero-width stop → refused, not a division by zero.
- Inverted stop/target geometry → refused per side.
- Costs enter *both* the reward numerator and the risk denominator, and the
  refusal message says how much R the costs alone consumed.
- Position size denominator includes costs; contract multiplier is explicit.
- Risk fraction outside 0–5% → refused.
- Gap risk through the stop is stated as an uncovered assumption, not hidden.

## Not implemented, on purpose

Options and volatility surface analytics (spec §21) — IV rank, skew, gamma
exposure, dealer positioning. Every one needs an options chain no free public
endpoint provides in usable form, and computing "gamma walls" from unavailable
data is exactly the fabrication this system exists to prevent. Positioning,
market-implied probabilities and consensus forecasts are supplied inputs for
the same reason. There is no bundled consensus table anywhere in this repo.

## Layout

```
macro/            engines (see table above)
macro/data/       FRED, US Treasury, snapshot store
macro/render/     single-file HTML terminal
macro/board.py    module registry -> board + architecture doc
macro/live.py     snapshot schema + 24/7 primary-source scanner
macro/terminal.py the live cross-asset terminal
macro/seed.py     captured market snapshot, fully attributed
board/            generated pages (standalone + embeddable fragments)
state/            snapshot.json, the terminal's data source
prompts/          operating system prompt for LLM-driven use
docs/             spec coverage map, architecture document
tools/            headless-browser verification for the board
tests/            284 tests, stdlib unittest
state.example.json
```

## Caveats

- Release clock times are institutional conventions that agencies do revise.
  Every entry carries a `confidence` and a `verify` URL — check before trading.
- Holiday calendars are not modelled, so `NTH_BUSINESS_DAY` and `NTH_WEEKDAY`
  rules shift around public holidays. The affected entries say so.
- Tone classification is lexical. It measures policy-loaded wording, not
  intent, and reports its own confidence based on how much signal-bearing
  language it actually found.
- Reaction-matrix confidences are calibrated judgement, not fitted parameters.
  They are stated per cell so they can be argued with.
- On hosts with trimmed tzdata, install the optional extra: `pip install .[tz]`.

Nothing here is investment advice.
