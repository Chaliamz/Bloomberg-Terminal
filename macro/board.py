"""Cold-start board: the operating architecture rendered as a standalone page.

Why this is code and not a hand-written HTML file
-------------------------------------------------
The board states how many modules are built. A hand-maintained page drifts from
the package the moment a module lands, and a status board that lies about its
own system is worse than none. So the registry below is the single source of
truth, the page is generated from it, and ``tests/test_board.py`` asserts the
rendered counts equal the registry counts.

Status is deliberately conservative. PARTIAL means some of the specified
section is implemented; it is not a softer word for BUILT.
"""

from __future__ import annotations

import html
import json
from dataclasses import dataclass
from enum import Enum

__all__ = ["MODULES", "Status", "Module", "counts", "render",
           "render_markdown", "main"]


class Status(str, Enum):
    BUILT = "BUILT"       # implemented in macro/ and covered by tests
    PARTIAL = "PARTIAL"   # part of the specified section exists
    SPEC = "SPEC"         # specified, not implemented


@dataclass(frozen=True)
class Module:
    name: str
    sections: str
    status: Status
    module: str           # implementing module, or "" when unbuilt
    feed: str             # the source that would fill it
    note: str = ""


B, P, S = Status.BUILT, Status.PARTIAL, Status.SPEC

MODULES: tuple[Module, ...] = (
    # ---- implemented ----------------------------------------------------
    Module("Source hierarchy & tiering", "§1 · §2", B, "macro/sources.py",
           "Wire access + institution registry",
           "Four tiers by registrable domain suffix; independence counted by host."),
    Module("Information integrity / anti-propaganda", "§3 · §4", B, "macro/sources.py",
           "Tier-1 document store",
           "Six misinformation patterns; conflicting reports never resolve to the "
           "more dramatic claim."),
    Module("Event surprise model", "§4 · §33", B, "macro/surprise.py",
           "Consensus + historical surprise series",
           "Standardised only against supplied history; no bundled sigma table."),
    Module("Release calendar & indicator semantics", "§5 · §6 (schedule layer)", B,
           "macro/calendar_spec.py", "Agency release calendars",
           "58 releases, 11 jurisdictions. Clocks and signs only, never values."),
    Module("Central-bank speech intelligence", "§15", B, "macro/centralbank.py",
           "Speech archives (Fed · ECB · BoE · BoJ)",
           "Weighted lexicon, five-level tone, statement diffing including deletions."),
    Module("Yield-curve regime", "§9 (curve layer)", B, "macro/curve.py",
           "UST par curve · TIPS · breakevens",
           "Four canonical moves; refuses attribution without real yields."),
    Module("Global liquidity & funding conditions", "§10", B, "macro/liquidity.py",
           "BIS · NY Fed · FRED",
           "16-input panel with hard alarms and coverage-weighted confidence."),
    Module("Cross-asset transmission & second order", "§12 · §19", B, "macro/reaction.py",
           "Cross-asset price series",
           "Cells derived from a stated chain, not a correlation table."),
    Module("Unexplained-move detector", "§50", B, "macro/liquidity.py",
           "Tick data + headline stream",
           "Emits weighted candidates; structurally cannot name a cause."),
    Module("Market structure & liquidity mapping", "§30", B, "macro/structure.py",
           "OHLCV series",
           "Pivot-confirmation lag enforced: no lookahead in any break."),
    Module("Trade gate", "§51", B, "macro/setups.py",
           "Structure + catalyst + cost model",
           "Five independent refusal gates; costs enter both legs and the size."),
    Module("Event whipsaw protocol", "§31 (execution layer)", B, "macro/setups.py",
           "Pre-event range levels",
           "Four-phase sequence; never enter the first spike."),
    Module("Duplicate & noise filter", "§26 · §43", B, "macro/noise.py",
           "Headline stream",
           "Near-duplicate collapse; the expectation-change test decides ranking."),
    Module("Information priority score", "§45", B, "macro/scoring.py",
           "Scored events",
           "Credibility multiplies rather than adds; floor 0.25."),
    Module("Information latency & staleness", "§16 · §42", B, "macro/scoring.py",
           "Publication timestamps",
           "Public detectability only — never a claim of non-public access."),
    Module("Event alert format", "§25", B, "macro/events.py",
           "Any scored event",
           "Every field renders UNKNOWN rather than a placeholder."),
    Module("Daily dashboard / brief", "§46", B, "macro/brief.py",
           "Populated market state",
           "Twelve sections; trading bias defaults to WAIT and must be earned."),
    Module("Feed adapters", "§1 (transport)", B, "macro/data/",
           "FRED key · home.treasury.gov egress",
           "Return Unavailable rather than substituting a cached value."),
    # ---- partial --------------------------------------------------------
    Module("Regime detection", "§39 · §41", P, "macro/regime.py · liquidity.py",
           "Full cross-asset panel",
           "Risk/liquidity regime is classified from data; monetary, inflation and "
           "growth regimes are supplied inputs. Geopolitical and volatility regimes "
           "are absent."),
    Module("Pre-event radar", "§31", P, "macro/preevent.py",
           "Consensus · implied vol · positioning",
           "T−60 / T−30 / T−15 / T−5 implemented. The T−24h slice specified in §31 "
           "is not."),
    Module("Command surface", "§47 – §50", P, "macro/radar.py",
           "Populated event book",
           "WHAT MATTERS and BEFORE THE MARKET are built; WHY IS PRICE MOVING is "
           "partial via the anomaly detector; EARLY WARNING is not implemented."),
    # ---- specified, not built -------------------------------------------
    Module("Inflation breadth & persistence", "§5", S, "",
           "BLS component detail",
           "Breadth, persistence, services/goods split and energy pass-through are "
           "not computed."),
    Module("Labor regime classifier", "§6", S, "",
           "BLS · DOL/ETA · JOLTS",
           "Payrolls against claims, JOLTS, wages and hours is not implemented."),
    Module("Growth nowcasting", "§7 · §32", S, "",
           "PMI · ISM · freight · claims · tax receipts",
           "Must be built point-in-time: no look-ahead from later releases."),
    Module("Fiscal policy engine", "§8", S, "", "CBO · Treasury statements",
           "Fiscal impulse and its rates/FX transmission."),
    Module("Treasury auction analytics", "§9 (auction layer)", S, "",
           "TreasuryDirect results",
           "Bid-to-cover, tail vs when-issued, indirect take-down."),
    Module("Market-implied policy pricing", "§17", S, "",
           "OIS · fed funds · SOFR futures",
           "The single highest-value missing input: without it, 'what is priced' "
           "stays UNKNOWN everywhere."),
    Module("Positioning engine", "§18", S, "", "CFTC COT · ETF flows",
           "Separates a fundamental signal from a crowded one."),
    Module("Derivatives & liquidation radar", "§25 · §26", S, "",
           "Options chain · OI · funding",
           "Requires a chain no free public endpoint supplies."),
    Module("Energy intelligence", "§13", S, "", "EIA · IEA · OPEC",
           "Physical supply shock into inflation into rates."),
    Module("Commodity intelligence", "§14", S, "", "Exchange stocks · crop reports",
           "Metals and agriculture with inventory and weather."),
    Module("Central-bank consensus map", "§16", S, "", "Official calendars + speeches",
           "The stance / last stance / change / next-action structure does not exist "
           "as data."),
    Module("Geopolitical & early warning", "§11 · §35 · §48", S, "",
           "ACLED · SIPRI · government primaries",
           "Signal / confirmation / probability / impact, never weak signal to claim."),
    Module("Supply-chain & tariff", "§36 · §37", S, "",
           "Freight · Baltic · customs · WTO",
           "Inflationary supply shock before it reaches CPI."),
    Module("Crypto on-chain intelligence", "§20 – §24", S, "",
           "Glassnode · CryptoQuant · CoinGlass",
           "Network, supply, miners, stablecoins, ETF flow."),
    Module("Capital-flow map", "§40", S, "", "Treasury TIC · fund flows",
           "Where capital moves, not where price moves."),
    Module("Systemic-risk radar", "§38", S, "", "FDIC · CDS · spreads",
           "Banking, credit, sovereign and market legs into one score."),
    Module("Market reaction analyzer", "§34", S, "", "Live cross-asset tape",
           "Expected reaction against actual. A divergence outranks the headline — "
           "the highest-value output still missing."),
    Module("Narrative vs data", "§44", S, "", "Headline stream + macro series",
           "Tracks the live narrative against what the data says."),
    Module("Confluence scoring", "§52", S, "", "All engines populated",
           "Macro / fundamentals / liquidity / positioning / structure at 20 each."),
)


