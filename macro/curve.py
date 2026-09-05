"""Yield-curve intelligence (spec section 11).

Classifies the four canonical curve moves and states what each is *potentially*
pricing.  It refuses to classify a move smaller than the noise threshold, and
it separates nominal from real: without breakevens, a nominal move cannot be
attributed to growth, inflation or term premium, and the module says so rather
than picking one.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .types import Category, Insufficient, Observation, insufficient, unknown


class CurveMove(str, Enum):
    BULL_STEEPENING = "BULL STEEPENING"
    BULL_FLATTENING = "BULL FLATTENING"
    BEAR_STEEPENING = "BEAR STEEPENING"
    BEAR_FLATTENING = "BEAR FLATTENING"
    UNCHANGED = "UNCHANGED / WITHIN NOISE"


# Below this, a move is not a regime signal.  2bp on the 2s10s is intraday
# noise in normal conditions.
NOISE_BP = 2.0


@dataclass(frozen=True)
class CurveRead:
    move: CurveMove
    d2y_bp: float
    d10y_bp: float
    d30y_bp: float | None
    slope_2s10s_bp: float | None
    d_slope_2s10s_bp: float
    d_slope_5s30s_bp: float | None
    real_yield_note: str
    breakeven_note: str
    pricing: tuple[str, ...]          # what the move is potentially pricing
    dominant_leg: str
    caveats: tuple[str, ...]
    category: Category = Category.INTERPRETATION
    ok: bool = True

    def render(self) -> str:
        return (
            f"{self.move.value}: 2y {self.d2y_bp:+.1f}bp, 10y {self.d10y_bp:+.1f}bp, "
            f"2s10s {self.d_slope_2s10s_bp:+.1f}bp ({self.dominant_leg} leg driving)"
        )


def _bp(now: Observation, prior: Observation) -> float | None:
    """Change in basis points. Both legs must be in percent."""
    if not (now.known and prior.known):
        return None
    if now.unit != prior.unit:
        raise ValueError(f"yield unit mismatch: {now.unit} vs {prior.unit}")
    scale = 100.0 if now.unit in ("pct", "percent", "%") else 1.0
    return (now.require("y") - prior.require("y")) * scale


def classify(
    *,
    y2_now: Observation,
    y2_prior: Observation,
    y10_now: Observation,
    y10_prior: Observation,
    y5_now: Observation | None = None,
    y5_prior: Observation | None = None,
    y30_now: Observation | None = None,
    y30_prior: Observation | None = None,
    real10_now: Observation | None = None,
    real10_prior: Observation | None = None,
    breakeven10_now: Observation | None = None,
    breakeven10_prior: Observation | None = None,
) -> CurveRead | Insufficient:
    d2 = _bp(y2_now, y2_prior)
    d10 = _bp(y10_now, y10_prior)
    if d2 is None or d10 is None:
        return insufficient(
            "curve classification needs both a 2y and a 10y change",
            *( ["2y"] if d2 is None else [] ), *( ["10y"] if d10 is None else [] ),
        )
    d30 = _bp(y30_now, y30_prior) if (y30_now and y30_prior) else None
    d5 = _bp(y5_now, y5_prior) if (y5_now and y5_prior) else None

    d_slope = d10 - d2                      # 2s10s change
    d_slope_5s30 = (d30 - d5) if (d30 is not None and d5 is not None) else None

    slope_level = None
    if y2_now.known and y10_now.known:
        slope_level = (y10_now.require("10y") - y2_now.require("2y")) * 100.0

    caveats: list[str] = []
    dominant = "long" if abs(d10) >= abs(d2) else "front"

    if abs(d2) < NOISE_BP and abs(d10) < NOISE_BP:
        move = CurveMove.UNCHANGED
        caveats.append(f"both legs moved less than {NOISE_BP:.0f}bp: no regime signal")
    else:
        # Direction is set by the leg that actually moved.
        driver = d10 if dominant == "long" else d2
        bull = driver < 0
        steepening = d_slope > 0
        if bull and steepening:
            move = CurveMove.BULL_STEEPENING
        elif bull and not steepening:
            move = CurveMove.BULL_FLATTENING
        elif not bull and steepening:
            move = CurveMove.BEAR_STEEPENING
        else:
            move = CurveMove.BEAR_FLATTENING
        if (d2 > 0) != (d10 > 0):
            caveats.append(
                "legs moved in opposite directions: the bull/bear label follows the "
                f"larger move ({dominant} end) and is weaker than usual"
            )

    pricing = _pricing(move, dominant)

    # Real vs nominal decomposition
    d_real = _bp(real10_now, real10_prior) if (real10_now and real10_prior) else None
    d_be = _bp(breakeven10_now, breakeven10_prior) if (breakeven10_now and breakeven10_prior) else None
    if d_real is None and d_be is None:
        real_note = (
            "UNKNOWN - no TIPS/real-yield input. A nominal move alone cannot be "
            "attributed to growth, inflation expectations or term premium."
        )
        be_note = "UNKNOWN - no breakeven input."
        caveats.append(
            "attribution suppressed: supply 10y real yields and breakevens to "
            "separate the inflation-expectations channel from the real-rate channel"
        )
    else:
        real_note = f"10y real yield {d_real:+.1f}bp" if d_real is not None else "10y real yield UNKNOWN"
        be_note = f"10y breakeven {d_be:+.1f}bp" if d_be is not None else "10y breakeven UNKNOWN"
        if d_real is not None and d_be is not None:
            if abs(d_real) > abs(d_be):
                pricing = pricing + (
                    "Real rates are driving: this is a growth/policy-path move, and it "
                    "transmits directly into equity discount rates and gold.",
                )
            else:
                pricing = pricing + (
                    "Breakevens are driving: this is an inflation-expectations move; "
                    "gold and breakeven-sensitive assets should respond more than "
                    "long-duration equity.",
                )

    caveats.append(
        "Curve moves are joint outcomes of policy expectations, term premium and "
        "supply. Without a term-premium estimate the split is not identified."
    )

    return CurveRead(
        move=move, d2y_bp=d2, d10y_bp=d10, d30y_bp=d30,
        slope_2s10s_bp=slope_level, d_slope_2s10s_bp=d_slope,
        d_slope_5s30s_bp=d_slope_5s30,
        real_yield_note=real_note, breakeven_note=be_note,
        pricing=pricing, dominant_leg=dominant, caveats=tuple(caveats),
    )


def _pricing(move: CurveMove, dominant: str) -> tuple[str, ...]:
    if move is CurveMove.BULL_STEEPENING:
        return (
            "Front end rallying faster than the long end: the market is pulling "
            "rate cuts forward.",
            "Classic pre-easing or growth-scare configuration; historically the "
            "recessionary variant of steepening, as opposed to the supply-driven one.",
            "Watch whether it is driven by a weakening labour signal (genuine) or by "
            "a single soft print (fadeable).",
        )
    if move is CurveMove.BULL_FLATTENING:
        return (
            "Long end rallying harder than the front: duration demand, safe-haven "
            "bid, or a downgrade to long-run growth/inflation.",
            "Consistent with risk-off flight to quality, or with the market accepting "
            "that policy will stay restrictive long enough to break growth.",
        )
    if move is CurveMove.BEAR_STEEPENING:
        return (
            "Long end selling off harder than the front: term premium, fiscal supply, "
            "or a rise in long-run inflation compensation.",
            "This is the configuration that tightens financial conditions without any "
            "policy action, and the one most hostile to long-duration equity and gold "
            "when it is real-rate driven.",
            "Check the auction calendar: coupon supply and QT can produce this without "
            "any macro news at all.",
        )
    if move is CurveMove.BEAR_FLATTENING:
        return (
            "Front end selling off harder: the market is pricing out cuts or pricing "
            "in hikes.",
            "Typical response to an upside inflation or labour surprise; the most "
            "direct expression of a hawkish repricing.",
            "Sustained bear flattening into inversion is the market saying policy is "
            "restrictive enough to force a later slowdown.",
        )
    return ("No material move; nothing is being repriced at the curve level.",)


__all__ = ["NOISE_BP", "CurveMove", "CurveRead", "classify"]
