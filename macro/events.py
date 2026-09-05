"""The unified event record and the MACRO ALERT format (spec sections 2, 25)."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime

from .noise import NoiseVerdict
from .reaction import ReactionMap
from .regime import MacroRegime
from .scoring import EventClass, ScoreCard, UrgencyBand, information_latency, score_event
from .sources import ConfirmationResult, confirm
from .surprise import SurpriseResult
from .types import (
    Category, Insufficient, Observation, SourceRef, Tier, Verification, iso, utcnow,
)


@dataclass(frozen=True)
class MacroEvent:
    event_id: str
    when: datetime | None
    title: str
    event_class: EventClass
    country: str
    summary: str
    sources: tuple[SourceRef, ...]
    confirmation: ConfirmationResult
    scores: ScoreCard
    noise: NoiseVerdict | None = None
    surprise: SurpriseResult | Insufficient | None = None
    reaction: ReactionMap | None = None
    market_pricing_before: str = "UNKNOWN - not supplied"
    key_levels: tuple[str, ...] = ()
    trade_implication: str = "NO TRADE - no validated setup attached to this event"
    invalidation: str = "UNKNOWN"
    is_unscheduled: bool = False
    tags: tuple[str, ...] = ()
    ok: bool = True

    @property
    def band(self) -> UrgencyBand:
        return self.scores.band

    @property
    def effective_priority(self) -> float:
        p = self.scores.priority
        return p * (self.noise.penalty if self.noise else 1.0)

    def one_line(self) -> str:
        t = iso(self.when) or "time UNKNOWN"
        return (
            f"[{self.effective_priority:5.1f}] {self.band.value:<13} {t}  "
            f"{self.country:<14} {self.title}"
        )


def make_event(
    title: str,
    *,
    event_class: EventClass,
    country: str,
    summary: str,
    sources: list[SourceRef],
    when: datetime | None = None,
    market_impact: float,
    expected_volatility: float,
    directional_confidence: float,
    surprise: SurpriseResult | Insufficient | None = None,
    reaction: ReactionMap | None = None,
    noise: NoiseVerdict | None = None,
    minutes_to_event: float | None = None,
    is_unscheduled: bool = False,
    live_streamed: bool = False,
    text_published_in_advance: bool = False,
    embargoed_release: bool = False,
    market_pricing_before: str = "UNKNOWN - not supplied",
    key_levels: tuple[str, ...] = (),
    trade_implication: str = "NO TRADE - no validated setup attached to this event",
    invalidation: str = "UNKNOWN",
    conflicts_with_primary: bool = False,
    market_reaction_contradicts: bool = False,
    tags: tuple[str, ...] = (),
) -> MacroEvent:
    """Assemble a fully scored event.  Surprise score is taken from the
    surprise engine when one is attached, never assumed."""
    conf = confirm(
        title, sources,
        conflicts_with_primary=conflicts_with_primary,
        market_reaction_contradicts=market_reaction_contradicts,
    )
    latency, _why = information_latency(
        event_class,
        live_streamed=live_streamed,
        text_published_in_advance=text_published_in_advance,
        embargoed_release=embargoed_release,
    )
    if surprise is not None and getattr(surprise, "ok", False):
        surprise_score = surprise.surprise_score           # type: ignore[union-attr]
    elif surprise is not None:
        surprise_score = 0.0
    else:
        surprise_score = 0.0

    scores = score_event(
        market_impact=market_impact,
        surprise=surprise_score,
        credibility_score=conf.credibility_score,
        information_latency_score=latency,
        expected_volatility=expected_volatility,
        directional_confidence=directional_confidence,
        minutes_to_event=minutes_to_event,
        is_unscheduled=is_unscheduled,
    )
    raw = f"{title}|{iso(when)}|{country}|{event_class.value}"
    eid = hashlib.sha1(raw.encode()).hexdigest()[:10]

    return MacroEvent(
        event_id=eid, when=when, title=title, event_class=event_class,
        country=country, summary=summary, sources=tuple(sources),
        confirmation=conf, scores=scores, noise=noise, surprise=surprise,
        reaction=reaction, market_pricing_before=market_pricing_before,
        key_levels=key_levels, trade_implication=trade_implication,
        invalidation=invalidation, is_unscheduled=is_unscheduled, tags=tags,
    )


# --------------------------------------------------------------------------
# Alert rendering (spec section 25)
# --------------------------------------------------------------------------

_FIRST_ORDER_ASSETS = ("USD (DXY)", "US 2Y", "US 10Y", "S&P 500", "Gold", "WTI Crude", "BTC")


def render_alert(ev: MacroEvent) -> str:
    lines: list[str] = []
    lines.append("=" * 78)
    lines.append("*** MACRO ALERT ***")
    lines.append("=" * 78)
    lines.append(f"TIME:         {iso(ev.when) or 'UNKNOWN'}")
    lines.append(f"EVENT:        {ev.title}")
    src = "; ".join(s.describe() for s in ev.sources) or "NO SOURCE ATTACHED"
    lines.append(f"SOURCE:       {src}")
    lines.append(
        f"CREDIBILITY:  {ev.confirmation.credibility_score:.0f}/100 - {ev.confirmation.label}"
    )
    lines.append(
        f"IMPACT SCORE: {ev.scores.market_impact:.0f}/100 | PRIORITY "
        f"{ev.effective_priority:.1f} | URGENCY {ev.scores.urgency:.1f} [{ev.band.value}]"
    )

    lines.append("")
    lines.append("WHAT HAPPENED")
    lines.append(f"  {ev.summary}")

    if ev.confirmation.misinformation_flags:
        lines.append("")
        lines.append("VERIFICATION FLAGS")
        for f in ev.confirmation.misinformation_flags:
            lines.append(f"  ! {f}")
        for a in ev.confirmation.required_actions:
            lines.append(f"  > {a}")

    lines.append("")
    lines.append("WHY IT MATTERS")
    if ev.reaction is not None:
        for i, step in enumerate(ev.reaction.chain, 1):
            lines.append(f"  {i}. {step}")
    else:
        lines.append("  UNKNOWN - no transmission map attached. Attach an impulse and a")
        lines.append("  regime to derive the mechanism rather than assert one.")

    lines.append("")
    lines.append("MARKET PRICING (BEFORE)")
    lines.append(f"  {ev.market_pricing_before}")

    if ev.surprise is not None:
        lines.append("")
        lines.append("SURPRISE")
        lines.append(f"  {ev.surprise.render()}")
        for n in getattr(ev.surprise, "notes", ()):
            lines.append(f"    - {n}")

    lines.append("")
    lines.append("EXPECTED FIRST-ORDER REACTION  (INTERPRETATION, not observation)")
    if ev.reaction is not None:
        for asset in _FIRST_ORDER_ASSETS:
            cell = ev.reaction.by_asset(asset)
            if cell:
                lines.append(
                    f"  {asset:<12} {cell.direction.arrow:<3} conf {cell.confidence:.2f}"
                    f" - {cell.mechanism}"
                )
                if cell.caveat:
                    lines.append(f"               [{cell.caveat}]")
    else:
        lines.append("  UNKNOWN - no reaction map attached.")

    lines.append("")
    lines.append("SECOND-ORDER EFFECT")
    if ev.reaction is not None:
        from .reaction import analyse_orders
        oa = analyse_orders(ev.reaction)
        lines.append(f"  {oa.second_order}")
        lines.append("")
        lines.append("THIRD-ORDER RISK")
        lines.append(f"  {oa.third_order_risk}")
    else:
        lines.append("  UNKNOWN")

    lines.append("")
    lines.append("KEY LEVELS")
    if ev.key_levels:
        for k in ev.key_levels:
            lines.append(f"  - {k}")
    else:
        lines.append("  UNKNOWN - no price series supplied; levels are not invented here.")

    lines.append("")
    lines.append("TRADE IMPLICATION")
    lines.append(f"  {ev.trade_implication}")
    lines.append("")
    lines.append("INVALIDATION")
    lines.append(f"  {ev.invalidation}")
    lines.append("=" * 78)
    return "\n".join(lines)


__all__ = ["MacroEvent", "make_event", "render_alert"]
