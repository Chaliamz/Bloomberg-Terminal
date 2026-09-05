"""Daily institutional brief - the 12-section global macro dashboard (spec 24)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta

from .calendar_spec import RELEASES, Release, top_tier
from .events import MacroEvent
from .regime import MacroRegime, RiskRegime
from .state import MarketState
from .types import Category, iso, utcnow

BIAS = ("BULLISH", "BEARISH", "NEUTRAL", "WAIT")


@dataclass(frozen=True)
class Section:
    number: int
    title: str
    lines: tuple[str, ...]

    def render(self) -> str:
        body = "\n".join(f"    {l}" for l in self.lines) or "    UNKNOWN"
        return f"  {self.number}. {self.title}\n{body}"


@dataclass(frozen=True)
class DailyBrief:
    generated_at: datetime
    sections: tuple[Section, ...]
    bias: str
    bias_reason: str
    category: Category = Category.INTERPRETATION
    ok: bool = True

    def render(self) -> str:
        head = [
            "=" * 78,
            "GLOBAL MACRO DASHBOARD - DAILY INSTITUTIONAL BRIEF",
            f"Generated {iso(self.generated_at)}",
            "=" * 78,
        ]
        body = [s.render() for s in self.sections]
        tail = [
            "=" * 78,
            f"  TRADING BIAS: {self.bias}",
            f"    {self.bias_reason}",
            "=" * 78,
        ]
        return "\n".join(head + body + tail)


def _unknown(what: str) -> tuple[str, ...]:
    return (f"UNKNOWN - {what}",)


def build(
    state: MarketState,
    events: list[MacroEvent],
    *,
    overnight: list[str] | None = None,
    geopolitical: list[str] | None = None,
    upcoming: list[tuple[str, str]] | None = None,
    now: datetime | None = None,
) -> DailyBrief:
    now = now or utcnow()
    ranked = sorted(events, key=lambda e: -e.effective_priority)

    # 1 overnight
    s1 = Section(1, "OVERNIGHT DEVELOPMENTS", tuple(overnight or ()) or _unknown(
        "no overnight items supplied. Asia and European sessions are not "
        "reconstructed from price alone."))

    # 2 catalysts
    if ranked:
        cat_lines = tuple(e.one_line() for e in ranked[:8])
    else:
        cat_lines = _unknown("no events loaded into the radar")
    s2 = Section(2, "TODAY'S MAJOR CATALYSTS (ranked by priority score)", cat_lines)

    # 3 central banks
    cb = [
        f"{r.label} - {r.agency}, {r.clock or 'no fixed time'} {r.tz} "
        f"(confidence {r.confidence:.2f}, verify: {r.verify})"
        for r in RELEASES
        if r.event_class.value in (
            "SCHEDULED POLICY DECISION", "PRESS CONFERENCE", "OFFICIAL SPEECH",
            "POLICY MINUTES / TRANSCRIPT",
        )
    ][:10]
    cb.append(
        "Specific meeting dates and speaker lists are NOT generated here: they come "
        "from each bank's published calendar and must be ingested."
    )
    s3 = Section(3, "CENTRAL BANKS", tuple(cb))

    # 4 data
    if upcoming:
        data_lines = tuple(f"{when}  {what}" for what, when in upcoming)
    else:
        rule_based = []
        today = (now.date() if isinstance(now, datetime) else date.today())
        for r in RELEASES:
            nxt = r.next_occurrences(today, 1)
            if isinstance(nxt, list) and nxt and (nxt[0].date() - today) <= timedelta(days=7):
                rule_based.append(
                    f"{iso(nxt[0])}  {r.label} ({r.agency}) - rule-derived, "
                    f"confidence {r.confidence:.2f}"
                )
        rule_based.sort()
        data_lines = tuple(rule_based) or _unknown("no rule-derivable releases in the next 7 days")
        data_lines += (
            "Agency-scheduled releases (CPI, PCE, FOMC, ECB, retail sales and most "
            "others) have no rule and are omitted until the official calendar is "
            "ingested. Consensus values are never generated.",
        )
    s4 = Section(4, "ECONOMIC DATA - NEXT 7 DAYS", data_lines)

    # 5 curve
    cr = state.curve()
    if getattr(cr, "ok", False):
        s5_lines = (cr.render(),) + tuple(cr.pricing) + (      # type: ignore[union-attr]
            f"real: {cr.real_yield_note} | breakevens: {cr.breakeven_note}",  # type: ignore[union-attr]
        )
    else:
        s5_lines = (cr.render(),)                              # type: ignore[union-attr]
    s5 = Section(5, "YIELD CURVE", s5_lines)

    # 6 dollar
    dxy, dxy_p = state.get("DXY", "index"), state.get("DXY_PRIOR", "index")
    if dxy.known and dxy_p.known:
        chg = dxy.require("dxy") - dxy_p.require("dxy")
        pct = 100.0 * chg / dxy_p.require("dxy")
        s6_lines = (
            f"DXY {dxy.render()} ({pct:+.2f}% vs prior close)",
            "The dollar leg is the cleanest confirmation of a rates-driven move: if "
            "yields move and the dollar does not, the move is not about policy.",
        )
    else:
        s6_lines = _unknown("dollar index and/or its prior close not supplied")
    s6 = Section(6, "USD", s6_lines)

    # 7 equity risk
    vix = state.get("VIX", "index")
    s7_lines = (
        f"VIX {vix.render()}",
        f"S&P 500 {state.get('SPX', 'index').render()} | "
        f"Nasdaq 100 {state.get('NDX', 'index').render()}",
        "Equity risk is read through the regime: in an inflation-dominant regime a "
        "yield move IS the equity story; in a growth-dominant one it is not.",
    ) if vix.known or state.get("SPX").known else _unknown("no equity or vol inputs supplied")
    s7 = Section(7, "EQUITY RISK", s7_lines)

    # 8 commodities
    s8_lines = (
        f"Gold {state.get('GOLD', 'usd').render()} | WTI {state.get('WTI', 'usd_bbl').render()}",
        "Gold: establish whether it is trading the real-yield channel or the haven "
        "channel before assigning a direction to any macro shock.",
        "Oil: supply news (OPEC+, outages, sanctions) routinely dominates the demand "
        "signal that macro data carries.",
    )
    s8 = Section(8, "COMMODITIES", s8_lines)

    # 9 crypto
    s9_lines = (
        f"BTC {state.get('BTC', 'usd').render()} | ETH {state.get('ETH', 'usd').render()}",
        "Transmission: dollar liquidity -> real yields -> risk appetite -> crypto. "
        "That chain is a weak prior, not a law: ETF flow, funding, liquidations and "
        "protocol events regularly override it.",
        "Funding rates, open interest, basis, stablecoin supply and exchange flows: "
        "UNKNOWN unless supplied - they are not inferred from price.",
    )
    s9 = Section(9, "CRYPTO", s9_lines)

    # 10 geopolitics
    s10 = Section(10, "GEOPOLITICAL RISK", tuple(geopolitical or ()) or _unknown(
        "no geopolitical items supplied. Only developments with an identifiable "
        "transmission channel into energy, trade, sanctions or sovereign risk "
        "belong in this section."))

    # 11 levels
    if state.session_levels:
        s11_lines = tuple(f"{k}: {v:.6g}" for k, v in sorted(state.session_levels.items()))
    else:
        s11_lines = _unknown(
            "no session levels supplied. Previous day/week extremes and Asia/London/NY "
            "session ranges are measurements, not estimates, and are not invented here.")
    s11 = Section(11, "KEY LEVELS", s11_lines)

    # 12 bias
    bias, reason = _bias(state, ranked)
    s12 = Section(12, "TRADING BIAS", (bias, reason))

    return DailyBrief(
        generated_at=now,
        sections=(s1, s2, s3, s4, s5, s6, s7, s8, s9, s10, s11, s12),
        bias=bias, bias_reason=reason,
    )


def _bias(state: MarketState, ranked: list[MacroEvent]) -> tuple[str, str]:
    """Bias defaults to WAIT.  It is earned, not assumed."""
    cond = state.conditions()
    cov = state.coverage

    if state.regime is MacroRegime.UNKNOWN:
        return "WAIT", (
            "Regime is not established. The same data surprise maps to opposite "
            "equity outcomes across regimes, so a directional bias here would be "
            "a coin flip dressed as analysis."
        )
    if cov < 0.35:
        return "WAIT", (
            f"Market-state coverage is {cov:.0%}. A bias formed on this little data "
            "is an opinion, not a read."
        )
    imminent = [e for e in ranked if e.band.value in ("EXTREME", "HIGH")]
    if imminent:
        return "WAIT", (
            f"{len(imminent)} high-or-extreme priority catalyst(s) unresolved "
            f"(top: {imminent[0].title}). Pre-event positioning into an unpriced "
            "binary is not an edge."
        )
    if getattr(cond, "ok", False):
        c = cond  # type: ignore[assignment]
        if c.regime is RiskRegime.LIQUIDITY_STRESS:
            return "BEARISH", (
                "Funding-stress alarms are live: in a liquidity-dominant regime "
                "correlations converge and the dollar bids regardless of the macro signal."
            )
        if c.regime is RiskRegime.RISK_ON and c.confidence >= 0.4:
            return "BULLISH", (
                f"Risk-on with {c.coverage:.0%} panel coverage and no unresolved "
                "high-priority catalyst."
            )
        if c.regime is RiskRegime.RISK_OFF and c.confidence >= 0.4:
            return "BEARISH", (
                f"Risk-off with {c.coverage:.0%} panel coverage and no unresolved "
                "high-priority catalyst."
            )
    return "NEUTRAL", (
        "No regime-level signal strong enough to justify a directional bias. "
        "Neutral is a position; forcing one is not."
    )


__all__ = ["BIAS", "DailyBrief", "Section", "build"]