def counts() -> dict[str, int]:
    out = {s.value: 0 for s in Status}
    for m in MODULES:
        out[m.status.value] += 1
    out["TOTAL"] = len(MODULES)
    return out


# ---------------------------------------------------------------------------
# Static board content (verbatim from the specification)
# ---------------------------------------------------------------------------

TIERS = (
    ("a", "Tier 1", "Primary / official", "overrides everything below", (
        "Federal Reserve", "FOMC", "US Treasury", "BLS", "BEA", "Census", "CFTC",
        "SEC", "FDIC", "OCC", "OFAC", "EIA", "DoE", "ECB", "Eurostat",
        "European Commission", "ESMA", "EBA", "BoE", "BoJ", "SNB", "PBoC",
        "BoC", "RBA", "RBNZ", "Riksbank", "Norges Bank", "RBI", "BCB", "Banxico",
        "BIS", "IMF", "World Bank")),
    ("b", "Tier 2", "Institutional press", "speed and context, never override", (
        "Reuters", "Bloomberg", "Financial Times", "WSJ", "Dow Jones", "AP",
        "CNBC", "Nikkei Asia", "The Economist")),
    ("c", "Tier 3", "Professional commentary", "named and attributable", (
        "Sell-side economists", "Strategists", "Credible financial journalists")),
    ("d", "Tier 4", "Social / alternative", "never treated as confirmed", (
        "X", "Telegram", "Reddit", "Blogs", "Anonymous accounts")),
)

WEIGHTS = (("Market impact", 0.36), ("Surprise", 0.26), ("Expected volatility", 0.18),
           ("Information latency", 0.10), ("Directional conf.", 0.10))

REGIMES = (
    ("Monetary", "Fed-driven · ECB-driven · liquidity-driven"),
    ("Inflation", "Deflation · disinflation · inflation · stagflation"),
    ("Growth", "Expansion · slowdown · recession"),
    ("Liquidity", "Expansion · contraction · stress"),
    ("Geopolitical", "Stable · elevated · crisis"),
    ("Volatility", "Low · normal · high · extreme"),
)

BANKS = (
    ("Federal Reserve", "federalreserve.gov"), ("ECB", "ecb.europa.eu"),
    ("Bank of England", "bankofengland.co.uk"), ("Bank of Japan", "boj.or.jp"),
    ("SNB", "snb.ch"), ("Bank of Canada", "bankofcanada.ca"),
    ("RBA", "rba.gov.au"), ("RBNZ", "rbnz.govt.nz"), ("PBoC", "pbc.gov.cn"),
    ("Riksbank", "riksbank.se"), ("Norges Bank", "norges-bank.no"),
    ("RBI", "rbi.org.in"), ("Banco Central do Brasil", "bcb.gov.br"),
    ("Banxico", "banxico.org.mx"),
)

FEEDS = (
    ("US macro", "BLS · BEA · Census", "Primary data"),
    ("Monetary policy", "Federal Reserve / FOMC", "Rates + speeches"),
    ("Europe", "ECB · Eurostat", "Macro + policy"),
    ("Global macro", "IMF · World Bank · BIS", "System level"),
    ("Global liquidity", "BIS", "Cross-border credit"),
    ("Treasury flows", "US Treasury TIC", "Foreign capital"),
    ("Energy", "EIA · IEA · OPEC", "Physical market"),
    ("Positioning", "CFTC", "Futures positioning"),
    ("Geopolitics", "UN · NATO · governments", "Primary confirmation"),
    ("Conflict", "ACLED", "Near-real-time events"),
    ("Military", "SIPRI", "Arms + expenditure"),
    ("Crypto on-chain", "Glassnode · CryptoQuant", "Network + supply"),
    ("Crypto derivatives", "CoinGlass · Kaiko", "OI · funding · liquidations"),
    ("Breaking news", "Reuters · Bloomberg · FT", "Speed + context"),
    ("Deep research", "IMF · BIS · central banks", "Analysis"),
)

CHAIN = ("Event", "Supply", "Commodity", "Inflation", "Central bank",
         "Rates", "FX", "Equities", "Credit", "Crypto")

TAPE = ("CPI", "PCE", "NFP", "UST 10Y", "DXY", "BRENT", "GOLD", "BTC", "HY OAS", "VIX")

STANDARD = (
    ("f", "Fact", "Directly verified against the issuing institution's own document."),
    ("d", "Data", "Quantitative observation with a unit, a timestamp and a source."),
    ("a", "Analysis", "Interpretation of fact and data. Carries a confidence."),
    ("i", "Inference", "System-generated conclusion. Never given the weight of a fact."),
    ("s", "Scenario", "Conditional outcome with an explicit trigger and invalidation."),
    ("r", "Rumor", "Unverified. Labelled, quarantined, excluded from any decision."),
)

LADDER = ("Primary data", "Verified news", "Market pricing", "Positioning",
          "Cross-asset confirm", "On-chain / flow", "Market structure", "Trade")

GATE = ("Catalyst exists", "Structure confirms", "Liquidity target identified",
        "Invalidation is clear", "R:R ≥ 3R net of costs", "Risk ≤ 1% of equity",
        "No conflicting catalyst")

COMMANDS = (
    ("WHAT MATTERS", "Top five developments only. What changed, why it matters, "
     "what is priced, what is not, next catalyst.", "built"),
    ("BEFORE THE MARKET", "Next 24h ranked by probability × impact: releases, "
     "speeches, auctions, expiries, unscheduled risk.", "built"),
    ("PRE-EVENT", "T−60m / T−30m / T−15m expectation map / T−5m execution map.", "built"),
    ("WHY IS PRICE MOVING", "Ranks probable causes across news, rates, positioning, "
     "liquidity and structure.", "partial"),
    ("REACTION CHECK", "Expected reaction against actual. A divergence outranks the "
     "headline that caused it.", "spec"),
    ("EARLY WARNING", "Credible, evidenced, not yet mainstream. Never manufactured — "
     "an empty result is a valid result.", "spec"),
)

MASTER = (
    "What did the market believe before this arrived?",
    "What new information actually arrived?",
    "How much does it move the distribution of outcomes?",
    "What <em>should</em> react, on theory?",
    "What <em class=\"hit\">did</em> react?",
    "Where is positioning vulnerable?",
    "Where is liquidity concentrated?",
    "What is already priced?",
    "What remains unpriced?",
    "What is the next confirmation signal?",
    "What would invalidate the thesis?",
)

