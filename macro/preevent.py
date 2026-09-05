"""Pre-event intelligence mode: T-60 / T-30 / T-15 / T-5 (spec section 7)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from .reaction import ReactionMap
from .regime import MacroRegime
from .setups import WhipsawPlan, whipsaw_plan
from .structure import StructureRead
from .surprise import Impulse, IndicatorSpec, surprise_distribution
from .types import Category, Observation, iso, unknown

UNK = "UNKNOWN - supply this input; it is not inferred"


@dataclass(frozen=True)
class Slice:
    label: str
    minutes_before: int
    lines: tuple[str, ...]

    def render(self) -> str:
        body = "\n".join(f"  {l}" for l in self.lines)
        return f"--- {self.label} ---\n{body}"


@dataclass(frozen=True)
class ScenarioLeg:
    name: str
    trigger: str
    expected_reaction: str
    assets_affected: tuple[str, ...]
    key_levels: str
    invalidation: str

    def render(self) -> str:
        return (
            f"  {self.name}\n"
            f"    TRIGGER      {self.trigger}\n"
            f"    REACTION     {self.expected_reaction}\n"
            f"    ASSETS       {', '.join(self.assets_affected)}\n"
            f"    KEY LEVELS   {self.key_levels}\n"
            f"    INVALIDATION {self.invalidation}"
        )


@dataclass(frozen=True)
class PreEventPack:
    event: str
    scheduled_for: datetime | None
    regime: MacroRegime
    slices: tuple[Slice, ...]
    bullish: ScenarioLeg
    bearish: ScenarioLeg
    whipsaw: WhipsawPlan
    five_minute_brief: tuple[str, ...]
    unknowns: tuple[str, ...]
    category: Category = Category.SCENARIO
    ok: bool = True

    def render(self) -> str:
        parts = [
            f"PRE-EVENT INTELLIGENCE - {self.event}",
            f"Scheduled: {iso(self.scheduled_for) or 'UNKNOWN'} | Regime: {self.regime.value}",
            "",
        ]
        parts += [s.render() for s in self.slices]
        parts += ["", "--- FINAL EVENT MAP (T-15) ---",
                  self.bullish.render(), self.bearish.render(), ""]
        parts += [self.whipsaw.render(), "", "--- 5-MINUTE MACRO BRIEF (T-5) ---"]
        parts += [f"  {l}" for l in self.five_minute_brief]
        if self.unknowns:
            parts += ["", "--- UNRESOLVED INPUTS (do not paper over these) ---"]
            parts += [f"  ? {u}" for u in self.unknowns]
        return "\n".join(parts)


def build(
    event: str,
    *,
    scheduled_for: datetime | None,
    regime: MacroRegime,
    indicator: IndicatorSpec | None = None,
    consensus: Observation | None = None,
    previous: Observation | None = None,
    sigma: float | None = None,
    reaction_up: ReactionMap | None = None,
    reaction_down: ReactionMap | None = None,
    structure: StructureRead | None = None,
    market_pricing: str | None = None,
    implied_vol: str | None = None,
    positioning: str | None = None,
    revision_risk: str | None = None,
    liquidity_note: str | None = None,
    pre_event_high: float | None = None,
    pre_event_low: float | None = None,
    recent_related: tuple[str, ...] = (),
) -> PreEventPack:
    """Assemble the full pre-event framework.

    Every input the caller does not supply is rendered as UNKNOWN. Nothing here
    invents a consensus, an implied vol or a positioning read.
    """
    consensus = consensus or (unknown(indicator.unit) if indicator else unknown("?"))
    previous = previous or (unknown(indicator.unit) if indicator else unknown("?"))
    unknowns: list[str] = []

    def val(x: str | None, name: str) -> str:
        if x:
            return x
        unknowns.append(name)
        return UNK

    dist = (
        surprise_distribution(indicator, consensus, sigma)
        if indicator else
        {"mild": UNK, "moderate": UNK, "extreme": UNK}
    )

    t60 = Slice("T-60 MINUTES", 60, (
        f"Regime: {regime.value} - {regime.explanation}",
        f"Consensus: {consensus.render()}    Previous: {previous.render()}",
        f"Revision risk: {val(revision_risk, 'revision risk')}",
        f"Market-implied pricing: {val(market_pricing, 'market-implied pricing')}",
        f"Options-implied volatility: {val(implied_vol, 'implied volatility')}",
        f"Positioning: {val(positioning, 'positioning')}",
        f"Liquidity conditions: {val(liquidity_note, 'liquidity conditions')}",
        "Related recent indicators: " + (", ".join(recent_related) if recent_related
                                         else UNK),
        f"Structure: {structure.trend.value if structure else UNK}",
        "Reaction function: what would have to be true for the policy path to move? "
        "If the front end does not reprice, the print did not matter.",
    ))

    t30 = Slice("T-30 MINUTES", 30, (
        "Re-check: new headlines since T-60, late forecast revisions, any official "
        "comment that changes the reaction function.",
        "Re-check: front-end yields, the dollar leg, and implied vol - a market that "
        "has already moved has partly priced the outcome you are waiting for.",
        "Re-check: whether correlated assets are confirming or diverging. Divergence "
        "before a release is information about positioning, not about the number.",
        f"Surprise bands - mild: {dist['mild']}",
        f"                moderate: {dist['moderate']}",
        f"                extreme: {dist['extreme']}",
    ))

    t15 = Slice("T-15 MINUTES", 15, (
        "Final event map below. Levels are fixed now, before the number, so the "
        "decision is not made inside the volatility.",
        "Confirm order-book depth has thinned (it will) and that stop distance "
        "accounts for the widened spread.",
        "Decide in advance which outcome means NO TRADE.",
    ))

    up_assets = tuple(
        c.asset for c in (reaction_up.cells if reaction_up else ()) if c.confidence >= 0.6
    ) or ("UNKNOWN",)
    dn_assets = tuple(
        c.asset for c in (reaction_down.cells if reaction_down else ()) if c.confidence >= 0.6
    ) or ("UNKNOWN",)

    levels = "UNKNOWN - no structural read supplied"
    if structure:
        bits = []
        if structure.last_confirmed_high:
            bits.append(f"swing high {structure.last_confirmed_high.price:.5g}")
        if structure.last_confirmed_low:
            bits.append(f"swing low {structure.last_confirmed_low.price:.5g}")
        for p in structure.pools[:2]:
            bits.append(f"{p.kind} pool {p.price:.5g}")
        levels = "; ".join(bits) or levels

    bullish = ScenarioLeg(
        name="BULLISH-FOR-RISK SCENARIO",
        trigger=(
            f"print below the mild band ({dist['mild']}) on an inflation series, or "
            "above it on a growth series in a growth-dominant regime"
        ),
        expected_reaction=(
            reaction_up.chain[0] if reaction_up else
            "UNKNOWN - attach a reaction map for the upside impulse"
        ),
        assets_affected=up_assets,
        key_levels=levels,
        invalidation=(
            "front-end yields fail to fall, or fall and immediately retrace: the "
            "market is rejecting the interpretation"
        ),
    )
    bearish = ScenarioLeg(
        name="BEARISH-FOR-RISK SCENARIO",
        trigger=(
            f"print beyond the extreme band ({dist['extreme']}) in the hawkish "
            "direction, or a hawkish revision to the prior print"
        ),
        expected_reaction=(
            reaction_down.chain[0] if reaction_down else
            "UNKNOWN - attach a reaction map for the downside impulse"
        ),
        assets_affected=dn_assets,
        key_levels=levels,
        invalidation=(
            "the dollar and the front end move in opposite directions - that "
            "combination means the move is flow, not repricing"
        ),
    )

    whip = whipsaw_plan(event, structure,
                        pre_event_high=pre_event_high, pre_event_low=pre_event_low)

    five = (
        f"{event} - {iso(scheduled_for) or 'time UNKNOWN'}",
        f"Consensus {consensus.render()}, previous {previous.render()}.",
        f"Regime {regime.value}: {'good news is sold' if regime is MacroRegime.INFLATION_DOMINANT else 'growth reads straight through'}.",
        f"Priced: {market_pricing or UNK}",
        f"Extreme band that actually forces a repricing: {dist['extreme']}",
        "Do not trade the first spike. Wait for the sweep and the rejection close.",
        f"Invalidation is fixed at: {levels}",
    )

    if not unknowns:
        unknowns = []
    if structure is None:
        unknowns.append("market structure / key levels")
    if reaction_up is None or reaction_down is None:
        unknowns.append("cross-asset reaction maps for one or both directions")
    if sigma is None:
        unknowns.append("historical surprise sigma (bands cannot be quantified without it)")

    return PreEventPack(
        event=event, scheduled_for=scheduled_for, regime=regime,
        slices=(t60, t30, t15), bullish=bullish, bearish=bearish, whipsaw=whip,
        five_minute_brief=five, unknowns=tuple(dict.fromkeys(unknowns)),
    )


__all__ = ["PreEventPack", "ScenarioLeg", "Slice", "build"]
