"""Event-reaction matrix and second-order analysis (spec sections 8, 9, 27).

The matrix is *derived*, not tabulated.  Each cell is produced by walking a
transmission chain - shock -> policy path -> nominal yields -> real yields ->
discount rate / dollar / financial conditions -> asset - and each cell carries
the mechanism that produced it.  That is deliberate: a lookup table of
historical correlations breaks exactly when the regime changes, which is
precisely when the money is made and lost.

Where the chain genuinely does not identify a sign, the cell is AMBIGUOUS with
the reason.  A confident arrow in an ambiguous cell is worse than no arrow.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .regime import MacroRegime
from .surprise import Impulse
from .types import Category


class Direction(str, Enum):
    STRONG_UP = "UP UP"
    UP = "UP"
    MILD_UP = "up"
    FLAT = "~"
    MILD_DOWN = "dn"
    DOWN = "DOWN"
    STRONG_DOWN = "DOWN DOWN"
    AMBIGUOUS = "?"

    @property
    def arrow(self) -> str:
        return {
            Direction.STRONG_UP: "^^", Direction.UP: "^", Direction.MILD_UP: "+",
            Direction.FLAT: "=", Direction.MILD_DOWN: "-", Direction.DOWN: "v",
            Direction.STRONG_DOWN: "vv", Direction.AMBIGUOUS: "?",
        }[self]


ASSETS = (
    "USD (DXY)", "EURUSD", "USDJPY", "US 2Y", "US 10Y", "2s10s", "S&P 500",
    "Nasdaq 100", "Gold", "WTI Crude", "BTC", "HY credit", "VIX",
)


@dataclass(frozen=True)
class Cell:
    asset: str
    direction: Direction
    mechanism: str
    confidence: float          # 0..1, how well the chain identifies the sign
    caveat: str = ""

    def render(self) -> str:
        c = f" [{self.caveat}]" if self.caveat else ""
        return f"{self.asset:<12} {self.direction.arrow:<3} ({self.confidence:.2f}) {self.mechanism}{c}"


@dataclass(frozen=True)
class ReactionMap:
    scenario: str
    impulse: Impulse
    regime: MacroRegime
    cells: tuple[Cell, ...]
    chain: tuple[str, ...]
    category: Category = Category.SCENARIO
    ok: bool = True

    def by_asset(self, asset: str) -> Cell | None:
        return next((c for c in self.cells if c.asset == asset), None)

    def render(self) -> str:
        head = f"{self.scenario}  |  regime: {self.regime.value}"
        chain = "\n".join(f"  {i+1}. {s}" for i, s in enumerate(self.chain))
        body = "\n".join("  " + c.render() for c in self.cells)
        return f"{head}\nTRANSMISSION CHAIN\n{chain}\nCROSS-ASSET MAP\n{body}"


def _c(asset, d, mech, conf, caveat="") -> Cell:
    return Cell(asset, d, mech, conf, caveat)


def build_matrix(
    impulse: Impulse,
    regime: MacroRegime,
    *,
    magnitude: float = 1.0,
    scenario_label: str | None = None,
) -> ReactionMap:
    """Derive the cross-asset map for one impulse under one regime.

    ``magnitude`` (roughly, |z| of the surprise) scales conviction, not sign.
    """
    label = scenario_label or f"{impulse.value} under {regime.value}"
    strong = magnitude >= 1.5
    up_big = Direction.STRONG_UP if strong else Direction.UP
    dn_big = Direction.STRONG_DOWN if strong else Direction.DOWN

    if regime is MacroRegime.UNKNOWN:
        return ReactionMap(
            scenario=label, impulse=impulse, regime=regime,
            chain=("Regime is not established, so the sign of the equity and dollar "
                   "response is not identified. Establish the regime first.",),
            cells=tuple(
                _c(a, Direction.AMBIGUOUS,
                   "regime unknown: the same shock maps to opposite equity outcomes "
                   "under inflation-dominant vs growth-dominant conditions", 0.0)
                for a in ASSETS
            ),
        )

    if regime is MacroRegime.LIQUIDITY_DOMINANT:
        return _liquidity_dominant(label, impulse, regime, up_big, dn_big)

    if impulse in (Impulse.INFLATION_HOTTER, Impulse.INFLATION_COOLER):
        return _inflation(label, impulse, regime, magnitude)
    if impulse in (Impulse.GROWTH_STRONGER, Impulse.GROWTH_WEAKER):
        return _growth(label, impulse, regime, magnitude)

    return ReactionMap(
        scenario=label, impulse=impulse, regime=regime,
        chain=("No material impulse: nothing in the policy path should change.",),
        cells=tuple(
            _c(a, Direction.FLAT, "in line with expectations; already priced", 0.4)
            for a in ASSETS
        ),
    )


def _inflation(label, impulse, regime, magnitude) -> ReactionMap:
    hot = impulse is Impulse.INFLATION_HOTTER
    s = 1 if hot else -1
    strong = magnitude >= 1.5

    def d(up: bool, big: bool = False) -> Direction:
        if up:
            return Direction.STRONG_UP if (big and strong) else Direction.UP
        return Direction.STRONG_DOWN if (big and strong) else Direction.DOWN

    chain = (
        f"Inflation impulse is {'hotter' if hot else 'cooler'} than the market's "
        "expectation, so the expected policy path shifts "
        f"{'higher/later' if hot else 'lower/sooner'}.",
        "The front end reprices first: the 2y is the cleanest expression of the "
        "policy path, so it moves more than the 10y - a bear flattening if hot, "
        "bull steepening if cool.",
        "Nominal 10y moves less than the 2y, and the real 10y is what transmits: "
        "if breakevens absorb part of the move, real yields move by less than "
        "nominals and the equity/gold response is muted.",
        "Higher real yields raise the discount rate on long-duration cash flows "
        "and widen rate differentials in favour of the dollar.",
        "Tighter financial conditions feed back into credit spreads and into the "
        "liquidity channel that crypto trades off.",
    )

    cells = (
        _c("USD (DXY)", d(hot), "rate differential widens in the dollar's favour as "
           "the front end reprices", 0.72),
        _c("EURUSD", d(not hot), "the mirror of the dollar leg, unless the shock is "
           "euro-area rather than US in origin", 0.68,
           "invert if the release is European"),
        _c("USDJPY", d(hot), "the most rate-differential-sensitive major; JPY is the "
           "funding leg", 0.70,
           "intervention risk truncates the upside near policy-sensitive levels"),
        _c("US 2Y", d(hot, True), "direct repricing of the policy path", 0.88),
        _c("US 10Y", d(hot), "follows the front end but by less; term premium and "
           "supply also drive it", 0.75),
        _c("2s10s", d(not hot), "bear flattening on a hot print, bull steepening on a "
           "cool one - the front end does more of the work", 0.72),
        _c("S&P 500", d(not hot), "higher real discount rate compresses multiples; in "
           "an inflation-dominant regime equities and bonds sell off together", 0.66
           if regime is MacroRegime.INFLATION_DOMINANT else 0.5,
           "" if regime is MacroRegime.INFLATION_DOMINANT else
           "weaker in a growth-dominant regime, where earnings dominate the discount rate"),
        _c("Nasdaq 100", d(not hot, True), "longest duration equity index: highest "
           "sensitivity to the real-rate leg", 0.68),
        _c("Gold", d(not hot), "real yields are the dominant driver of the gold carry "
           "cost", 0.55,
           "breaks down when gold is bid as an inflation or sovereign-risk hedge "
           "rather than a real-rate asset - check whether real yields or breakevens "
           "moved"),
        _c("WTI Crude", Direction.AMBIGUOUS, "oil is an input to the inflation print "
           "as much as a response to it; the sign depends on whether energy drove "
           "the surprise", 0.25,
           "decompose the release: energy-led vs services-led changes the answer"),
        _c("BTC", d(not hot), "trades the dollar-liquidity and real-rate channel; "
           "beta to Nasdaq is high but unstable", 0.45,
           "idiosyncratic flow (ETF creations, liquidations, protocol events) "
           "regularly overwhelms the macro signal"),
        _c("HY credit", d(not hot), "tighter financial conditions widen spreads; the "
           "response lags equities by hours to days", 0.55),
        _c("VIX", d(hot), "repricing of the policy path raises realised and implied "
           "equity vol", 0.6,
           "if the print merely confirms what was priced, vol crushes instead"),
    )
    return ReactionMap(scenario=label, impulse=impulse, regime=regime,
                       cells=cells, chain=chain)


def _growth(label, impulse, regime, magnitude) -> ReactionMap:
    stronger = impulse is Impulse.GROWTH_STRONGER
    inflation_dominant = regime is MacroRegime.INFLATION_DOMINANT
    strong = magnitude >= 1.5

    def d(up: bool, big: bool = False) -> Direction:
        if up:
            return Direction.STRONG_UP if (big and strong) else Direction.UP
        return Direction.STRONG_DOWN if (big and strong) else Direction.DOWN

    # The whole point: the equity sign flips with the regime.
    equity_up = stronger if not inflation_dominant else (not stronger)

    if inflation_dominant:
        chain = (
            f"Growth impulse is {'stronger' if stronger else 'weaker'} than expected.",
            "In an inflation-dominant regime the policy path is the binding "
            "constraint, so stronger growth means later/less easing: yields rise.",
            "Good news is therefore sold in equities and bad news is bought - the "
            "stock/bond correlation is positive.",
            "This holds only while growth is far enough above stall speed. Once "
            "weak data starts threatening earnings, the regime itself flips and the "
            "sign of the equity response inverts.",
        )
    else:
        chain = (
            f"Growth impulse is {'stronger' if stronger else 'weaker'} than expected.",
            "In a growth-dominant regime earnings and recession risk are binding, so "
            "the growth signal is read directly rather than through the policy path.",
            "Bonds resume hedging equities: weak data rallies duration and sells "
            "equities simultaneously.",
            "The dollar's sign is genuinely contested here - the rate-differential "
            "channel and the haven channel pull in opposite directions.",
        )

    cells = (
        _c("USD (DXY)",
           d(stronger) if inflation_dominant else Direction.AMBIGUOUS,
           "rate differentials favour the dollar on strong data" if inflation_dominant
           else "rate differential says down on weak data, haven demand says up; "
                "which wins depends on whether the weakness is US-specific or global",
           0.65 if inflation_dominant else 0.3,
           "" if inflation_dominant else "resolve by checking whether US yields fell "
           "more than G10 peers"),
        _c("EURUSD", d(not stronger) if inflation_dominant else Direction.AMBIGUOUS,
           "mirror of the dollar leg", 0.6 if inflation_dominant else 0.3),
        _c("USDJPY", d(stronger), "rate-differential sensitivity dominates in both "
           "regimes, though risk-off JPY demand can override it", 0.6,
           "sharp risk-off reverses this: JPY is a funding currency"),
        _c("US 2Y", d(stronger, True), "growth surprise moves the expected policy "
           "path directly", 0.8),
        _c("US 10Y", d(stronger), "follows the front end, damped by term premium", 0.72),
        _c("2s10s", d(not stronger), "front end does more work in both directions", 0.6,
           "a fiscal or supply shock can steepen the curve against this"),
        _c("S&P 500", d(equity_up),
           "good news is bad news: tighter expected policy compresses multiples"
           if inflation_dominant else
           "growth reads straight through to earnings expectations",
           0.6),
        _c("Nasdaq 100", d(equity_up, True),
           "duration amplifies whichever channel dominates", 0.58),
        _c("Gold", d(not stronger) if inflation_dominant else Direction.AMBIGUOUS,
           "real yields dominate" if inflation_dominant else
           "falling real yields say up, risk-asset liquidation says down", 0.5,
           "" if inflation_dominant else "check whether gold is trading as a real-rate "
           "asset or as a haven this week"),
        _c("WTI Crude", d(stronger), "demand expectations move with the growth "
           "impulse", 0.55, "supply news (OPEC+, outages) routinely dominates demand"),
        _c("BTC", d(equity_up), "trades as a high-beta liquidity asset, so it "
           "generally follows the equity leg", 0.42,
           "the weakest link in the chain: correlation is unstable and regime-dependent"),
        _c("HY credit", d(equity_up), "spreads follow the growth/earnings signal", 0.55),
        _c("VIX", d(not equity_up), "vol rises when the equity leg falls", 0.55),
    )
    return ReactionMap(scenario=label, impulse=impulse, regime=regime,
                       cells=cells, chain=chain)


def _liquidity_dominant(label, impulse, regime, up_big, dn_big) -> ReactionMap:
    chain = (
        "Funding and collateral conditions are the binding constraint.",
        "Forced deleveraging dominates the macro signal: correlations converge "
        "toward one and everything that can be sold is sold.",
        "The dollar bids as the funding currency regardless of the growth or "
        "inflation signal - this is the channel that overrides rate differentials.",
        "Treasuries are genuinely two-sided: haven demand pulls yields down, "
        "liquidation of the most liquid collateral pushes them up.",
    )
    cells = (
        _c("USD (DXY)", up_big, "dollar funding demand overrides rate differentials", 0.8),
        _c("EURUSD", dn_big, "mirror of the dollar bid", 0.72),
        _c("USDJPY", Direction.AMBIGUOUS, "dollar bid says up, JPY repatriation and "
           "carry unwind say down; in acute stress the carry unwind usually wins", 0.35,
           "the single most violent pair in a liquidity event"),
        _c("US 2Y", Direction.DOWN, "policy-easing expectations get priced fast", 0.6),
        _c("US 10Y", Direction.AMBIGUOUS, "haven bid vs liquidation of liquid "
           "collateral", 0.3, "watch the swap spread to tell them apart"),
        _c("2s10s", Direction.UP, "front end rallies hardest on easing expectations", 0.55),
        _c("S&P 500", dn_big, "risk liquidation", 0.78),
        _c("Nasdaq 100", dn_big, "highest beta to liquidation", 0.78),
        _c("Gold", Direction.AMBIGUOUS, "haven bid, but gold is sold early in a "
           "margin event because it is liquid", 0.3,
           "sequence matters: sold first, bought later"),
        _c("WTI Crude", Direction.DOWN, "demand destruction plus liquidation", 0.6),
        _c("BTC", dn_big, "highest-beta liquidity asset, 24/7 market makes it the "
           "first thing sold when other markets are shut", 0.7),
        _c("HY credit", dn_big, "spreads gap; primary market closes", 0.75),
        _c("VIX", up_big, "vol expansion is the definition of the regime", 0.85),
    )
    return ReactionMap(scenario=label, impulse=impulse, regime=regime,
                       cells=cells, chain=chain)


# --------------------------------------------------------------------------
# Second-order analysis (spec section 9)
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class OrderAnalysis:
    first_order: str
    second_order: str
    third_order_risk: str
    most_sensitive_assets: tuple[str, ...]
    questions_answered: tuple[tuple[str, str], ...]
    category: Category = Category.INTERPRETATION
    ok: bool = True

    def render(self) -> str:
        q = "\n".join(f"  - {k}\n      {v}" for k, v in self.questions_answered)
        return (
            f"FIRST ORDER   {self.first_order}\n"
            f"SECOND ORDER  {self.second_order}\n"
            f"THIRD ORDER   {self.third_order_risk}\n"
            f"MOST SENSITIVE: {', '.join(self.most_sensitive_assets)}\n"
            f"TRANSMISSION\n{q}"
        )


def analyse_orders(rmap: ReactionMap) -> OrderAnalysis:
    """Spec section 9: go past 'the print was hot'."""
    hot = rmap.impulse is Impulse.INFLATION_HOTTER
    cool = rmap.impulse is Impulse.INFLATION_COOLER
    strong = rmap.impulse is Impulse.GROWTH_STRONGER
    weak = rmap.impulse is Impulse.GROWTH_WEAKER

    ranked = sorted(rmap.cells, key=lambda c: -c.confidence)
    sensitive = tuple(c.asset for c in ranked[:4])

    if hot or strong:
        first = ("Front end sells off, dollar bids, long-duration equity de-rates. "
                 "This leg is mechanical and fast - it is priced within minutes.")
        second = ("The tradeable question is whether the move survives the day. "
                  "Watch whether the curve holds its flattening and whether real "
                  "yields, not just breakevens, did the work. A repricing carried "
                  "entirely by breakevens usually mean-reverts; one carried by real "
                  "yields persists and keeps pressuring multiples.")
        third = ("The interpretation fails if the surprise came from a component the "
                 "policy reaction function ignores (used cars, airfares, energy "
                 "base effects), if the prior print is revised the other way, or if "
                 "officials explicitly discount it within 48 hours.")
    elif cool or weak:
        first = ("Front end rallies, dollar softens, duration and long-duration "
                 "equity bid. Again mechanical and fast.")
        second = ("Whether easing expectations that get pulled forward actually stay "
                  "pulled forward. If the weakness is broad enough to threaten "
                  "earnings, the regime itself flips from inflation-dominant to "
                  "growth-dominant and the equity leg inverts even though the bond "
                  "leg is unchanged - the single most common way this trade fails.")
        third = ("Invalidated by a hot follow-up print, by officials pushing back on "
                 "the market's easing path, or by a supply/fiscal shock steepening "
                 "the curve for reasons unrelated to growth.")
    else:
        first = "No material repricing expected: the print was in line."
        second = ("Positioning unwind is the only likely move; it is noise, not "
                  "information, and it typically retraces.")
        third = "A revision to the prior print can still matter more than the headline."

    questions = (
        ("What does this change about the policy path?",
         "Read it off the front end, not off the headline: the 2y move IS the "
         "market's answer. If the 2y did not move, the print did not change the path."),
        ("Nominal vs real yields?",
         "Decompose the 10y into real and breakeven. Real does the transmission "
         "work into equity multiples, gold and the dollar; breakevens alone are "
         "usually a fade."),
        ("Dollar?",
         "Rate differentials versus G10 peers, not US yields in isolation. A US "
         "yield rise that Europe matches is not a dollar signal."),
        ("Financial conditions?",
         "Combine the dollar, real yields, credit spreads and equity level. A "
         "tightening in conditions does the Fed's work for it and is itself "
         "disinflationary with a lag - which is why the second-order move often "
         "opposes the first."),
        ("Equity valuation?",
         "Multiple compression is immediate and mechanical; earnings revisions are "
         "slow. Separate the two before concluding the move is 'wrong'."),
        ("Gold?",
         "Real yields when gold trades as a rates asset; the dollar and sovereign "
         "risk when it trades as a haven. Establish which mode is active before "
         "assigning a sign."),
        ("Crypto?",
         "Dollar liquidity and risk appetite, plus idiosyncratic flow. Treat the "
         "macro correlation as a weak prior that idiosyncratic flow frequently "
         "overrides - correlation here is not causation."),
        ("What is most sensitive?",
         "Highest-confidence cells in this map: " + ", ".join(sensitive) + "."),
    )

    return OrderAnalysis(
        first_order=first, second_order=second, third_order_risk=third,
        most_sensitive_assets=sensitive, questions_answered=questions,
    )


__all__ = [
    "ASSETS", "Cell", "Direction", "OrderAnalysis", "ReactionMap",
    "analyse_orders", "build_matrix",
]
