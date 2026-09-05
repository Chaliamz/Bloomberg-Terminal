# Specification coverage

Section-by-section map from the Institutional Macro Intelligence & News Radar
master prompt to the implementation, with an honest note on what is *not*
implemented and why.

| # | Spec section | Where it lives | Status |
|---|---|---|---|
| 1 | Core objective / 16 event categories | `macro/scoring.py::EventClass` | 17 event classes modelled |
| 2 | Real-time radar, urgency 0-100 | `macro/scoring.py`, `macro/radar.py::cmd_radar` | Bands match the spec exactly (90/75/50/25) |
| 3 | Global macro calendar | `macro/calendar_spec.py` | 58 releases across 11 jurisdictions; **semantics and clocks only, never values** |
| 4 | Expectation vs actual engine | `macro/surprise.py` | Absolute + standardised surprise; z-score only against supplied history |
| 5 | Central-bank intelligence | `macro/centralbank.py` | 5-level tone scale, weighted lexicon, statement diffing incl. deletions |
| 6 | Public speech radar | `macro/centralbank.py::speech_radar` | Hawkish/dovish/neutral trigger maps; refuses to invent pricing |
| 7 | "Minutes before" mode | `macro/preevent.py` | T-60 / T-30 / T-15 / T-5, final event map, unresolved-input ledger |
| 8 | Event-reaction matrix | `macro/reaction.py` | 13 assets × derived (not tabulated) cells, each with its mechanism |
| 9 | Second-order analysis | `macro/reaction.py::analyse_orders` | First/second/third order + all 10 spec questions |
| 10 | Liquidity & market-structure radar | `macro/liquidity.py::detect_anomaly` | Flags unexplained moves; **enumerates candidates, never names a cause** |
| 11 | Yield-curve intelligence | `macro/curve.py` | 4 canonical regimes + real/breakeven attribution + noise floor |
| 12 | Liquidity & financial conditions | `macro/liquidity.py::assess` | 16-input panel, hard alarms, coverage-weighted confidence |
| 13 | Geopolitical radar | `macro/scoring.py`, brief §10 | Scoring and slot exist; **item ingestion is the operator's job** |
| 14 | Source hierarchy | `macro/sources.py` | 4 tiers by registrable domain suffix |
| 15 | Source confirmation engine | `macro/sources.py::confirm` | Independence by host, 6 misinformation patterns |
| 16 | Information-latency score | `macro/scoring.py::information_latency` | Per event class; carries an explicit no-privileged-access disclaimer |
| 17 | Market surprise engine | `macro/surprise.py::surprise_distribution` | Mild/moderate/extreme bands, UNKNOWN without sigma |
| 18 | Liquidity / stop-hunt / vol analysis | `macro/structure.py` | Swings, equal highs/lows, pools, FVGs, displacement, sweeps |
| 19 | Trade setup engine | `macro/setups.py::build_setup` | 3R floor, 5R preference, five independent refusal gates |
| 20 | Event whipsaw protocol | `macro/setups.py::whipsaw_plan` | Four-phase sequence, no first-spike entry |
| 21 | Options & volatility radar | — | **Not implemented.** See "Deliberate gaps" below |
| 22 | Crypto macro radar | `macro/reaction.py`, brief §9 | Transmission chain modelled; flow inputs must be supplied |
| 23 | News impact score | `macro/scoring.py::score_event` | All six sub-scores + documented composite |
| 24 | Daily institutional brief | `macro/brief.py` | All 12 sections; bias defaults to WAIT |
| 25 | Event alert format | `macro/events.py::render_alert` | Every spec field, UNKNOWN where unsupplied |
| 26 | Noise filter | `macro/noise.py` | Dedupe, clickbait, opinion, staleness, expectation-change test |
| 27 | Information advantage framework | `macro/reaction.py`, `macro/radar.py::cmd_what_matters` | Before / new / repricing / transmission / positioning / structure |
| 28 | Output principles | `macro/types.py::Category` | FACT / INTERPRETATION / SCENARIO / SPECULATION on every result type |
| 29 | Real-time commands | `macro/radar.py` | All 14 commands, on the CLI too |
| 30 | Final operating rule | Everything | Enforced in `tests/test_integrity.py` |

## Deliberate gaps

**Section 21 (options and volatility) is not implemented, and this is a
decision rather than an oversight.** Every quantity it asks for — IV rank,
skew, gamma exposure, dealer positioning, open interest by strike — requires an
options chain that no free public endpoint provides in usable form. An engine
that computed "gamma walls" from unavailable data would be exactly the
fabrication the rest of this system exists to prevent. The scoring engine
accepts an `expected_volatility` input, so a user with an options feed can wire
one in; what is refused is manufacturing the number.

The same reasoning limits three other areas:

- **Positioning** (CFTC COT, dealer inventories) is a supplied input, never inferred.
- **Market-implied probabilities** (OIS, fed funds futures) are supplied, never assumed.
- **Consensus forecasts** are supplied, never generated. There is no bundled
  consensus table anywhere in this repository.

## What "never fabricate" means in code, not prose

- `Observation.value` is `None` for anything unknown; there is no default.
- Engines return `Insufficient(reason, missing)` rather than a number.
- `same_unit()` raises on a unit mismatch instead of coercing.
- The surprise engine ships **no** sigma table, so a z-score without supplied
  history is impossible, not merely discouraged.
- `calendar_spec` refuses to derive a date for any agency-scheduled release.
- Data adapters return `Unavailable` and never substitute a cached value.
- `detect_anomaly` returns weighted candidate explanations and an instruction
  to verify — it structurally cannot name a cause.
- `tests/test_integrity.py` asserts these properties end to end.
