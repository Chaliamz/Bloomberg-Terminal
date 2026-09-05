# Institutional market intelligence terminal

The operating architecture behind the cold-start board
(`board/cold-start-terminal.html`, regenerate with `python -m macro board`).

This document and the board are both generated from one registry in
`macro/board.py`, so neither can claim more than the package delivers.

**40 modules: 18 built, 3 partial, 19 specified.**
Zero feeds are connected. Every value slot in the system reads UNKNOWN until a
primary source is attached, and that is the designed behaviour rather than a gap.

---

## Doctrine

**Primary before press.** A Tier-2 wire reporting X is never promoted to X confirmed without the Tier-1 document. `Reuters reports X` and `the agency published X` are different claims and stay different.

**Independence by organisation.** Twenty articles tracing to one original report is one information event, not twenty confirmations.

**Credibility multiplies.** An unverifiable claim keeps at most a quarter of its raw priority. A loud anonymous claim cannot outrank a confirmed release.

**Regime decides the sign.** The same surprise maps to opposite equity outcomes across regimes. With the regime unresolved the directional answer is AMBIGUOUS, not a guess.

**Never name an unexplained cause.** A move without a headline yields weighted candidate explanations and a verification instruction, never an invented reason.

**Latency is public detectability.** How early something can be seen in public sources. It is never a claim of embargoed, privileged or non-public access.

**No trade beats a bad trade.** Catalyst, structure, liquidity target, invalidation and >=3R after costs, or the answer is NO TRADE.

**Six categories never mix.** Fact, data, analysis, inference, scenario, rumor. Each is labelled; none is silently promoted.

---

## Source hierarchy

- **Tier 1 &mdash; Primary / official** (overrides everything below): Federal Reserve, FOMC, US Treasury, BLS, BEA, Census, CFTC, SEC, FDIC, OCC, OFAC, EIA, DoE, ECB, Eurostat, European Commission, ESMA, EBA, BoE, BoJ, SNB, PBoC, BoC, RBA, RBNZ, Riksbank, Norges Bank, RBI, BCB, Banxico, BIS, IMF, World Bank
- **Tier 2 &mdash; Institutional press** (speed and context, never override): Reuters, Bloomberg, Financial Times, WSJ, Dow Jones, AP, CNBC, Nikkei Asia, The Economist
- **Tier 3 &mdash; Professional commentary** (named and attributable): Sell-side economists, Strategists, Credible financial journalists
- **Tier 4 &mdash; Social / alternative** (never treated as confirmed): X, Telegram, Reddit, Blogs, Anonymous accounts

Tier 4 is never treated as confirmed. Anything unverified is labelled
`UNCONFIRMED - REQUIRES VERIFICATION` and excluded from any trade decision.

---

## Geopolitical transmission

Never report that tensions increased. Translate:

```
Event -> Supply -> Commodity -> Inflation -> Central bank -> Rates -> FX -> Equities -> Credit -> Crypto
```

If a link cannot be established - no affected supply, no commodity channel - the
event scores high on attention and low on market relevance, and the system says
so rather than manufacturing a narrative.

---

## Module registry

