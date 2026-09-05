"""Urgency, information-latency and priority scoring (spec sections 2, 16, 23).

The composite is documented rather than hidden because the weights are a
design choice, not a measured fact.  Credibility enters as a *multiplier*, not
as an addend: an anonymous claim of a rate cut must not outrank a confirmed
statistical release simply because its notional impact is large.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .types import Tier, Verification, clamp


class EventClass(str, Enum):
    SCHEDULED_STATISTIC = "SCHEDULED STATISTICAL RELEASE"
    SCHEDULED_POLICY = "SCHEDULED POLICY DECISION"
    POLICY_MINUTES = "POLICY MINUTES / TRANSCRIPT"
    OFFICIAL_SPEECH = "OFFICIAL SPEECH"
    PRESS_CONFERENCE = "PRESS CONFERENCE"
    GOVERNMENT_ANNOUNCEMENT = "GOVERNMENT ANNOUNCEMENT"
    PARLIAMENTARY = "PARLIAMENTARY / LEGISLATIVE"
    REGULATORY = "REGULATORY ANNOUNCEMENT"
    EMERGENCY_ACTION = "EMERGENCY POLICY ACTION"
    INTERVENTION = "FX / MARKET INTERVENTION"
    GEOPOLITICAL = "GEOPOLITICAL DEVELOPMENT"
    CORPORATE_SYSTEMIC = "CORPORATE / SYSTEMIC DEVELOPMENT"
    DATA_REVISION = "DATA REVISION"
    FUNDING_STRESS = "LIQUIDITY / FUNDING STRESS"
    CROSS_ASSET_ANOMALY = "CROSS-ASSET ANOMALY"
    AUCTION = "SOVEREIGN DEBT AUCTION"
    MARKET_EXPECTATION_SHIFT = "CHANGE IN MARKET EXPECTATIONS"


class UrgencyBand(str, Enum):
    EXTREME = "EXTREME"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFORMATIONAL = "INFORMATIONAL"


def band(score: float) -> UrgencyBand:
    if score >= 90:
        return UrgencyBand.EXTREME
    if score >= 75:
        return UrgencyBand.HIGH
    if score >= 50:
        return UrgencyBand.MEDIUM
    if score >= 25:
        return UrgencyBand.LOW
    return UrgencyBand.INFORMATIONAL


# --------------------------------------------------------------------------
# Information latency (spec section 16)
# --------------------------------------------------------------------------
#
# Latency here measures only how early information can become *publicly*
# detectable.  It is not, and must never be read as, a claim of privileged
# access.  A scheduled statistic scores low precisely because it is locked
# until the release instant and then reaches everyone at once.

_LATENCY_BASE: dict[EventClass, int] = {
    EventClass.SCHEDULED_STATISTIC: 10,
    EventClass.SCHEDULED_POLICY: 15,
    EventClass.POLICY_MINUTES: 20,
    EventClass.AUCTION: 25,
    EventClass.OFFICIAL_SPEECH: 50,
    EventClass.PRESS_CONFERENCE: 60,
    EventClass.PARLIAMENTARY: 60,
    EventClass.REGULATORY: 55,
    EventClass.GOVERNMENT_ANNOUNCEMENT: 60,
    EventClass.DATA_REVISION: 30,
    EventClass.CORPORATE_SYSTEMIC: 55,
    EventClass.GEOPOLITICAL: 70,
    EventClass.FUNDING_STRESS: 75,
    EventClass.CROSS_ASSET_ANOMALY: 80,
    EventClass.INTERVENTION: 75,
    EventClass.EMERGENCY_ACTION: 80,
    EventClass.MARKET_EXPECTATION_SHIFT: 65,
}

LATENCY_NOTE = (
    "Information latency scores how early a development can be detected from "
    "PUBLIC sources only. It is never a claim of privileged, embargoed or "
    "non-public access."
)


def information_latency(
    event_class: EventClass,
    *,
    live_streamed: bool = False,
    text_published_in_advance: bool = False,
    embargoed_release: bool = False,
) -> tuple[float, str]:
    """Return (0-100 latency score, one-line rationale)."""
    score = float(_LATENCY_BASE.get(event_class, 40))
    why = [f"base {score:.0f} for {event_class.value.lower()}"]
    if embargoed_release:
        score = min(score, 10.0)
        why.append("locked-file embargo: nobody sees it early, everyone at once")
    if live_streamed:
        score += 10
        why.append("live stream: audible before wire headlines clear")
    if text_published_in_advance:
        score += 10
        why.append("prepared text posted ahead of delivery")
    return clamp(score), "; ".join(why)


# --------------------------------------------------------------------------
# Credibility (spec sections 14, 15)
# --------------------------------------------------------------------------

_TIER_CREDIBILITY = {
    Tier.PRIMARY: 95.0,
    Tier.INSTITUTIONAL: 78.0,
    Tier.PROFESSIONAL: 58.0,
    Tier.SOCIAL: 25.0,
    Tier.UNKNOWN: 15.0,
}

_VERIFICATION_ADJ = {
    Verification.CONFIRMED: 5.0,
    Verification.OFFICIAL_PENDING: 0.0,
    Verification.PRELIMINARY: -5.0,
    Verification.REPORTED: -8.0,
    Verification.UNCONFIRMED: -30.0,
    Verification.DISPUTED: -45.0,
}


def credibility(
    tier: Tier,
    verification: Verification,
    *,
    independent_confirmations: int = 0,
    has_primary_document: bool = False,
    timestamp_clear: bool = True,
    source_has_error_history: bool = False,
) -> float:
    score = _TIER_CREDIBILITY.get(tier, 15.0)
    score += _VERIFICATION_ADJ.get(verification, -20.0)
    # Independent confirmations help, with diminishing returns and a cap:
    # ten copies of one unverified claim are still one claim.
    score += min(independent_confirmations, 3) * 6.0
    if has_primary_document:
        score += 10.0
    if not timestamp_clear:
        score -= 12.0
    if source_has_error_history:
        score -= 15.0
    return clamp(score)


# --------------------------------------------------------------------------
# Composite scores (spec section 23)
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class ScoreCard:
    market_impact: float
    surprise: float
    credibility: float
    information_latency: float
    expected_volatility: float
    directional_confidence: float
    urgency: float
    priority: float
    band: UrgencyBand
    rationale: tuple[str, ...]
    ok: bool = True

    def render(self) -> str:
        return (
            f"PRIORITY {self.priority:5.1f} | URGENCY {self.urgency:5.1f} "
            f"[{self.band.value}] | impact {self.market_impact:.0f} "
            f"surprise {self.surprise:.0f} cred {self.credibility:.0f} "
            f"latency {self.information_latency:.0f} vol {self.expected_volatility:.0f} "
            f"dir {self.directional_confidence:.0f}"
        )


# Weights for the additive core.  They sum to 1.0.
W_IMPACT = 0.36
W_SURPRISE = 0.26
W_VOL = 0.18
W_LATENCY = 0.10
W_DIRECTION = 0.10

# Credibility gate: an unverifiable claim keeps at most 25% of its raw score.
CRED_FLOOR = 0.25


def score_event(
    *,
    market_impact: float,
    surprise: float,
    credibility_score: float,
    information_latency_score: float,
    expected_volatility: float,
    directional_confidence: float,
    minutes_to_event: float | None = None,
    is_unscheduled: bool = False,
) -> ScoreCard:
    """Blend the six spec sub-scores into an urgency and a priority.

    ``minutes_to_event`` lifts urgency (not priority) as an event approaches:
    urgency answers "does this need attention now", priority answers "does
    this matter at all".
    """
    mi = clamp(market_impact)
    su = clamp(surprise)
    cr = clamp(credibility_score)
    il = clamp(information_latency_score)
    ev = clamp(expected_volatility)
    dc = clamp(directional_confidence)

    core = W_IMPACT * mi + W_SURPRISE * su + W_VOL * ev + W_LATENCY * il + W_DIRECTION * dc
    cred_factor = CRED_FLOOR + (1.0 - CRED_FLOOR) * (cr / 100.0)
    priority = clamp(core * cred_factor)

    rationale = [
        f"core {core:.1f} = {W_IMPACT}*impact + {W_SURPRISE}*surprise + "
        f"{W_VOL}*vol + {W_LATENCY}*latency + {W_DIRECTION}*direction",
        f"credibility multiplier {cred_factor:.2f} (floor {CRED_FLOOR}) -> priority {priority:.1f}",
    ]

    urgency = priority
    if is_unscheduled:
        urgency = clamp(urgency + 8.0)
        rationale.append("unscheduled development: +8 urgency, markets have not pre-positioned")
    if minutes_to_event is not None:
        if minutes_to_event <= 0:
            bump = 12.0 if minutes_to_event > -60 else 0.0
            label = "in progress / just released"
        elif minutes_to_event <= 5:
            bump, label = 15.0, "T-5"
        elif minutes_to_event <= 15:
            bump, label = 12.0, "T-15"
        elif minutes_to_event <= 30:
            bump, label = 9.0, "T-30"
        elif minutes_to_event <= 60:
            bump, label = 6.0, "T-60"
        elif minutes_to_event <= 24 * 60:
            bump, label = 2.0, "same session"
        else:
            bump, label = 0.0, "beyond the session"
        if bump:
            rationale.append(f"proximity {label}: +{bump:.0f} urgency")
        urgency = clamp(urgency + bump)

    return ScoreCard(
        market_impact=mi,
        surprise=su,
        credibility=cr,
        information_latency=il,
        expected_volatility=ev,
        directional_confidence=dc,
        urgency=urgency,
        priority=priority,
        band=band(urgency),
        rationale=tuple(rationale),
    )


__all__ = [
    "EventClass", "LATENCY_NOTE", "ScoreCard", "UrgencyBand", "band",
    "credibility", "information_latency", "score_event",
]
