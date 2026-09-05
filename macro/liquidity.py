"""Liquidity, funding and market-structure radar (spec sections 10 and 12).

Two jobs:

1.  Classify the funding/risk regime from whatever indicators are actually
    supplied, and report how much of the panel was observable.  A RISK-ON call
    made on two of eleven inputs is labelled as such.

2.  Flag price action that moved without an identifying headline.  When it
    does, this module lists *candidate* explanations with confidence weights
    and explicitly refuses to name a cause.  Inventing the reason for an
    unexplained move is the single most damaging thing a news system can do.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .regime import RiskRegime
from .types import Category, Insufficient, Observation, clamp, insufficient, unknown


# Each indicator maps to a signed contribution: +1 means "a rise in this
# indicator is risk-positive", -1 means "a rise is risk-negative".
STRESS_SIGN: dict[str, int] = {
    "vix": -1,
    "move_index": -1,
    "hy_oas_bp": -1,
    "ig_oas_bp": -1,
    "sofr_effr_spread_bp": -1,
    "cross_ccy_basis_bp": +1,      # more negative basis = more dollar stress
    "sofr_iorb_spread_bp": -1,
    "srf_usage_bn": -1,
    "dxy": -1,                     # a bid dollar is a tightening impulse
    "spx_pct": +1,
    "hyg_lqd_ratio": +1,
    "btc_pct": +1,
    "gold_pct": 0,                 # ambiguous: real-rate AND haven asset
    "reserve_balances_bn": +1,
    "rrp_bn": 0,                   # direction depends on the funding phase
    "cb_balance_sheet_bn": +1,
}

# Thresholds beyond which a level (not a change) is itself an alarm.
HARD_ALARMS: dict[str, tuple[str, float, str]] = {
    "vix": (">", 30.0, "equity vol at crisis-adjacent levels"),
    "hy_oas_bp": (">", 500.0, "high-yield spreads at recession-pricing levels"),
    "sofr_effr_spread_bp": (">", 25.0, "repo printing well through the policy rate: collateral scarcity"),
    "sofr_iorb_spread_bp": (">", 10.0, "SOFR above IORB: reserves no longer abundant"),
    "cross_ccy_basis_bp": ("<", -50.0, "dollar funding premium: offshore USD scarcity"),
    "srf_usage_bn": (">", 5.0, "standing repo facility in genuine use, not testing"),
}


@dataclass(frozen=True)
class ConditionsRead:
    regime: RiskRegime
    score: float                  # -100 (stress) .. +100 (risk-on)
    observed_inputs: int
    total_inputs: int
    coverage: float               # 0..1
    alarms: tuple[str, ...]
    contributions: tuple[tuple[str, float, str], ...]
    missing: tuple[str, ...]
    confidence: float
    caveats: tuple[str, ...]
    category: Category = Category.INTERPRETATION
    ok: bool = True

    def render(self) -> str:
        return (
            f"{self.regime.value} (score {self.score:+.1f}, coverage "
            f"{self.coverage:.0%} on {self.observed_inputs}/{self.total_inputs} inputs, "
            f"confidence {self.confidence:.2f})"
            + (f" | ALARMS: {'; '.join(self.alarms)}" if self.alarms else "")
        )


def assess(
    levels: dict[str, Observation] | None = None,
    changes_z: dict[str, float] | None = None,
) -> ConditionsRead | Insufficient:
    """Classify the funding/risk regime.

    ``levels`` are current readings keyed by the names in ``STRESS_SIGN``.
    ``changes_z`` are standardised daily changes for the same keys, supplied by
    the caller from its own history.  Levels drive the hard alarms; z-scored
    changes drive the score.
    """
    levels = levels or {}
    changes_z = changes_z or {}

    known_levels = {k: v for k, v in levels.items() if v is not None and v.known}
    seen = set(known_levels) | set(changes_z)
    if not seen:
        return insufficient(
            "no liquidity or risk indicators supplied; regime cannot be inferred "
            "and will not be guessed",
            "levels", "changes_z",
        )

    alarms: list[str] = []
    for key, (op, thr, why) in HARD_ALARMS.items():
        obs = known_levels.get(key)
        if obs is None:
            continue
        v = obs.require(key)
        if (op == ">" and v > thr) or (op == "<" and v < thr):
            alarms.append(f"{key}={v:g} {op} {thr:g} ({why})")

    contributions: list[tuple[str, float, str]] = []
    total = 0.0
    weight = 0.0
    for key, z in changes_z.items():
        sign = STRESS_SIGN.get(key)
        if sign is None:
            continue
        if sign == 0:
            contributions.append((key, 0.0, "ambiguous sign: excluded from the score"))
            continue
        contrib = sign * max(-3.0, min(3.0, float(z)))
        total += contrib
        weight += 1.0
        direction = "risk-positive" if contrib > 0 else "risk-negative"
        contributions.append((key, contrib, f"{z:+.2f}s move, {direction}"))

    score = (total / weight) * 33.3 if weight else 0.0
    score = max(-100.0, min(100.0, score))

    total_inputs = len(STRESS_SIGN)
    observed = len(seen & set(STRESS_SIGN))
    coverage = observed / total_inputs

    if alarms and (score < 0 or len(alarms) >= 2):
        regime = RiskRegime.LIQUIDITY_STRESS
    elif not weight:
        regime = RiskRegime.UNKNOWN
    elif score >= 25:
        regime = RiskRegime.RISK_ON
    elif score <= -25:
        regime = RiskRegime.RISK_OFF
    else:
        regime = RiskRegime.MIXED

    confidence = clamp(coverage * 100.0, 0, 90) / 100.0
    caveats = [
        "Regime is inferred from the supplied panel only; unobserved indicators "
        "cannot be assumed benign.",
    ]
    if coverage < 0.4:
        caveats.append(
            f"Thin panel ({observed}/{total_inputs}): this is a directional hint, "
            "not a financial-conditions read."
        )
    if alarms and regime is not RiskRegime.LIQUIDITY_STRESS:
        caveats.append(
            "A hard alarm tripped while the aggregate score stayed benign - "
            "check whether the stress is idiosyncratic to one funding market."
        )
    if any(k in changes_z for k in ("rrp_bn", "gold_pct")):
        caveats.append(
            "Ambiguous-sign inputs (RRP, gold) were excluded from the score rather "
            "than assigned a convenient direction."
        )

    return ConditionsRead(
        regime=regime, score=score, observed_inputs=observed,
        total_inputs=total_inputs, coverage=coverage, alarms=tuple(alarms),
        contributions=tuple(contributions),
        missing=tuple(sorted(set(STRESS_SIGN) - seen)),
        confidence=round(confidence, 2), caveats=tuple(caveats),
    )


# --------------------------------------------------------------------------
# Unexplained-move detector (spec section 10)
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class AnomalyFlag:
    asset: str
    move_z: float
    window_minutes: int
    headline_found: bool
    verdict: str
    candidate_explanations: tuple[tuple[str, float], ...]
    instruction: str
    category: Category = Category.SPECULATION
    ok: bool = True

    def render(self) -> str:
        cands = "\n    ".join(f"{p:>4.0%}  {c}" for c, p in self.candidate_explanations)
        return f"{self.verdict}\n  {self.asset} {self.move_z:+.2f}s over {self.window_minutes}m\n    {cands}"


ANOMALY_Z = 2.5


def detect_anomaly(
    asset: str,
    move_z: float,
    *,
    window_minutes: int = 15,
    headline_found: bool = False,
    volume_z: float | None = None,
    correlated_assets_moved: bool | None = None,
    scheduled_event_within_minutes: int | None = None,
) -> AnomalyFlag | None:
    """Flag a move that is large relative to its own recent distribution.

    Returns None when the move is inside normal dispersion.  When it fires, it
    NEVER names a cause: it enumerates candidates with weights that sum to 1
    and hands the verification job back to the operator.
    """
    if abs(move_z) < ANOMALY_Z:
        return None

    if headline_found:
        verdict = "LARGE MOVE WITH IDENTIFIED HEADLINE - normal repricing"
    else:
        verdict = "POTENTIAL INFORMATION-DRIVEN MOVE - cause NOT identified"

    cands: list[tuple[str, float]] = []
    if headline_found:
        cands.append(("Known headline already on the wires is the cause", 0.70))
        cands.append(("Headline is coincidental; flow is the real driver", 0.30))
    else:
        base = [
            ("Positioning / stop-loss cascade with no new information", 0.24),
            ("Liquidity gap: thin book absorbing an ordinary-sized order", 0.22),
            ("Information not yet on the wires (embargo break, delegate briefing, "
             "regional wire, non-English source)", 0.18),
            ("Cross-asset transmission from a move that started elsewhere", 0.16),
            ("Systematic/CTA or index-rebalance flow", 0.12),
            ("Erroneous print or feed artefact", 0.08),
        ]
        if scheduled_event_within_minutes is not None and scheduled_event_within_minutes <= 30:
            base.insert(0, (
                f"Pre-positioning into a scheduled event {scheduled_event_within_minutes}m away",
                0.20,
            ))
        if correlated_assets_moved is False:
            base = [(c, p * (1.6 if "Liquidity gap" in c or "Erroneous" in c else 0.85))
                    for c, p in base]
        if correlated_assets_moved is True:
            base = [(c, p * (1.5 if "Cross-asset" in c or "Information not yet" in c else 0.9))
                    for c, p in base]
        if volume_z is not None and volume_z > 2.0:
            base = [(c, p * (0.5 if "Liquidity gap" in c else 1.15)) for c, p in base]
        total = sum(p for _, p in base)
        cands = [(c, p / total) for c, p in base]
        cands.sort(key=lambda cp: -cp[1])

    return AnomalyFlag(
        asset=asset,
        move_z=move_z,
        window_minutes=window_minutes,
        headline_found=headline_found,
        verdict=verdict,
        candidate_explanations=tuple(cands),
        instruction=(
            "Do not assign a cause without a primary or Tier-2 source. Check, in "
            "order: (1) the issuing agency or central-bank site directly, (2) "
            "non-English regional wires, (3) the exchange notice feed, (4) whether "
            "correlated instruments confirm. If none confirms, treat the move as "
            "flow until proven otherwise."
        ),
    )


__all__ = [
    "ANOMALY_Z", "AnomalyFlag", "ConditionsRead", "HARD_ALARMS", "STRESS_SIGN",
    "assess", "detect_anomaly",
]
