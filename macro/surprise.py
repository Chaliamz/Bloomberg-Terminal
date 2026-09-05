"""Expectation-vs-actual engine (spec sections 4 and 17).

Two deliberate refusals live here:

1.  The standardised surprise is only produced when a *supplied* history of
    past (actual - consensus) errors exists.  There is no built-in table of
    "typical" surprise volatilities, because inventing one would put a
    fabricated denominator under every z-score in the system.

2.  A "strong" number is never labelled bullish.  The engine emits an
    *economic impulse* (growth/inflation direction) and leaves the market
    mapping to :mod:`macro.reaction`, which needs the prevailing regime.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .types import (
    Category, Insufficient, Observation, clamp, insufficient, same_unit, stdev,
)


class SurpriseClass(str, Enum):
    MAJOR_POSITIVE = "MAJOR POSITIVE SURPRISE"
    MODERATE_POSITIVE = "MODERATE POSITIVE SURPRISE"
    NEUTRAL = "NEUTRAL / IN LINE"
    MODERATE_NEGATIVE = "MODERATE NEGATIVE SURPRISE"
    MAJOR_NEGATIVE = "MAJOR NEGATIVE SURPRISE"


class Impulse(str, Enum):
    """Direction of the shock in macro space, not in price space."""

    GROWTH_STRONGER = "GROWTH IMPULSE STRONGER"
    GROWTH_WEAKER = "GROWTH IMPULSE WEAKER"
    INFLATION_HOTTER = "INFLATION IMPULSE HOTTER"
    INFLATION_COOLER = "INFLATION IMPULSE COOLER"
    MIXED = "MIXED / OFFSETTING"
    NEUTRAL = "NO MATERIAL IMPULSE"


@dataclass(frozen=True)
class IndicatorSpec:
    """Structural metadata about a release.  No values, only semantics."""

    code: str
    label: str
    country: str
    unit: str
    # +1 when a higher print means a structurally stronger economy, -1 when a
    # higher print means a weaker one (unemployment rate, jobless claims).
    strength_sign: int
    # +1 when a higher print is more inflationary, -1 less, 0 not applicable.
    inflation_sign: int = 0
    agency: str = ""
    revision_prone: bool = False

    def __post_init__(self) -> None:
        if self.strength_sign not in (-1, 0, 1):
            raise ValueError(f"{self.code}: strength_sign must be -1, 0 or 1")
        if self.inflation_sign not in (-1, 0, 1):
            raise ValueError(f"{self.code}: inflation_sign must be -1, 0 or 1")


@dataclass(frozen=True)
class SurpriseResult:
    indicator: IndicatorSpec
    actual: Observation
    consensus: Observation
    previous: Observation
    revised_previous: Observation
    market_implied: Observation
    absolute_surprise: float
    unit: str
    standardized_surprise: float | None
    sigma_used: float | None
    sigma_sample: int
    classification: SurpriseClass
    impulse: Impulse
    revision_delta: float | None
    momentum_delta: float | None
    surprise_score: float           # 0-100, for the priority engine
    notes: tuple[str, ...]
    category: Category = Category.FACT
    ok: bool = True

    def render(self) -> str:
        z = "n/a" if self.standardized_surprise is None else f"{self.standardized_surprise:+.2f}s"
        return (
            f"{self.indicator.label}: actual {self.actual.render()} vs cons "
            f"{self.consensus.render()} -> {self.absolute_surprise:+.3f} {self.unit} "
            f"({z}) {self.classification.value}; {self.impulse.value}"
        )


# Standardised-surprise band edges, in sigmas.  A design choice, stated so it
# can be challenged: |z| < 0.5 is inside normal forecast dispersion, |z| >= 1.5
# is the tail that historically forces a repricing.
BAND_MODERATE = 0.5
BAND_MAJOR = 1.5
# Fallback bands when sigma is unavailable, expressed as a fraction of the
# absolute consensus level.  Used only to classify, never to fake a z-score.
REL_MODERATE = 0.10
REL_MAJOR = 0.30


def evaluate(
    spec: IndicatorSpec,
    actual: Observation,
    consensus: Observation,
    previous: Observation | None = None,
    revised_previous: Observation | None = None,
    market_implied: Observation | None = None,
    surprise_history: list[float] | None = None,
) -> SurpriseResult | Insufficient:
    """Compute the full surprise picture for one release.

    ``surprise_history`` is a list of past (actual - consensus) values in the
    indicator's own unit.  Supply at least 8 for a usable sigma.
    """
    from .types import unknown

    previous = previous or unknown(spec.unit)
    revised_previous = revised_previous or unknown(spec.unit)
    market_implied = market_implied or unknown(spec.unit)

    # Spec-unit check first: a caller passing the wrong series entirely is a
    # different (and more likely) error than mixing units between two sides.
    if actual.known and actual.unit != spec.unit:
        return insufficient(
            f"unit mismatch: {spec.code} is defined in '{spec.unit}' but the "
            f"actual arrived as '{actual.unit}'"
        )
    same_unit(actual, consensus, previous, revised_previous)

    missing = [n for n, o in (("actual", actual), ("consensus", consensus)) if not o.known]
    if missing:
        return insufficient("cannot compute a surprise without both sides", *missing)

    a = actual.require("actual")
    c = consensus.require("consensus")
    abs_surprise = a - c

    notes: list[str] = []

    # --- standardised surprise -------------------------------------------
    sigma: float | None = None
    sample = 0
    if surprise_history:
        clean = [float(x) for x in surprise_history if x is not None]
        sample = len(clean)
        if sample >= 8:
            sigma = stdev(clean)
            if sigma is None:
                notes.append(
                    "supplied surprise history has zero dispersion; z-score suppressed"
                )
        else:
            notes.append(
                f"surprise history too short ({sample} obs, need 8); z-score suppressed"
            )
    else:
        notes.append(
            "no surprise history supplied; standardised surprise is UNKNOWN "
            "(no built-in sigma table exists by design)"
        )

    z = (abs_surprise / sigma) if sigma else None

    # --- classification ---------------------------------------------------
    if z is not None:
        mag = abs(z)
        if mag >= BAND_MAJOR:
            strength = 2
        elif mag >= BAND_MODERATE:
            strength = 1
        else:
            strength = 0
    else:
        denom = abs(c)
        if denom < 1e-9:
            notes.append(
                "consensus is ~0 and no sigma is available; magnitude cannot be "
                "scaled, classification limited to sign"
            )
            strength = 1 if abs(abs_surprise) > 0 else 0
        else:
            rel = abs(abs_surprise) / denom
            strength = 2 if rel >= REL_MAJOR else (1 if rel >= REL_MODERATE else 0)
        notes.append("classification uses a relative-to-consensus fallback, not a z-score")

    if strength == 0:
        classification = SurpriseClass.NEUTRAL
    elif abs_surprise > 0:
        classification = (
            SurpriseClass.MAJOR_POSITIVE if strength == 2 else SurpriseClass.MODERATE_POSITIVE
        )
    else:
        classification = (
            SurpriseClass.MAJOR_NEGATIVE if strength == 2 else SurpriseClass.MODERATE_NEGATIVE
        )

    # --- macro impulse (NOT a market call) --------------------------------
    impulse = _impulse(spec, abs_surprise, strength)

    # --- revisions and momentum -------------------------------------------
    revision_delta = None
    if previous.known and revised_previous.known:
        revision_delta = revised_previous.require("revised") - previous.require("previous")
        if abs(revision_delta) > 0:
            notes.append(
                f"prior print revised by {revision_delta:+.3f} {spec.unit}; the revision "
                "can dominate the headline surprise"
            )
    momentum_base = revised_previous if revised_previous.known else previous
    momentum_delta = (a - momentum_base.require("previous")) if momentum_base.known else None

    if market_implied.known:
        gap = c - market_implied.require("market_implied")
        if abs(gap) > 0:
            notes.append(
                f"economist consensus sits {gap:+.3f} {spec.unit} away from the "
                "market-implied expectation; the market number is what gets repriced"
            )
    else:
        notes.append("market-implied expectation UNKNOWN; surprise is measured vs economists only")

    if spec.revision_prone:
        notes.append("series is revision-prone: treat the first print as provisional")

    score = _surprise_score(z, strength)

    return SurpriseResult(
        indicator=spec,
        actual=actual,
        consensus=consensus,
        previous=previous,
        revised_previous=revised_previous,
        market_implied=market_implied,
        absolute_surprise=abs_surprise,
        unit=spec.unit,
        standardized_surprise=z,
        sigma_used=sigma,
        sigma_sample=sample,
        classification=classification,
        impulse=impulse,
        revision_delta=revision_delta,
        momentum_delta=momentum_delta,
        surprise_score=score,
        notes=tuple(notes),
    )


def _impulse(spec: IndicatorSpec, abs_surprise: float, strength: int) -> Impulse:
    if strength == 0:
        return Impulse.NEUTRAL
    infl = spec.inflation_sign * (1 if abs_surprise > 0 else -1)
    grow = spec.strength_sign * (1 if abs_surprise > 0 else -1)
    if spec.inflation_sign != 0 and spec.strength_sign != 0:
        return Impulse.MIXED
    if spec.inflation_sign != 0:
        return Impulse.INFLATION_HOTTER if infl > 0 else Impulse.INFLATION_COOLER
    if spec.strength_sign != 0:
        return Impulse.GROWTH_STRONGER if grow > 0 else Impulse.GROWTH_WEAKER
    return Impulse.NEUTRAL


def _surprise_score(z: float | None, strength: int) -> float:
    """0-100 surprise component for the priority engine."""
    if z is not None:
        # 0s -> 0, 1s -> 40, 2s -> 70, 3s+ -> ~90
        return clamp(100.0 * (1.0 - 2.718281828 ** (-abs(z) / 1.6)))
    return {0: 10.0, 1: 45.0, 2: 70.0}[strength]


def surprise_distribution(
    spec: IndicatorSpec, consensus: Observation, sigma: float | None
) -> dict[str, str]:
    """Spec section 17: what would count as mild / moderate / extreme.

    Returns UNKNOWN strings rather than invented thresholds when sigma is absent.
    """
    if not consensus.known:
        return {k: "UNKNOWN - consensus not supplied" for k in ("mild", "moderate", "extreme")}
    c = consensus.require("consensus")
    if not sigma:
        return {
            "mild": "UNKNOWN - requires supplied surprise history",
            "moderate": "UNKNOWN - requires supplied surprise history",
            "extreme": "UNKNOWN - requires supplied surprise history",
        }
    return {
        "mild": f"{c - BAND_MODERATE * sigma:.2f} to {c + BAND_MODERATE * sigma:.2f} {spec.unit}",
        "moderate": (
            f"{c - BAND_MAJOR * sigma:.2f} to {c - BAND_MODERATE * sigma:.2f} or "
            f"{c + BAND_MODERATE * sigma:.2f} to {c + BAND_MAJOR * sigma:.2f} {spec.unit}"
        ),
        "extreme": (
            f"below {c - BAND_MAJOR * sigma:.2f} or above "
            f"{c + BAND_MAJOR * sigma:.2f} {spec.unit}"
        ),
    }


__all__ = [
    "Impulse", "IndicatorSpec", "SurpriseClass", "SurpriseResult", "evaluate",
    "surprise_distribution",
]
