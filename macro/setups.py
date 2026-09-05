"""Trade setup engine and event whipsaw protocol (spec sections 19 and 20).

Every gate in this module is a refusal gate.  A setup is emitted only when the
catalyst, the structure, the liquidity target, the invalidation and the
risk/reward all pass independently.  Failing any one returns NO TRADE with the
reason, because a forced setup costs more than a missed one.

Risk arithmetic is deliberately explicit about the failure modes it guards:
zero-width stops, inverted stop/target geometry, costs quietly excluded from
R:R, and position sizes computed without a contract multiplier.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .structure import EventKind, StructureRead, Trend
from .types import Category, clamp


class Side(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"


MIN_RR = 3.0          # spec section 19 floor
PREFERRED_RR = 5.0    # spec section 19 preference


@dataclass(frozen=True)
class NoTrade:
    asset: str
    reasons: tuple[str, ...]
    verdict: str = "NO TRADE - WAIT FOR CONFIRMATION"
    category: Category = Category.INTERPRETATION
    ok: bool = False

    def render(self) -> str:
        rs = "\n".join(f"    - {r}" for r in self.reasons)
        return f"{self.verdict}  [{self.asset}]\n{rs}"


@dataclass(frozen=True)
class Sizing:
    account_risk_amount: float
    risk_per_unit: float
    units: float
    contract_multiplier: float
    notional_at_entry: float
    assumptions: tuple[str, ...]

    def render(self) -> str:
        return (
            f"size {self.units:.4g} units (multiplier {self.contract_multiplier:g}), "
            f"risk/unit {self.risk_per_unit:.5g}, notional {self.notional_at_entry:,.2f}"
        )


@dataclass(frozen=True)
class Setup:
    asset: str
    side: Side
    timeframe: str
    catalyst: str
    market_structure: str
    liquidity_target: str
    entry_low: float
    entry_high: float
    invalidation: float
    tp1: float
    tp2: float
    tp3: float
    rr_gross: float
    rr_net: float
    cost_per_unit: float
    confidence: float
    catalyst_risk: str
    sizing: Sizing | None
    notes: tuple[str, ...]
    category: Category = Category.SCENARIO
    ok: bool = True

    @property
    def entry_mid(self) -> float:
        return (self.entry_low + self.entry_high) / 2.0

    def render(self) -> str:
        n = "\n".join(f"    - {x}" for x in self.notes)
        s = f"\n  SIZING        {self.sizing.render()}" if self.sizing else ""
        return (
            f"SETUP {self.side.value} {self.asset} ({self.timeframe})\n"
            f"  CATALYST      {self.catalyst}\n"
            f"  STRUCTURE     {self.market_structure}\n"
            f"  LIQUIDITY     {self.liquidity_target}\n"
            f"  ENTRY         {self.entry_low:.5g} - {self.entry_high:.5g}\n"
            f"  INVALIDATION  {self.invalidation:.5g}\n"
            f"  TP1/TP2/TP3   {self.tp1:.5g} / {self.tp2:.5g} / {self.tp3:.5g}\n"
            f"  R:R           {self.rr_gross:.2f}R gross, {self.rr_net:.2f}R net of "
            f"{self.cost_per_unit:.5g}/unit costs\n"
            f"  CONFIDENCE    {self.confidence:.2f}\n"
            f"  CATALYST RISK {self.catalyst_risk}{s}\n  NOTES\n{n}"
        )


def build_setup(
    *,
    asset: str,
    side: Side,
    timeframe: str,
    catalyst: str | None,
    structure: StructureRead | None,
    entry_low: float,
    entry_high: float,
    invalidation: float,
    tp1: float,
    tp2: float,
    tp3: float,
    liquidity_target: str | None,
    cost_per_unit: float = 0.0,
    account_equity: float | None = None,
    risk_fraction: float = 0.01,
    contract_multiplier: float = 1.0,
    catalyst_aligned: bool | None = None,
    catalyst_risk: str = "UNKNOWN",
    require_structure_confirmation: bool = True,
) -> Setup | NoTrade:
    """Validate and assemble one setup, or refuse it with reasons."""
    reasons: list[str] = []
    notes: list[str] = []

    if entry_high < entry_low:
        entry_low, entry_high = entry_high, entry_low
        notes.append("entry bounds were supplied inverted and have been swapped")
    entry = (entry_low + entry_high) / 2.0

    # --- geometry ---------------------------------------------------------
    if side is Side.LONG:
        if not (invalidation < entry_low):
            reasons.append(
                f"geometry invalid for a long: invalidation {invalidation:.5g} must sit "
                f"below the entry zone low {entry_low:.5g}"
            )
        if not (tp1 > entry_high):
            reasons.append(
                f"TP1 {tp1:.5g} is not above the entry zone high {entry_high:.5g}"
            )
        if not (tp1 <= tp2 <= tp3):
            reasons.append("targets are not monotonically ordered for a long")
        risk_per_unit = entry - invalidation
        reward_per_unit = tp3 - entry
        first_reward = tp1 - entry
    else:
        if not (invalidation > entry_high):
            reasons.append(
                f"geometry invalid for a short: invalidation {invalidation:.5g} must sit "
                f"above the entry zone high {entry_high:.5g}"
            )
        if not (tp1 < entry_low):
            reasons.append(
                f"TP1 {tp1:.5g} is not below the entry zone low {entry_low:.5g}"
            )
        if not (tp1 >= tp2 >= tp3):
            reasons.append("targets are not monotonically ordered for a short")
        risk_per_unit = invalidation - entry
        reward_per_unit = entry - tp3
        first_reward = entry - tp1

    if risk_per_unit <= 0:
        reasons.append(
            "risk per unit is zero or negative: the stop is at or beyond the entry, "
            "which would divide by zero in the R:R and the position size"
        )
        return NoTrade(asset, tuple(reasons))

    if cost_per_unit < 0:
        reasons.append("cost_per_unit is negative; costs cannot be a credit")
    # Costs hit both legs of the trade: they widen effective risk and shrink reward.
    rr_gross = reward_per_unit / risk_per_unit
    rr_net = (reward_per_unit - cost_per_unit) / (risk_per_unit + cost_per_unit)

    # --- gates ------------------------------------------------------------
    if catalyst is None or not catalyst.strip():
        reasons.append("no macro catalyst identified: this system does not trade structure alone")
    if liquidity_target is None or not liquidity_target.strip():
        reasons.append("no identifiable liquidity target: nothing for price to be drawn toward")
    if catalyst_aligned is False:
        reasons.append("macro catalyst points against the technical direction")
    if catalyst_aligned is None:
        notes.append(
            "catalyst/structure alignment was not asserted: treat directional "
            "confidence as capped"
        )

    struct_note = "UNKNOWN - no structural read supplied"
    if structure is not None:
        struct_note = structure.trend.value
        confirming = {
            Side.LONG: (EventKind.BOS_UP, EventKind.CHOCH_UP, EventKind.SWEEP_LOW,
                        EventKind.DISPLACEMENT_UP),
            Side.SHORT: (EventKind.BOS_DOWN, EventKind.CHOCH_DOWN, EventKind.SWEEP_HIGH,
                         EventKind.DISPLACEMENT_DOWN),
        }[side]
        found = [e for e in structure.events if e.kind in confirming]
        if found:
            last = found[-1]
            struct_note = f"{structure.trend.value}; last confirmation {last.kind.value} @ {last.price:.5g}"
            notes.append(f"structural confirmation: {last.detail}")
        elif require_structure_confirmation:
            reasons.append(
                f"no structural confirmation for a {side.value}: need a BOS, CHoCH, "
                "opposing-side sweep or displacement in the trade direction"
            )
    elif require_structure_confirmation:
        reasons.append("no structural read supplied and structure confirmation is required")

    if rr_net < MIN_RR:
        reasons.append(
            f"risk/reward {rr_net:.2f}R net is below the {MIN_RR:.0f}R floor "
            f"(gross {rr_gross:.2f}R). Costs alone account for "
            f"{rr_gross - rr_net:.2f}R of that."
        )

    if reasons:
        return NoTrade(asset, tuple(reasons))

    # --- sizing -----------------------------------------------------------
    sizing = None
    if account_equity is not None:
        if account_equity <= 0:
            return NoTrade(asset, ("account equity must be positive to size a position",))
        if not (0 < risk_fraction <= 0.05):
            return NoTrade(
                asset,
                (f"risk_fraction {risk_fraction:.4f} is outside the sane 0-5% band; "
                 "refusing to size a position that large",),
            )
        if contract_multiplier <= 0:
            return NoTrade(asset, ("contract_multiplier must be positive",))
        risk_amount = account_equity * risk_fraction
        denom = (risk_per_unit + cost_per_unit) * contract_multiplier
        units = risk_amount / denom
        sizing = Sizing(
            account_risk_amount=risk_amount,
            risk_per_unit=risk_per_unit,
            units=units,
            contract_multiplier=contract_multiplier,
            notional_at_entry=units * entry * contract_multiplier,
            assumptions=(
                f"price and stop are quoted in the same unit as entry ({asset})",
                f"one unit controls {contract_multiplier:g} of the underlying",
                "stop fills at the invalidation level: gap risk through the stop is "
                "NOT covered by this size, and around macro releases it is material",
                f"costs of {cost_per_unit:.5g}/unit are included in the risk denominator",
            ),
        )

    # --- confidence -------------------------------------------------------
    conf = 0.35
    if rr_net >= PREFERRED_RR:
        conf += 0.15
    if catalyst_aligned:
        conf += 0.15
    if structure is not None and structure.trend is not Trend.RANGING:
        conf += 0.10
    if structure is not None and any(
        e.kind in (EventKind.DISPLACEMENT_UP, EventKind.DISPLACEMENT_DOWN)
        for e in structure.events[-6:]
    ):
        conf += 0.05
    conf = clamp(conf, 0.0, 0.85)

    notes.append(
        f"first target is {first_reward / risk_per_unit:.2f}R: scaling there de-risks "
        "the position before the second-order move decides the rest"
    )
    if rr_net < PREFERRED_RR:
        notes.append(
            f"{rr_net:.2f}R clears the floor but is below the {PREFERRED_RR:.0f}R "
            "preference; size accordingly or wait for a better entry"
        )
    notes.append(
        "R:R assumes the full position runs to TP3. Scaling out lowers realised R "
        "below the number shown."
    )

    return Setup(
        asset=asset, side=side, timeframe=timeframe, catalyst=catalyst,
        market_structure=struct_note, liquidity_target=liquidity_target,
        entry_low=entry_low, entry_high=entry_high, invalidation=invalidation,
        tp1=tp1, tp2=tp2, tp3=tp3, rr_gross=rr_gross, rr_net=rr_net,
        cost_per_unit=cost_per_unit, confidence=round(conf, 2),
        catalyst_risk=catalyst_risk, sizing=sizing, notes=tuple(notes),
    )


# --------------------------------------------------------------------------
# Event whipsaw protocol (spec section 20)
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class WhipsawPlan:
    event: str
    initial_reaction_zone: str
    sweep_zone: str
    confirmation_zone: str
    structural_invalidation: str
    final_target: str
    sequence: tuple[str, ...]
    rule: str
    category: Category = Category.SCENARIO
    ok: bool = True

    def render(self) -> str:
        seq = "\n".join(f"  {i+1}. {s}" for i, s in enumerate(self.sequence))
        return (
            f"WHIPSAW PROTOCOL - {self.event}\n{seq}\n"
            f"  INITIAL REACTION  {self.initial_reaction_zone}\n"
            f"  SWEEP ZONE        {self.sweep_zone}\n"
            f"  CONFIRMATION      {self.confirmation_zone}\n"
            f"  INVALIDATION      {self.structural_invalidation}\n"
            f"  FINAL TARGET      {self.final_target}\n"
            f"  RULE              {self.rule}"
        )


def whipsaw_plan(
    event: str,
    structure: StructureRead | None,
    *,
    pre_event_high: float | None = None,
    pre_event_low: float | None = None,
) -> WhipsawPlan:
    """Map the four-phase release sequence onto real levels where they exist."""
    def lvl(x: float | None, label: str) -> str:
        return f"{label} {x:.5g}" if x is not None else f"{label} UNKNOWN - supply the level"

    if structure and structure.pools:
        buy = [p for p in structure.pools if p.kind == "buy-side"]
        sell = [p for p in structure.pools if p.kind == "sell-side"]
        sweep = "; ".join(
            f"{p.kind} pool at {p.price:.5g} ({p.touches} touches)"
            for p in (buy[-1:] + sell[-1:])
        ) or "no clustered pools identified"
    else:
        sweep = "UNKNOWN - no clustered liquidity identified in the supplied series"

    invalid = "UNKNOWN"
    if structure and structure.last_confirmed_low and structure.last_confirmed_high:
        invalid = (
            f"last confirmed swing low {structure.last_confirmed_low.price:.5g} / "
            f"swing high {structure.last_confirmed_high.price:.5g}"
        )

    return WhipsawPlan(
        event=event,
        initial_reaction_zone=(
            f"{lvl(pre_event_low, 'pre-event low')} to {lvl(pre_event_high, 'pre-event high')} "
            "- the algorithmic first move, usually completed inside 60 seconds"
        ),
        sweep_zone=sweep,
        confirmation_zone=(
            "a close beyond the swept level in the opposite direction, ideally with "
            "displacement, on the first candle after the sweep completes"
        ),
        structural_invalidation=invalid,
        final_target=(
            "the opposing liquidity pool, or the unfilled FVG left by the "
            "displacement leg" if structure and structure.fvgs
            else "UNKNOWN - no unfilled imbalance identified"
        ),
        sequence=(
            "Initial spike: algorithmic reaction to the headline number, frequently "
            "against the eventual direction.",
            "Liquidity sweep: the spike runs the obvious stops sitting either side of "
            "the pre-event range.",
            "Reversal: real money begins pricing the full release, not the headline "
            "(components, revisions, the policy read-through).",
            "Directional move: the leg that holds, usually beginning 5-30 minutes "
            "after the release.",
        ),
        rule=(
            "Do not enter on the first spike. Wait for the sweep to complete and for "
            "a close that rejects the swept level. Missing the first 20% of the move "
            "is the cost of not being the liquidity."
        ),
    )


__all__ = [
    "MIN_RR", "PREFERRED_RR", "NoTrade", "Setup", "Side", "Sizing", "WhipsawPlan",
    "build_setup", "whipsaw_plan",
]