INTEGRITY = (
    ("Source reliability", "UNSCORED"), ("Primary confirmation", "NO"),
    ("Independent confirmation", "NO"), ("Conflicting reports", "NONE INGESTED"),
    ("Information age", "N/A"), ("Propaganda risk", "UNASSESSED"),
    ("Market relevance", "UNSCORED"), ("Confidence", "0 / 100"),
)


def e(x: object) -> str:
    return html.escape(str(x), quote=True)


# ---------------------------------------------------------------------------

CSS = r"""
:root{
  --ink:#070A12;--ink-2:#0A0F1A;--panel:#0E1421;--panel-2:#111826;
  --line:#1B2536;--line-hi:#27364C;
  --amber:#F2A93B;--amber-dim:#8A6524;
  --cyan:#3FC7C0;--cyan-dim:#1F6B68;
  --crimson:#E2565F;--crimson-dim:#7A2E33;
  --violet:#8B7CBD;--violet-dim:#41386B;
  --txt:#C8D2E0;--txt-2:#93A1B5;--mute:#61708A;--faint:#3D4A5F;
  --mono:"IBM Plex Mono",ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
  --sans:"IBM Plex Sans",system-ui,-apple-system,"Segoe UI",sans-serif;
  --disp:"Archivo","Archivo Narrow",system-ui,sans-serif;
  --gap:14px;
}
*{box-sizing:border-box}
html{background:var(--ink)}
body{margin:0;background:var(--ink);color:var(--txt);font-family:var(--sans);
  font-size:13px;line-height:1.5;-webkit-font-smoothing:antialiased;overflow-x:hidden}
img{max-width:100%}
[hidden]{display:none!important}
#bg{position:fixed;inset:0;z-index:0;display:block;pointer-events:none}
.wash{position:fixed;inset:0;z-index:1;pointer-events:none;
  background:
    radial-gradient(1100px 620px at 12% -8%, rgba(242,169,59,.075), transparent 62%),
    radial-gradient(900px 520px at 92% 4%, rgba(63,199,192,.055), transparent 60%),
    radial-gradient(1200px 800px at 50% 118%, rgba(139,124,189,.055), transparent 65%);}
.shell{position:relative;z-index:2}

.mast{border-bottom:1px solid var(--line-hi);
  background:linear-gradient(180deg,rgba(14,20,33,.97),rgba(7,10,18,.93));
  padding:14px 20px 0}
.mast-top{display:flex;align-items:flex-end;justify-content:space-between;gap:20px;
  flex-wrap:wrap;max-width:1560px;margin:0 auto}
.brand{display:flex;align-items:baseline;gap:14px;flex-wrap:wrap;min-width:0}
.brand h1{font-family:var(--disp);font-weight:800;font-size:26px;letter-spacing:-.02em;
  margin:0;color:var(--amber);text-transform:uppercase;text-wrap:balance}
.brand .sub{font-family:var(--mono);font-size:10.5px;letter-spacing:.19em;
  text-transform:uppercase;color:var(--mute)}
.mast-meta{display:flex;gap:26px;font-family:var(--mono);font-size:10.5px;
  letter-spacing:.11em;text-transform:uppercase;text-align:right;flex-wrap:wrap}
.mast-meta div span{display:block;color:var(--faint);font-size:9px;letter-spacing:.2em;
  margin-bottom:2px}
.mast-meta div b{font-weight:500;color:var(--txt-2);font-variant-numeric:tabular-nums;
  white-space:nowrap}
.tapebar{max-width:1560px;margin:12px auto 0;display:flex;overflow:hidden;
  border-top:1px solid var(--line)}
.tapebar .cell{flex:1 1 0;min-width:0;padding:9px 12px;border-right:1px solid var(--line);
  font-family:var(--mono);font-size:10px;letter-spacing:.13em;text-transform:uppercase;
  display:flex;align-items:center;gap:8px;color:var(--mute);white-space:nowrap;
  overflow:hidden;text-overflow:ellipsis}
.tapebar .cell:last-child{border-right:0}
.tapebar .cell b{color:var(--violet);font-weight:500}

main{max-width:1560px;margin:0 auto;padding:var(--gap) 20px 60px;
  display:grid;grid-template-columns:repeat(12,minmax(0,1fr));gap:var(--gap);
  align-items:start}
.p{border:1px solid var(--line);background:var(--panel);border-radius:2px;
  display:flex;flex-direction:column;min-width:0;
  animation:rise .5s cubic-bezier(.2,.7,.3,1) both}
.p:nth-child(1){animation-delay:.02s}.p:nth-child(2){animation-delay:.05s}
.p:nth-child(3){animation-delay:.08s}.p:nth-child(4){animation-delay:.11s}
.p:nth-child(5){animation-delay:.14s}.p:nth-child(6){animation-delay:.17s}
.p:nth-child(7){animation-delay:.20s}.p:nth-child(8){animation-delay:.23s}
.p:nth-child(9){animation-delay:.26s}.p:nth-child(n+10){animation-delay:.29s}
@keyframes rise{from{opacity:0;transform:translateY(7px)}to{opacity:1;transform:none}}
.p>h2{margin:0;padding:8px 12px;border-bottom:1px solid var(--line);
  background:var(--panel-2);font-family:var(--mono);font-weight:600;font-size:10.5px;
  letter-spacing:.17em;text-transform:uppercase;color:var(--txt-2);
  display:flex;align-items:baseline;justify-content:space-between;gap:6px 12px;
  flex-wrap:wrap;min-width:0}
/* The spec label must yield before the panel does: flex:none made it push the
   header past the viewport on narrow screens. */
.p>h2 .sec{color:var(--faint);font-weight:400;letter-spacing:.12em;
  flex:0 1 auto;min-width:0;text-align:right;overflow-wrap:anywhere}
.p .body{padding:12px;display:flex;flex-direction:column;gap:10px;min-width:0}
.p .body>*{min-width:0}
.p .body.tight{padding:0}
.c12{grid-column:span 12}.c8{grid-column:span 8}.c7{grid-column:span 7}
.c6{grid-column:span 6}.c5{grid-column:span 5}.c4{grid-column:span 4}.c3{grid-column:span 3}
@media(max-width:1180px){.c8,.c7,.c6,.c5{grid-column:span 12}.c4,.c3{grid-column:span 6}}
@media(max-width:660px){.c4,.c3{grid-column:span 12}main{padding:var(--gap) 12px 48px}
  .brand h1{font-size:20px}
  .mast-meta{gap:10px 14px;text-align:left;font-size:9.5px}
  .mast{padding:12px 12px 0}
  /* show every ticker by scrolling rather than clipping seven of ten away */
  .tapebar{overflow-x:auto;-webkit-overflow-scrolling:touch}
  .tapebar .cell{flex:0 0 auto}
  .p>h2 .sec{font-size:9.5px}}

.lamp{width:7px;height:7px;border-radius:50%;flex:none;display:inline-block;
  background:var(--violet);box-shadow:0 0 0 2px rgba(139,124,189,.14)}
.lamp.built{background:var(--cyan);box-shadow:0 0 0 2px rgba(63,199,192,.14);
  animation:breathe 3.4s ease-in-out infinite}
.lamp.partial{background:var(--amber);box-shadow:0 0 0 2px rgba(242,169,59,.14)}
.lamp.spec{background:var(--violet-dim);box-shadow:0 0 0 2px rgba(139,124,189,.09)}
@keyframes breathe{0%,100%{opacity:1}50%{opacity:.42}}

.tag{font-family:var(--mono);font-size:9px;letter-spacing:.14em;text-transform:uppercase;
  padding:2px 6px;border-radius:2px;border:1px solid;white-space:nowrap;flex:none;
  display:inline-block}
.tag.unfed{color:var(--violet);border-color:var(--violet-dim);background:rgba(139,124,189,.07)}
.tag.built{color:var(--cyan);border-color:var(--cyan-dim);background:rgba(63,199,192,.07)}
.tag.partial{color:var(--amber);border-color:var(--amber-dim);background:rgba(242,169,59,.07)}
.tag.spec{color:var(--mute);border-color:var(--line-hi);background:rgba(97,112,138,.06)}
.tag.t1{color:var(--cyan);border-color:var(--cyan-dim);background:rgba(63,199,192,.07)}
.tag.t2{color:var(--amber);border-color:var(--amber-dim);background:rgba(242,169,59,.07)}
.tag.t3{color:var(--txt-2);border-color:var(--line-hi);background:rgba(147,161,181,.06)}
.tag.t4{color:var(--crimson);border-color:var(--crimson-dim);background:rgba(226,86,95,.07)}

.note{font-size:11.5px;line-height:1.55;color:var(--mute);
  border-left:2px solid var(--line-hi);padding-left:9px;margin:0}
.note b{color:var(--txt-2);font-weight:500}

table{width:100%;border-collapse:collapse;font-family:var(--mono);font-size:11px}
th{text-align:left;font-weight:400;font-size:9px;letter-spacing:.15em;text-transform:uppercase;
  color:var(--faint);padding:7px 12px;border-bottom:1px solid var(--line);
  position:sticky;top:0;background:var(--panel);z-index:1}
td{padding:6px 12px;border-bottom:1px solid rgba(27,37,54,.6);vertical-align:top;color:var(--txt-2)}
tr:last-child td{border-bottom:0}
tbody tr:hover td{background:rgba(39,54,76,.26)}
td.k{color:var(--txt);font-weight:500}
td.u{color:var(--violet)}
.scroll{overflow:auto;min-width:0;max-width:100%;max-height:340px}
.scroll::-webkit-scrollbar{width:8px;height:8px}
.scroll::-webkit-scrollbar-thumb{background:var(--line-hi);border-radius:4px}
.scroll::-webkit-scrollbar-track{background:transparent}

.tier{border-left:3px solid;padding:9px 0 9px 11px;display:flex;flex-direction:column;gap:5px}
.tier.a{border-color:var(--cyan)}.tier.b{border-color:var(--amber)}
.tier.c{border-color:var(--txt-2)}.tier.d{border-color:var(--crimson)}
.tier-h{display:flex;align-items:baseline;gap:9px;flex-wrap:wrap}
.tier-h strong{font-family:var(--mono);font-size:11px;letter-spacing:.13em;
  text-transform:uppercase;color:var(--txt);font-weight:600}
.tier-h em{font-style:normal;font-size:11px;color:var(--mute)}
.orgs{display:flex;flex-wrap:wrap;gap:4px}
.orgs span{font-family:var(--mono);font-size:9.5px;color:var(--txt-2);
  border:1px solid var(--line);padding:1px 5px;border-radius:2px;background:var(--ink-2)}
.tier.d .orgs span{color:var(--mute)}

.rack{display:flex;flex-direction:column}
.mod{display:grid;grid-template-columns:14px minmax(0,1fr) auto;gap:9px;align-items:center;
  padding:7px 12px;border-bottom:1px solid rgba(27,37,54,.6)}
.rack .mod:last-child{border-bottom:0}
.mod:hover{background:rgba(39,54,76,.26)}
.mod .nm{min-width:0}
.mod .nm b{display:block;font-family:var(--mono);font-size:11px;font-weight:500;
  color:var(--txt);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.mod .nm i{font-style:normal;font-size:10px;color:var(--mute);font-family:var(--mono);
  display:block;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.mod .st{display:flex;gap:5px;flex:none}

.wrow{display:grid;grid-template-columns:126px minmax(0,1fr) 42px;gap:10px;align-items:center}
.wrow .lb{font-family:var(--mono);font-size:10px;letter-spacing:.06em;color:var(--txt-2);
  text-transform:uppercase}
.wtrack{display:block;height:9px;background:var(--ink-2);border:1px solid var(--line);
  border-radius:2px;overflow:hidden}
.wfill{display:block;height:100%;background:var(--amber);border-radius:0 2px 2px 0;
  transform-origin:left center;animation:grow .85s cubic-bezier(.2,.75,.3,1) both .35s}
.wrow .vv{font-family:var(--mono);font-size:10.5px;color:var(--amber);text-align:right;
  font-variant-numeric:tabular-nums}
@keyframes grow{from{transform:scaleX(0)}to{transform:scaleX(1)}}

.ladder{display:flex;flex-direction:column}
.rung{display:grid;grid-template-columns:26px minmax(0,1fr);gap:10px;align-items:center;
  padding:7px 0;border-bottom:1px dashed rgba(27,37,54,.85)}
.rung:last-child{border-bottom:0}
.rung .idx{font-family:var(--mono);font-size:10px;color:var(--faint);
  border:1px solid var(--line);border-radius:2px;text-align:center;padding:1px 0}
.rung .lbl{font-family:var(--mono);font-size:11px;letter-spacing:.08em;color:var(--txt-2);
  text-transform:uppercase}
.rung.last .idx{border-color:var(--amber-dim);color:var(--amber)}
.rung.last .lbl{color:var(--amber)}

.chips{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:8px}
.chip{border:1px solid var(--line);border-top:2px solid;border-radius:2px;padding:8px 9px;
  background:var(--ink-2)}
.chip h4{margin:0 0 3px;font-family:var(--mono);font-size:10px;letter-spacing:.16em;
  text-transform:uppercase;font-weight:600}
.chip p{margin:0;font-size:11px;color:var(--mute);line-height:1.45}
.chip.f{border-top-color:var(--cyan)}.chip.f h4{color:var(--cyan)}
.chip.d{border-top-color:#7FB3E8}.chip.d h4{color:#7FB3E8}
.chip.a{border-top-color:var(--amber)}.chip.a h4{color:var(--amber)}
.chip.i{border-top-color:var(--violet)}.chip.i h4{color:var(--violet)}
.chip.s{border-top-color:#B08BD6}.chip.s h4{color:#B08BD6}
.chip.r{border-top-color:var(--crimson)}.chip.r h4{color:var(--crimson)}

.cmds{display:flex;flex-direction:column;gap:7px}
.cmd{border:1px solid var(--line);border-radius:2px;background:var(--ink-2);
  padding:8px 10px;display:grid;grid-template-columns:minmax(0,1fr) auto;gap:6px 10px;
  transition:border-color .18s ease,background .18s ease}
.cmd:hover{border-color:var(--amber-dim);background:rgba(242,169,59,.045)}
.cmd .key{font-family:var(--mono);font-size:10.5px;font-weight:600;color:var(--amber);
  letter-spacing:.1em}
.cmd .desc{grid-column:1/-1;font-size:11.5px;color:var(--mute);line-height:1.45}

.regime{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:9px}
@media(max-width:900px){.regime{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:520px){.regime{grid-template-columns:1fr}}
.rg{border:1px solid var(--line);border-radius:2px;padding:9px 10px;background:var(--ink-2)}
.rg .rh{font-family:var(--mono);font-size:9.5px;letter-spacing:.17em;text-transform:uppercase;
  color:var(--faint);margin-bottom:6px}
.rg .rv{font-family:var(--mono);font-size:12px;letter-spacing:.09em;color:var(--violet);
  font-weight:500;margin-bottom:7px}
.states{display:flex;flex-wrap:wrap;gap:3px}
.states span{font-family:var(--mono);font-size:9px;color:var(--faint);
  border:1px solid rgba(27,37,54,.9);padding:1px 4px;border-radius:2px}

.fields{display:grid;grid-template-columns:minmax(0,1fr) auto}
.fn{font-family:var(--mono);font-size:10.5px;letter-spacing:.1em;text-transform:uppercase;
  color:var(--txt-2);padding:6px 0;border-bottom:1px solid rgba(27,37,54,.6)}
.fv{font-family:var(--mono);font-size:10.5px;color:var(--violet);text-align:right;
  padding:6px 0 6px 12px;border-bottom:1px solid rgba(27,37,54,.6)}

.gate{display:flex;flex-direction:column}
.gcond{display:grid;grid-template-columns:16px minmax(0,1fr) auto;gap:9px;align-items:center;
  font-family:var(--mono);font-size:11px;color:var(--txt-2);padding:5px 0;
  border-bottom:1px solid rgba(27,37,54,.55)}
.gcond:last-of-type{border-bottom:0}
.gcond .bx{width:12px;height:12px;border:1px solid var(--line-hi);border-radius:2px;
  background:var(--ink-2)}
.gcond .st{font-size:9.5px;letter-spacing:.13em;color:var(--violet)}
.verdict{margin-top:8px;border:1px solid var(--crimson-dim);background:rgba(226,86,95,.075);
  border-radius:2px;padding:10px;text-align:center}
.verdict b{display:block;font-family:var(--disp);font-weight:800;font-size:18px;
  letter-spacing:.06em;color:var(--crimson);text-transform:uppercase}
.verdict span{font-family:var(--mono);font-size:10px;letter-spacing:.1em;color:var(--mute)}

.flowwrap{overflow-x:auto;overflow-y:hidden;min-width:0;max-width:100%;
  padding:4px 0 2px;-webkit-overflow-scrolling:touch}
.flow{display:block;min-width:1130px;height:auto}
.dash{stroke-dasharray:5 9;animation:travel 2.6s linear infinite}
@keyframes travel{to{stroke-dashoffset:-56}}

.mq{margin:0;padding-left:18px;display:flex;flex-direction:column;gap:5px;font-size:12px;
  color:var(--txt-2);line-height:1.5}
.mq em{font-style:normal;color:var(--txt)}
.mq em.hit{color:var(--amber)}

.legend{display:flex;flex-direction:column;gap:7px;border-left:1px solid var(--line);
  padding-left:20px}
.legend .lh{font-family:var(--mono);font-size:9.5px;letter-spacing:.18em;
  text-transform:uppercase;color:var(--faint);margin-bottom:1px}
.legend .row{display:flex;align-items:center;gap:9px}
.legend .row span:last-child{font-family:var(--mono);font-size:11px;color:var(--txt-2)}
.legend .tag{width:56px;text-align:center}
.thesis{display:grid;grid-template-columns:minmax(0,1.55fr) minmax(0,1fr);gap:26px;
  align-items:start}
@media(max-width:900px){
  .thesis{grid-template-columns:1fr;gap:16px}
  .legend{border-left:0;padding-left:0;border-top:1px solid var(--line);padding-top:12px}
}
.thesis p{margin:0;font-size:14px;line-height:1.65;color:var(--txt)}
.thesis .hl{color:var(--amber);font-weight:600}
.thesis .un{color:var(--violet);font-family:var(--mono);font-size:12.5px;letter-spacing:.08em}

footer{max-width:1560px;margin:0 auto;padding:20px;border-top:1px solid var(--line);
  color:var(--mute);font-size:11.5px;line-height:1.6}
footer strong{color:var(--txt-2);font-weight:500}
footer code{font-family:var(--mono);font-size:10.5px;color:var(--amber)}
:focus-visible{outline:2px solid var(--amber);outline-offset:2px}
noscript .ns{display:block;margin:var(--gap) 20px;padding:12px;border:1px solid var(--amber-dim);
  background:rgba(242,169,59,.07);color:var(--amber);font-family:var(--mono);font-size:11.5px;
  border-radius:2px}
@media(prefers-reduced-motion:reduce){
  *,*::before,*::after{animation-duration:.001ms!important;animation-iteration-count:1!important;
    transition-duration:.001ms!important}
}
"""