| Module | Spec | Status | Implementation | Feed required |
|---|---|---|---|---|
| Source hierarchy & tiering | §1 · §2 | **BUILT** | `macro/sources.py` | Wire access + institution registry |
| Information integrity / anti-propaganda | §3 · §4 | **BUILT** | `macro/sources.py` | Tier-1 document store |
| Event surprise model | §4 · §33 | **BUILT** | `macro/surprise.py` | Consensus + historical surprise series |
| Release calendar & indicator semantics | §5 · §6 (schedule layer) | **BUILT** | `macro/calendar_spec.py` | Agency release calendars |
| Central-bank speech intelligence | §15 | **BUILT** | `macro/centralbank.py` | Speech archives (Fed · ECB · BoE · BoJ) |
| Yield-curve regime | §9 (curve layer) | **BUILT** | `macro/curve.py` | UST par curve · TIPS · breakevens |
| Global liquidity & funding conditions | §10 | **BUILT** | `macro/liquidity.py` | BIS · NY Fed · FRED |
| Cross-asset transmission & second order | §12 · §19 | **BUILT** | `macro/reaction.py` | Cross-asset price series |
| Unexplained-move detector | §50 | **BUILT** | `macro/liquidity.py` | Tick data + headline stream |
| Market structure & liquidity mapping | §30 | **BUILT** | `macro/structure.py` | OHLCV series |
| Trade gate | §51 | **BUILT** | `macro/setups.py` | Structure + catalyst + cost model |
| Event whipsaw protocol | §31 (execution layer) | **BUILT** | `macro/setups.py` | Pre-event range levels |
| Duplicate & noise filter | §26 · §43 | **BUILT** | `macro/noise.py` | Headline stream |
| Information priority score | §45 | **BUILT** | `macro/scoring.py` | Scored events |
| Information latency & staleness | §16 · §42 | **BUILT** | `macro/scoring.py` | Publication timestamps |
| Event alert format | §25 | **BUILT** | `macro/events.py` | Any scored event |
| Daily dashboard / brief | §46 | **BUILT** | `macro/brief.py` | Populated market state |
| Feed adapters | §1 (transport) | **BUILT** | `macro/data/` | FRED key · home.treasury.gov egress |
| Regime detection | §39 · §41 | **PARTIAL** | `macro/regime.py · liquidity.py` | Full cross-asset panel |
| Pre-event radar | §31 | **PARTIAL** | `macro/preevent.py` | Consensus · implied vol · positioning |
| Command surface | §47 – §50 | **PARTIAL** | `macro/radar.py` | Populated event book |
| Inflation breadth & persistence | §5 | **SPEC** | &mdash; | BLS component detail |
| Labor regime classifier | §6 | **SPEC** | &mdash; | BLS · DOL/ETA · JOLTS |
| Growth nowcasting | §7 · §32 | **SPEC** | &mdash; | PMI · ISM · freight · claims · tax receipts |
| Fiscal policy engine | §8 | **SPEC** | &mdash; | CBO · Treasury statements |
| Treasury auction analytics | §9 (auction layer) | **SPEC** | &mdash; | TreasuryDirect results |
| Market-implied policy pricing | §17 | **SPEC** | &mdash; | OIS · fed funds · SOFR futures |
| Positioning engine | §18 | **SPEC** | &mdash; | CFTC COT · ETF flows |
| Derivatives & liquidation radar | §25 · §26 | **SPEC** | &mdash; | Options chain · OI · funding |
| Energy intelligence | §13 | **SPEC** | &mdash; | EIA · IEA · OPEC |
| Commodity intelligence | §14 | **SPEC** | &mdash; | Exchange stocks · crop reports |
| Central-bank consensus map | §16 | **SPEC** | &mdash; | Official calendars + speeches |
| Geopolitical & early warning | §11 · §35 · §48 | **SPEC** | &mdash; | ACLED · SIPRI · government primaries |
| Supply-chain & tariff | §36 · §37 | **SPEC** | &mdash; | Freight · Baltic · customs · WTO |
| Crypto on-chain intelligence | §20 – §24 | **SPEC** | &mdash; | Glassnode · CryptoQuant · CoinGlass |
| Capital-flow map | §40 | **SPEC** | &mdash; | Treasury TIC · fund flows |
| Systemic-risk radar | §38 | **SPEC** | &mdash; | FDIC · CDS · spreads |
| Market reaction analyzer | §34 | **SPEC** | &mdash; | Live cross-asset tape |
| Narrative vs data | §44 | **SPEC** | &mdash; | Headline stream + macro series |
| Confluence scoring | §52 | **SPEC** | &mdash; | All engines populated |

`BUILT` means implemented in `macro/` and covered by `python -m macro selftest`.
`PARTIAL` means part of the specified section exists; it is not a softer word for
built. `SPEC` means defined here and not implemented.

---

## Feed registry

| Function | Source of record | Role | State |
|---|---|---|---|
| US macro | BLS · BEA · Census | Primary data | not connected |
| Monetary policy | Federal Reserve / FOMC | Rates + speeches | not connected |
| Europe | ECB · Eurostat | Macro + policy | not connected |
| Global macro | IMF · World Bank · BIS | System level | not connected |
| Global liquidity | BIS | Cross-border credit | not connected |
| Treasury flows | US Treasury TIC | Foreign capital | not connected |
| Energy | EIA · IEA · OPEC | Physical market | not connected |
| Positioning | CFTC | Futures positioning | not connected |
| Geopolitics | UN · NATO · governments | Primary confirmation | not connected |
| Conflict | ACLED | Near-real-time events | not connected |
| Military | SIPRI | Arms + expenditure | not connected |
| Crypto on-chain | Glassnode · CryptoQuant | Network + supply | not connected |
| Crypto derivatives | CoinGlass · Kaiko | OI · funding · liquidations | not connected |
| Breaking news | Reuters · Bloomberg · FT | Speed + context | not connected |
| Deep research | IMF · BIS · central banks | Analysis | not connected |

FRED and the US Treasury par-yield curve have adapters in `macro/data/`. Both
return `Unavailable` rather than substituting a cached value when the source is
unreachable.

---

## Priority score

```
core     = 0.36*impact + 0.26*surprise + 0.18*volatility
         + 0.10*latency + 0.10*direction
priority = core * (0.25 + 0.75 * credibility/100)
```

Credibility multiplies rather than adds, with a floor of 0.25. Urgency bands:
90-100 EXTREME, 75-89 HIGH, 50-74 MEDIUM, 25-49 LOW, 0-24 INFORMATIONAL.

---

## The highest-value gap

`§34 Market reaction analyzer` - expected reaction against actual - is
specified and unbuilt. A divergence (hot CPI, yields up, dollar down) carries
more information than the release that caused it, and nothing in the system
currently detects one. `§17 market-implied policy pricing` is the second: until
it exists, *what is already priced* stays UNKNOWN everywhere it is asked.

---

*Nothing in this repository is investment advice.*