JS = r"""
(function(){
"use strict";
var D=window.__BOARD__;
function e(s){return String(s).replace(/[&<>"]/g,function(c){
  return {"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c];});}
function q(id){return document.getElementById(id);}
/* Every DOM write goes through these. A missing node must degrade one panel,
   never abort the script and take the rest of the board down with it. */
function setText(id,v){var el=q(id);if(el){el.textContent=v;}
  else if(window.console&&console.warn){console.warn("board: missing #"+id);}}
function setHTML(id,v){var el=q(id);if(el){el.innerHTML=v;}
  else if(window.console&&console.warn){console.warn("board: missing #"+id);}}

/* ---- engine rack: counts are derived here, never typed ---- */
var built=0,partial=0,spec=0;
setHTML("rack",D.modules.map(function(m){
  if(m.status==="BUILT")built++;else if(m.status==="PARTIAL")partial++;else spec++;
  var cls=m.status.toLowerCase();
  var where=m.module?m.module:"not implemented";
  return '<div class="mod" title="'+e(m.note)+'">'
    +'<span class="lamp '+cls+'" aria-hidden="true"></span>'
    +'<span class="nm"><b>'+e(m.name)+'</b><i>'+e(m.sections)+' &middot; '+e(where)
    +' &middot; needs '+e(m.feed)+'</i></span>'
    +'<span class="st"><span class="tag '+cls+'">'+e(m.status)+'</span>'
    +'<span class="tag unfed">Unfed</span></span></div>';
}).join(""));
setText("m-built",built+" built");
setText("m-partial",partial+" partial");
setText("m-spec",spec+" spec");
setText("rack-count",D.modules.length+" modules");
setText("feeds-live","0 of "+D.feeds.length);

/* ---- priority weights ---- */
var maxw=Math.max.apply(null,D.weights.map(function(w){return w[1];}));
setHTML("weights",D.weights.map(function(w,i){
  return '<div class="wrow"><span class="lb">'+e(w[0])+'</span>'
    +'<span class="wtrack"><span class="wfill" style="width:'
    +(w[1]/maxw*100).toFixed(1)+'%;animation-delay:'+(0.35+i*0.07).toFixed(2)+'s"></span></span>'
    +'<span class="vv">'+w[1].toFixed(2)+'</span></div>';
}).join(""));

/* ---- regimes ---- */
setHTML("regime",D.regimes.map(function(r){
  return '<div class="rg"><div class="rh">'+e(r[0])+' regime</div>'
    +'<div class="rv">UNDETERMINED</div><div class="states">'
    +r[1].split(" · ").map(function(x){return "<span>"+e(x)+"</span>";}).join("")
    +'</div></div>';
}).join(""));

/* ---- tables ---- */
setHTML("cbmap",D.banks.map(function(b){
  return '<tr><td class="k">'+e(b[0])+'</td><td class="u">UNFED</td>'
    +'<td class="u">&mdash;</td><td style="color:var(--mute)">'+e(b[1])+'</td></tr>';
}).join(""));
setHTML("feeds",D.feeds.map(function(f){
  return '<tr><td class="k">'+e(f[0])+'</td><td>'+e(f[1])+'</td>'
    +'<td style="color:var(--mute)">'+e(f[2])+'</td>'
    +'<td><span class="tag unfed">Not connected</span></td></tr>';
}).join(""));

/* ---- transmission chain ---- */
(function(){
  var n=D.chain.length,x0=24,x1=1106,step=(x1-x0)/(n-1),out="";
  for(var i=0;i<n;i++){
    var x=(x0+step*i).toFixed(1);
    var hue=i<2?"#E2565F":(i<6?"#F2A93B":"#3FC7C0");
    var idx=(i+1)<10?("0"+(i+1)):String(i+1);
    out+='<circle cx="'+x+'" cy="52" r="6.5" fill="#0E1421" stroke="'+hue+'" stroke-width="2"/>'
      +'<circle cx="'+x+'" cy="52" r="2.2" fill="'+hue+'"/>'
      +'<text x="'+x+'" y="82" text-anchor="middle" fill="#C8D2E0" font-family="IBM Plex Mono, monospace" font-size="10.5">'+e(D.chain[i])+'</text>'
      +'<text x="'+x+'" y="99" text-anchor="middle" fill="#3D4A5F" font-family="IBM Plex Mono, monospace" font-size="8.5" letter-spacing="1.2">'+idx+'</text>'
      +'<text x="'+x+'" y="28" text-anchor="middle" fill="#8B7CBD" font-family="IBM Plex Mono, monospace" font-size="8.5" letter-spacing="1">UNFED</text>';
  }
  setHTML("nodes",out);
})();

/* ---- clock ---- */
(function(){
  if(!q("clock"))return;
  function tick(){setText("clock",new Date().toISOString().slice(11,19)+"Z");}
  tick();setInterval(tick,1000);
})();

/* ---- ambient canvas: seamless parallax tape + CRT sweep ---- */
(function(){
  var c=q("bg");if(!c||!c.getContext)return;
  var ctx=c.getContext("2d");if(!ctx)return;
  var reduce=window.matchMedia&&matchMedia("(prefers-reduced-motion: reduce)").matches;
  var W=0,H=0,dpr=1,layers=[],sweep=-0.25,N=280;

  /* Periodic sums of sinusoids with integer wavenumbers: the series is exactly
     cyclic over N, so rotating the ring scrolls it with no seam and no drain. */
  function makeLayer(seed,speed,alpha,hue){
    var pts=[],k=[3,7,13],a=[0.16,0.09,0.05];
    for(var i=0;i<N;i++){
      var y=0.5;
      for(var j=0;j<3;j++){y+=a[j]*Math.sin(2*Math.PI*k[j]*i/N+seed*(j+1));}
      pts.push(Math.max(0.06,Math.min(0.94,y)));
    }
    return {pts:pts,speed:speed,alpha:alpha,hue:hue,acc:0};
  }
  function resize(){
    dpr=Math.min(window.devicePixelRatio||1,2);
    W=c.width=Math.max(1,Math.floor(innerWidth*dpr));
    H=c.height=Math.max(1,Math.floor(innerHeight*dpr));
    c.style.width=innerWidth+"px";c.style.height=innerHeight+"px";
  }
  function drawLayer(L){
    var seg=W/(N-1),i,x,y;
    ctx.beginPath();
    for(i=0;i<=N;i++){
      x=(i-L.acc)*seg;y=L.pts[i%N]*H;
      if(i===0){ctx.moveTo(x,y);}
      else{ctx.lineTo(x,L.pts[(i-1)%N]*H);ctx.lineTo(x,y);}
    }
    ctx.strokeStyle=L.hue;ctx.globalAlpha=L.alpha;ctx.lineWidth=dpr;
    ctx.stroke();ctx.globalAlpha=1;
  }
  function frame(){
    ctx.clearRect(0,0,W,H);
    ctx.fillStyle="#070A12";ctx.fillRect(0,0,W,H);
    ctx.strokeStyle="rgba(27,37,54,0.55)";ctx.lineWidth=1;
    var gs=64*dpr,x,y;
    for(x=0;x<W;x+=gs){ctx.beginPath();ctx.moveTo(x,0);ctx.lineTo(x,H);ctx.stroke();}
    for(y=0;y<H;y+=gs){ctx.beginPath();ctx.moveTo(0,y);ctx.lineTo(W,y);ctx.stroke();}
    for(var i=0;i<layers.length;i++){
      var L=layers[i];
      if(!reduce){
        L.acc+=L.speed;
        while(L.acc>=1){L.pts.push(L.pts.shift());L.acc-=1;}
      }
      drawLayer(L);
    }
    if(!reduce){
      sweep+=0.0016;if(sweep>1.25)sweep=-0.25;
      var sx=sweep*W,g=ctx.createLinearGradient(sx-150*dpr,0,sx+18*dpr,0);
      g.addColorStop(0,"rgba(242,169,59,0)");
      g.addColorStop(0.82,"rgba(242,169,59,0.045)");
      g.addColorStop(1,"rgba(242,169,59,0.11)");
      ctx.fillStyle=g;ctx.fillRect(sx-150*dpr,0,168*dpr,H);
      ctx.fillStyle="rgba(242,169,59,0.16)";ctx.fillRect(sx,0,dpr,H);
      requestAnimationFrame(frame);
    }
  }
  layers=[makeLayer(1.3,0.055,0.16,"#F2A93B"),
          makeLayer(4.7,0.032,0.11,"#3FC7C0"),
          makeLayer(8.1,0.018,0.08,"#8B7CBD")];
  resize();frame();
  addEventListener("resize",function(){resize();if(reduce)frame();},{passive:true});
})();
})();
"""


def render(standalone: bool = True) -> str:
    """Render the board.

    ``standalone`` emits a complete HTML document for the repository. Setting it
    False emits page content only (title, styles, markup, scripts) for hosts that
    supply their own document skeleton.
    """
    c = counts()

    tape = "".join(
        f'<div class="cell">{e(t)} <b>UNFED</b></div>' for t in TAPE
    )

    tiers = "".join(
        f'<div class="tier {cls}"><div class="tier-h">'
        f'<span class="tag t{cls_i}">{e(label)}</span><strong>{e(name)}</strong>'
        f'<em>{e(rule)}</em></div><div class="orgs">'
        + "".join(f"<span>{e(o)}</span>" for o in orgs)
        + "</div></div>"
        for cls_i, (cls, label, name, rule, orgs) in enumerate(TIERS, start=1)
    )

    ladder = "".join(
        f'<div class="rung{" last" if i == len(LADDER) else ""}">'
        f'<span class="idx">{i:02d}</span><span class="lbl">{e(x)}</span></div>'
        for i, x in enumerate(LADDER, start=1)
    )

    gate = "".join(
        f'<div class="gcond"><span class="bx"></span><span>{e(g)}</span>'
        f'<span class="st">UNMET</span></div>' for g in GATE
    )

    chips = "".join(
        f'<div class="chip {cls}"><h4>{e(name)}</h4><p>{e(desc)}</p></div>'
        for cls, name, desc in STANDARD
    )

    cmds = "".join(
        f'<div class="cmd"><span class="key">{e(k)}</span>'
        f'<span class="tag {st}">{st}</span>'
        f'<span class="desc">{e(d)}</span></div>'
        for k, d, st in COMMANDS
    )

    integrity = "".join(
        f'<div class="fn">{e(k)}</div><div class="fv">{e(v)}</div>'
        for k, v in INTEGRITY
    )

    master = "".join(f"<li>{m}</li>" for m in MASTER)

    payload = json.dumps({
        "modules": [
            {"name": m.name, "sections": m.sections, "status": m.status.value,
             "module": m.module, "feed": m.feed, "note": m.note}
            for m in MODULES
        ],
        "weights": [[w[0], w[1]] for w in WEIGHTS],
        "regimes": [[r[0], r[1]] for r in REGIMES],
        "banks": [[b[0], b[1]] for b in BANKS],
        "feeds": [[f[0], f[1], f[2]] for f in FEEDS],
        "chain": list(CHAIN),
    }, ensure_ascii=False).replace("</", "<\\/")

    head = f"""<title>Cold Start Terminal</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Archivo:wght@500;600;700;800&amp;family=IBM+Plex+Mono:wght@400;500;600&amp;family=IBM+Plex+Sans:wght@400;500&amp;display=swap">
<style>{CSS}</style>"""

    body = f"""<canvas id="bg" aria-hidden="true"></canvas>
<div class="wash" aria-hidden="true"></div>

<div class="shell">
<header class="mast">
  <div class="mast-top">
    <div class="brand">
      <h1>Cold Start Terminal</h1>
      <span class="sub">Institutional Market Intelligence &middot; Operating Board</span>
    </div>
    <div class="mast-meta">
      <div><span>Session UTC</span><b id="clock">--:--:--</b></div>
      <div><span>Modules</span><b><span id="m-built">&mdash;</span> / <span id="m-partial">&mdash;</span> / <span id="m-spec">&mdash;</span></b></div>
      <div><span>Feeds live</span><b style="color:var(--violet)" id="feeds-live">&mdash;</b></div>
      <div><span>State</span><b style="color:var(--amber)">COLD START</b></div>
    </div>
  </div>
  <div class="tapebar">{tape}</div>
</header>

<noscript><span class="ns">This board builds its module rack, tables and counts from an
embedded registry at load. Enable JavaScript to see them; the doctrine panels below render
without it.</span></noscript>

<main>

  <section class="p c12">
    <h2>Board state <span class="sec">§53 &middot; §54 information standard</span></h2>
    <div class="body">
      <div class="thesis">
        <p>Every value slot on this board reads <span class="un">UNFED</span> because no primary
        source is connected. That is the terminal working correctly, not failing. The governing
        rule &mdash; <span class="hl">primary data before verified news before market pricing</span>
        &mdash; makes an invented number strictly worse than a blank one. What the board shows
        instead is the wiring: which engines hold live logic, which are still specification, and
        exactly which institution's feed fills each gap. Module status is generated from the
        package registry, so this page cannot overstate what the system actually does.</p>
        <div class="legend">
          <div class="lh">Legend</div>
          <div class="row"><span class="lamp built"></span><span>Built &mdash; implemented and tested</span></div>
          <div class="row"><span class="lamp partial"></span><span>Partial &mdash; section incomplete</span></div>
          <div class="row"><span class="lamp spec"></span><span>Spec &mdash; not yet written</span></div>
          <div class="row"><span class="tag unfed">Unfed</span><span>No source connected</span></div>
          <div class="row"><span class="tag t1">Tier 1</span><span>Primary document, outranks all</span></div>
          <div class="row"><span class="tag t4">Tier 4</span><span>Never treated as confirmed</span></div>
        </div>
      </div>
    </div>
  </section>

  <section class="p c5">
    <h2>Source hierarchy <span class="sec">§1 &middot; §2</span></h2>
    <div class="body">
      {tiers}
      <p class="note"><b>Independence is counted by organisation, not by citation.</b>
      Twenty articles tracing to one original report is one information event (§43). A Tier-2 wire
      saying &ldquo;Reuters reports X&rdquo; is never promoted to &ldquo;X is confirmed&rdquo;
      without the Tier-1 document.</p>
    </div>
  </section>

  <section class="p c7">
    <h2>Engine rack <span class="sec"><span id="rack-count">&mdash;</span> &middot; logic vs feed</span></h2>
    <div class="body tight">
      <div class="scroll" style="max-height:470px"><div class="rack" id="rack"></div></div>
    </div>
  </section>

  <section class="p c12">
    <h2>Geopolitical transmission chain <span class="sec">§12 &middot; never report &ldquo;tensions increased&rdquo;</span></h2>
    <div class="body">
      <div class="flowwrap">
        <svg class="flow" viewBox="0 0 1130 112" role="img" aria-label="Transmission chain from event through supply, commodity, inflation, central bank, rates, FX, equities and credit to crypto">
          <defs><linearGradient id="wire" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0" stop-color="#E2565F"/><stop offset="0.42" stop-color="#F2A93B"/>
            <stop offset="1" stop-color="#3FC7C0"/></linearGradient></defs>
          <line x1="24" y1="52" x2="1106" y2="52" stroke="#1B2536" stroke-width="2" fill="none"/>
          <line x1="24" y1="52" x2="1106" y2="52" stroke="url(#wire)" stroke-width="2" fill="none" class="dash" opacity="0.95"/>
          <g id="nodes"></g>
        </svg>
      </div>
      <p class="note"><b>The chain is the output, not the headline.</b> A missile test is not a
      market event until it is priced through physical supply. If a link cannot be established
      &mdash; no affected supply, no commodity channel &mdash; the event scores high on attention
      and low on market relevance, and the board says so rather than manufacturing a narrative.</p>
    </div>
  </section>

  <section class="p c4">
    <h2>Priority score model <span class="sec">§45</span></h2>
    <div class="body">
      <div style="display:flex;flex-direction:column;gap:7px" id="weights"></div>
      <div style="border:1px solid var(--cyan-dim);background:rgba(63,199,192,.06);border-radius:2px;padding:9px 10px">
        <div style="font-family:var(--mono);font-size:9.5px;letter-spacing:.15em;text-transform:uppercase;color:var(--cyan);margin-bottom:4px">Credibility gate</div>
        <div style="font-family:var(--mono);font-size:11px;color:var(--txt-2)">priority = core &times; (0.25 + 0.75 &times; cred/100)</div>
        <p style="margin:6px 0 0;font-size:11px;color:var(--mute);line-height:1.45">Multiplicative,
        not additive. An unverifiable claim keeps at most a quarter of its raw score &mdash; so
        &ldquo;sources say emergency 100bp cut&rdquo; from an anonymous account cannot outrank a
        confirmed print.</p>
      </div>
      <p class="note">Novelty (§45) is handled by the duplicate filter; market sensitivity is folded
      into impact. Neither is yet a separate input.</p>
    </div>
  </section>

  <section class="p c8">
    <h2>Regime matrix <span class="sec">§39 &middot; §41 &middot; all six undetermined</span></h2>
    <div class="body">
      <div class="regime" id="regime"></div>
      <p class="note"><b>Regime decides the sign, not the data.</b> The same weak payroll is bought
      under a monetary-driven regime and sold under a growth-driven one. Until these six resolve,
      every directional cell in the cross-asset map returns
      <span style="color:var(--violet);font-family:var(--mono)">AMBIGUOUS</span> at zero confidence.</p>
    </div>
  </section>

  <section class="p c7">
    <h2>Central-bank consensus map <span class="sec">§15 &middot; §16 &middot; §17</span></h2>
    <div class="body tight">
      <div class="scroll"><table>
        <thead><tr><th style="width:23%">Bank</th><th style="width:22%">Stance</th>
        <th style="width:22%">&Delta; vs last</th><th style="width:33%">Primary source of record</th></tr></thead>
        <tbody id="cbmap"></tbody></table></div>
    </div>
  </section>

  <section class="p c5">
    <h2>Information integrity <span class="sec">§3 &middot; §4</span></h2>
    <div class="body">
      <div class="fields">{integrity}</div>
      <p class="note"><b>On conflict, the dramatic story never wins by default.</b> The engine emits
      <span style="color:var(--crimson);font-family:var(--mono);font-size:10.5px">CONFLICTING REPORTS &mdash; NOT CONFIRMED</span>,
      then separates confirmed facts from disputed claims and names the next confirmation point.</p>
    </div>
  </section>

  <section class="p c3">
    <h2>Golden rule <span class="sec">§54</span></h2>
    <div class="body">
      <div class="ladder">{ladder}</div>
      <p class="note">Numbering here is precedence, not decoration. A convincing narrative never
      reverses the order.</p>
    </div>
  </section>

  <section class="p c4">
    <h2>Trade gate <span class="sec">§51 &middot; §52</span></h2>
    <div class="body">
      <div class="gate">{gate}
        <div class="verdict"><b>No Trade</b><span>0 of {len(GATE)} conditions met</span></div>
      </div>
      <p class="note">The gate is implemented; the §52 confluence score (macro, fundamentals,
      liquidity, positioning, structure at 20 each) is not. Preference is 5R; 3R is the floor,
      measured after costs on both legs.</p>
    </div>
  </section>

  <section class="p c5">
    <h2>Master question <span class="sec">§55 &middot; asked of every event</span></h2>
    <div class="body">
      <ol class="mq">{master}</ol>
      <p class="note">Question 5 minus question 4 is the highest-value output the terminal produces
      &mdash; and the one engine still unbuilt (§34).</p>
    </div>
  </section>

  <section class="p c7">
    <h2>Feed registry <span class="sec">contracted sources &middot; connection state</span></h2>
    <div class="body tight">
      <div class="scroll" style="max-height:392px"><table>
        <thead><tr><th style="width:26%">Function</th><th style="width:34%">Source of record</th>
        <th style="width:22%">Role</th><th style="width:18%">State</th></tr></thead>
        <tbody id="feeds"></tbody></table></div>
    </div>
  </section>

  <section class="p c5">
    <h2>Callable functions <span class="sec">§47 &ndash; §50</span></h2>
    <div class="body"><div class="cmds">{cmds}</div></div>
  </section>

  <section class="p c12">
    <h2>Information standard <span class="sec">§53 &middot; these six never mix</span></h2>
    <div class="body"><div class="chips">{chips}</div></div>
  </section>

</main>

<footer>
  <strong>Reading this board.</strong> Cyan marks logic that exists and is tested, amber marks a
  section only partly implemented, violet marks a slot with no data behind it. The module rack and
  every count on this page are generated from the registry in <code>macro/board.py</code>, so the
  board cannot claim more than the package delivers. Nothing here is a market observation, a price,
  a forecast or investment advice &mdash; the terminal has no feeds attached, and states so rather
  than filling the gap. Total modules {c['TOTAL']}: {c['BUILT']} built, {c['PARTIAL']} partial,
  {c['SPEC']} specified.
</footer>
</div>

<script>window.__BOARD__={payload};</script>
<script>{JS}</script>"""

    if not standalone:
        return head + "\n" + body + "\n"
    return (
        "<!doctype html>\n<html lang=\"en\">\n<head>\n"
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width,initial-scale=1">\n'
        '<meta name="description" content="Institutional market intelligence '
        'architecture at cold start: every live slot marked UNFED with the primary '
        'source that would fill it.">\n'
        + head + "\n</head>\n<body>\n" + body + "\n</body>\n</html>\n"
    )


DOCTRINE = (
    ("Primary before press", "A Tier-2 wire reporting X is never promoted to X confirmed "
     "without the Tier-1 document. `Reuters reports X` and `the agency published X` are "
     "different claims and stay different."),
    ("Independence by organisation", "Twenty articles tracing to one original report is one "
     "information event, not twenty confirmations."),
    ("Credibility multiplies", "An unverifiable claim keeps at most a quarter of its raw "
     "priority. A loud anonymous claim cannot outrank a confirmed release."),
    ("Regime decides the sign", "The same surprise maps to opposite equity outcomes across "
     "regimes. With the regime unresolved the directional answer is AMBIGUOUS, not a guess."),
    ("Never name an unexplained cause", "A move without a headline yields weighted candidate "
     "explanations and a verification instruction, never an invented reason."),
    ("Latency is public detectability", "How early something can be seen in public sources. "
     "It is never a claim of embargoed, privileged or non-public access."),
    ("No trade beats a bad trade", "Catalyst, structure, liquidity target, invalidation and "
     ">=3R after costs, or the answer is NO TRADE."),
    ("Six categories never mix", "Fact, data, analysis, inference, scenario, rumor. Each is "
     "labelled; none is silently promoted."),
)


def render_markdown() -> str:
    """The architecture document, generated from the same registry as the board."""
    c = counts()
    rows = []
    for st in (Status.BUILT, Status.PARTIAL, Status.SPEC):
        for m in MODULES:
            if m.status is not st:
                continue
            where = f"`{m.module}`" if m.module else "&mdash;"
            rows.append(
                f"| {m.name} | {m.sections} | **{m.status.value}** | {where} | {m.feed} |"
            )
    table = "\n".join(rows)

    doctrine = "\n".join(f"**{h}.** {b}\n" for h, b in DOCTRINE)

    tiers = "\n".join(
        f"- **{label} &mdash; {name}** ({rule}): " + ", ".join(orgs)
        for _cls, label, name, rule, orgs in TIERS
    )

    feeds = "\n".join(
        f"| {f[0]} | {f[1]} | {f[2]} | not connected |" for f in FEEDS
    )

    chain = " -> ".join(CHAIN)

    return f"""# Institutional market intelligence terminal

The operating architecture behind the cold-start board
(`board/cold-start-terminal.html`, regenerate with `python -m macro board`).

This document and the board are both generated from one registry in
`macro/board.py`, so neither can claim more than the package delivers.

**{c['TOTAL']} modules: {c['BUILT']} built, {c['PARTIAL']} partial, {c['SPEC']} specified.**
Zero feeds are connected. Every value slot in the system reads UNKNOWN until a
primary source is attached, and that is the designed behaviour rather than a gap.

---

## Doctrine

{doctrine}
---

## Source hierarchy

{tiers}

Tier 4 is never treated as confirmed. Anything unverified is labelled
`UNCONFIRMED - REQUIRES VERIFICATION` and excluded from any trade decision.

---

## Geopolitical transmission

Never report that tensions increased. Translate:

```
{chain}
```

If a link cannot be established - no affected supply, no commodity channel - the
event scores high on attention and low on market relevance, and the system says
so rather than manufacturing a narrative.

---

## Module registry

| Module | Spec | Status | Implementation | Feed required |
|---|---|---|---|---|
{table}

`BUILT` means implemented in `macro/` and covered by `python -m macro selftest`.
`PARTIAL` means part of the specified section exists; it is not a softer word for
built. `SPEC` means defined here and not implemented.

---

## Feed registry

| Function | Source of record | Role | State |
|---|---|---|---|
{feeds}

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
"""


def main(out: str = "board/cold-start-terminal.html",
         doc_out: str = "docs/intelligence-terminal.md") -> int:
    import os

    def _write(path: str, text: str) -> int:
        os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        return len(text.encode("utf-8"))

    n_html = _write(out, render())
    n_md = _write(doc_out, render_markdown())
    frag = os.path.join(os.path.dirname(out) or ".", "board-fragment.html")
    _write(frag, render(standalone=False))
    c = counts()
    print(f"wrote {out} ({n_html:,} bytes)")
    print(f"wrote {doc_out} ({n_md:,} bytes)")
    print(f"{c['TOTAL']} modules: {c['BUILT']} built, {c['PARTIAL']} partial, "
          f"{c['SPEC']} spec | 0 of {len(FEEDS)} feeds connected")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
