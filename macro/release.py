"""Actual-vs-expected for a statistical release, and the verdict that follows.

The terminal already had a countdown to each release and a flag that flipped to
RELEASED when the clock passed.  That is a *schedule*, not intelligence: it says
a number exists, never what the number was or what it meant.  This module closes
that gap under the same no-fabrication contract as the rest of the system.

Three refusals are deliberate and are the whole point:

1.  An :class:`Expectation` cannot be constructed without a source, a tier and a
    timestamp for the actual, and a separately-named carrier for the consensus.
    A consensus with no carrier is somebody's memory of a consensus.

2.  A print is mapped to exactly **one** transmission channel - policy or growth
    - and an expectation that claims both is rejected at construction.  A number
    that moves risk through two channels at once needs two rows, each with its
    own reasoning, not one row with a blended verdict nobody can audit.

3.  The market verdict is **regime-conditional and refused when the regime is
    unknown**.  "Hot inflation is bearish" is only true given a central bank that
    reacts to it; under a different regime the same print reads differently.
    :func:`assess` returns :class:`~macro.types.Insufficient` rather than guess.

And one thing this module deliberately does **not** own: the mapping from an
impulse to an asset direction.  That already exists in :mod:`macro.reaction`,
which is regime-conditional, explains its chain of reasoning and is tested.  An
independent copy of it here would be a second opinion inside one system - and
the two immediately disagreed in review, on whether weak growth under an
inflation-dominant regime is bought or is ambiguous.  :func:`assess` therefore
reads the S&P cell out of :func:`macro.reaction.build_matrix` and translates its
direction, so there is exactly one reaction function in this codebase.

The tolerance band is a stated design choice, never a silent one.  Most price
indices are published to the same precision the consensus is quoted at, so the
band is zero and any difference at all is a surprise.  Weekly jobless claims are
the exception and say so in their own note.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime

from .reaction import Direction, MacroRegime, build_matrix
from .surprise import Impulse
from .types import Insufficient, insufficient

__all__ = [
    "Expectation", "Forecast", "Verdict", "assess", "roll_up", "fmt_value",
    "ABOVE", "BELOW", "IN_LINE",
    "BULLISH", "BEARISH", "NEUTRAL", "MIXED",
]


# Direction of the print against its consensus.  Purely arithmetic: no view.
ABOVE = "ABOVE"
BELOW = "BELOW"
IN_LINE = "IN LINE"

# Verdict for *risk assets* (equities, crypto).  Bonds and the dollar take the
# opposite sign through the policy channel; that inversion is stated in `why`
# rather than crammed into the label.
BULLISH = "BULLISH"
BEARISH = "BEARISH"
NEUTRAL = "NEUTRAL"
MIXED = "MIXED"

# Comparisons are done on floats parsed from published decimals, so 0.2 - 0.3
# is -0.09999999999999998 and 5.4 - 5.3 is 0.10000000000000053.  Without this
# slack a tolerance of exactly 0.1 would classify the second as a surprise and
# the first as in line, which is the sort of bug that never shows up in review.
EPS = 1e-9

# Transmission channels.  Exactly one per expectation.
POLICY = "policy"
GROWTH = "growth"

NO_IMPULSE = "NO MATERIAL SURPRISE"

# The asset whose direction IS the risk read. Equities rather than crypto: the
# reaction map gives BTC a wider band and lower confidence, and a headline
# verdict should be taken from the instrument the mapping is most certain about.
RISK_PROXY = "S&P 500"

REGIMES = {"INFLATION": MacroRegime.INFLATION_DOMINANT,
           "GROWTH": MacroRegime.GROWTH_DOMINANT}

RISK_FROM_DIRECTION = {
    Direction.STRONG_UP: BULLISH, Direction.UP: BULLISH, Direction.MILD_UP: BULLISH,
    Direction.STRONG_DOWN: BEARISH, Direction.DOWN: BEARISH,
    Direction.MILD_DOWN: BEARISH,
    Direction.FLAT: NEUTRAL, Direction.AMBIGUOUS: MIXED,
}


@dataclass(frozen=True)
class Expectation:
    """One published figure beside the number the market was carrying for it."""

    metric: str                 # "Headline YoY", "Core MoM"
    actual: float
    consensus: float
    unit: str                   # "pct", "k", "index"
    source: str                 # carrier of the ACTUAL
    tier: int
    as_of: str                  # ISO8601 Z, the release instant
    consensus_source: str       # carrier of the CONSENSUS - a different claim
    # +1 when a higher print pushes policy tighter (any price index, a policy
    # rate).  Mutually exclusive with growth_sign.
    hawkish_sign: int = 0
    # +1 when a higher print means a structurally stronger economy, -1 when it
    # means a weaker one (jobless claims, unemployment).
    growth_sign: int = 0
    previous: float | None = None
    tolerance: float = 0.0
    note: str = ""

    def __post_init__(self) -> None:
        if not self.metric.strip():
            raise ValueError("a print without a metric name is not representable")
        if not self.source.strip():
            raise ValueError(f"{self.metric}: the actual needs a source")
        if not self.consensus_source.strip():
            raise ValueError(
                f"{self.metric}: the consensus needs its own carrier - a consensus "
                f"with no source is somebody's memory of a consensus")
        if self.tier not in (1, 2, 3, 4):
            raise ValueError(f"{self.metric}: tier must be 1-4, got {self.tier}")
        if not self.unit.strip():
            raise ValueError(f"{self.metric}: unit is mandatory")
        try:
            datetime.strptime(self.as_of, "%Y-%m-%dT%H:%M:%SZ")
        except ValueError as exc:
            raise ValueError(f"{self.metric}: as_of must be ISO8601 Z: {exc}") from exc
        for name, sign in (("hawkish_sign", self.hawkish_sign),
                           ("growth_sign", self.growth_sign)):
            if sign not in (-1, 0, 1):
                raise ValueError(f"{self.metric}: {name} must be -1, 0 or 1")
        if self.hawkish_sign and self.growth_sign:
            raise ValueError(
                f"{self.metric}: a print carries exactly one transmission channel; "
                f"one that moves risk through both needs two rows, each with its "
                f"own reasoning")
        if self.tolerance < 0:
            raise ValueError(f"{self.metric}: tolerance cannot be negative")
        for name, v in (("actual", self.actual), ("consensus", self.consensus)):
            if v != v or v in (float("inf"), float("-inf")):
                raise ValueError(f"{self.metric}: {name} must be finite")

    @property
    def channel(self) -> str | None:
        if self.hawkish_sign:
            return POLICY
        if self.growth_sign:
            return GROWTH
        return None


@dataclass(frozen=True)
class Forecast:
    """What the market is carrying for a release that has NOT printed yet.

    Deliberately a different type from :class:`Expectation` rather than one with
    a nullable actual. An Expectation is a fact plus a fact; a Forecast is only
    the second half, and no verdict can be derived from it - the direction does
    not exist until the number does. Making them one class with `actual=None`
    would let every downstream caller forget to check, which is the exact shape
    of the bug this codebase exists to refuse.

    It still carries a named carrier and a stamp, because a consensus with no
    source is somebody's memory of a consensus whether or not the print has
    landed.
    """

    metric: str
    consensus: float
    unit: str
    consensus_source: str
    as_of: str                  # when the consensus was READ, not the release
    previous: float | None = None
    note: str = ""

    def __post_init__(self) -> None:
        if not self.metric.strip():
            raise ValueError("a forecast without a metric name is not representable")
        if not self.consensus_source.strip():
            raise ValueError(
                f"{self.metric}: a forecast needs the carrier of its consensus")
        if not self.unit.strip():
            raise ValueError(f"{self.metric}: unit is mandatory")
        try:
            datetime.strptime(self.as_of, "%Y-%m-%dT%H:%M:%SZ")
        except ValueError as exc:
            raise ValueError(f"{self.metric}: as_of must be ISO8601 Z: {exc}") from exc
        if self.consensus != self.consensus or self.consensus in (
                float("inf"), float("-inf")):
            raise ValueError(f"{self.metric}: consensus must be finite")

    def render(self) -> str:
        prev = "" if self.previous is None else (
            f", prior {fmt_value(self.previous, self.unit)}")
        return (f"{self.metric}: {fmt_value(self.consensus, self.unit)} expected"
                f"{prev} - not yet printed")


@dataclass(frozen=True)
class Verdict:
    expectation: Expectation
    delta: float
    direction: str              # ABOVE / BELOW / IN LINE
    impulse: str
    risk: str                   # BULLISH / BEARISH / NEUTRAL
    why: str
    regime: str
    ok: bool = True

    def render(self) -> str:
        e = self.expectation
        prev = "" if e.previous is None else f", prior {fmt_value(e.previous, e.unit)}"
        return (f"{e.metric}: {fmt_value(e.actual, e.unit)} actual vs "
                f"{fmt_value(e.consensus, e.unit)} expected{prev} -> "
                f"{self.direction} = {self.risk}")


def fmt_value(v: float, unit: str) -> str:
    """Render at the precision the carriers publish, no further."""
    if unit == "pct":
        one = abs(v * 10 - math.floor(abs(v * 10) + 0.5) * (1 if v >= 0 else -1))
        return f"{v:.1f}%" if one < 1e-9 else f"{_half_up(v, 2):.2f}%"
    if unit == "k":
        return f"{_half_up(v, 0):,.0f}k"
    if unit == "bp":
        return f"{_half_up(v, 0):+,.0f}bp"
    return (f"{_half_up(v, 2):,.2f}" if abs(v) < 1000
            else f"{_half_up(v, 0):,.0f}")


def _half_up(v: float, dp: int) -> float:
    """The house rounding rule, floor(x+0.5), applied on both sides of every
    language boundary in this codebase. Python's format spec rounds half to
    even, so 0.125 would print 0.12 here and 0.13 in macro.terminal._fmt."""
    p = 10 ** dp
    return math.floor(abs(v) * p + 0.5) / p * (-1 if v < 0 else 1)


def _regime_key(regime: str) -> str | None:
    r = (regime or "").upper()
    if "INFLATION" in r:
        return "INFLATION"
    if "GROWTH" in r:
        return "GROWTH"
    return None


def assess(exp: Expectation, regime: str) -> Verdict | Insufficient:
    """Direction, impulse and the risk-asset verdict, conditional on the regime."""
    channel = exp.channel
    if channel is None:
        return insufficient(
            f"{exp.metric}: no transmission channel is declared for this print, so "
            f"no market verdict can be derived from it", "hawkish_sign/growth_sign")

    key = _regime_key(regime)
    if key is None:
        return insufficient(
            f"{exp.metric}: the same print reads differently under different "
            f"reaction functions, and the prevailing regime is not established",
            "regime")

    delta = exp.actual - exp.consensus
    if abs(delta) <= exp.tolerance + EPS:
        return Verdict(
            expectation=exp, delta=delta, direction=IN_LINE, impulse=NO_IMPULSE,
            risk=NEUTRAL, regime=regime,
            why=("Printed inside the band the consensus was quoted at, so it carries "
                 "no new information for the policy path."
                 if exp.tolerance else
                 "Printed exactly on consensus: no repricing follows from it."))

    above = delta > 0
    direction = ABOVE if above else BELOW

    if channel == POLICY:
        tighter = (1 if above else -1) * exp.hawkish_sign > 0
        impulse = Impulse.INFLATION_HOTTER if tighter else Impulse.INFLATION_COOLER
    else:
        stronger = (1 if above else -1) * exp.growth_sign > 0
        impulse = Impulse.GROWTH_STRONGER if stronger else Impulse.GROWTH_WEAKER

    rmap = build_matrix(impulse, REGIMES[key], magnitude=1.0,
                        scenario_label=f"{exp.metric} {direction.lower()} consensus")
    cell = rmap.by_asset(RISK_PROXY)
    if cell is None:                       # unreachable unless ASSETS changes
        return insufficient(
            f"{exp.metric}: the reaction map carries no {RISK_PROXY} cell, so no "
            f"risk read can be taken from it", RISK_PROXY)

    risk = RISK_FROM_DIRECTION.get(cell.direction, MIXED)
    # chain[1] is the step that names the binding constraint. Indexing another
    # module's tuple, so it degrades rather than throwing if that changes.
    lead = rmap.chain[1] if len(rmap.chain) > 1 else (rmap.chain[0] if rmap.chain else "")
    why = f"{lead} For {RISK_PROXY}: {cell.mechanism}".lstrip()
    if cell.caveat:
        why += f" ({cell.caveat})"
    return Verdict(expectation=exp, delta=delta, direction=direction,
                   impulse=impulse.value, risk=risk, regime=regime,
                   why=why.rstrip(".") + ".")


def roll_up(verdicts: list[Verdict]) -> tuple[str, str]:
    """One verdict for the release as a whole.

    Agreement is required, not manufactured.  Legs that disagree produce MIXED
    with the split named, because a release whose headline is hot and whose core
    is cool genuinely is mixed and averaging it would erase the only interesting
    thing about it.
    """
    if not verdicts:
        return NEUTRAL, "No figure from this release has been sourced yet."
    live = [v for v in verdicts if v.risk != NEUTRAL]
    if not live:
        return NEUTRAL, "Every sourced leg printed inside expectations."
    labels = {v.risk for v in live}
    if len(labels) == 1:
        only = live[0].risk
        legs = ", ".join(v.expectation.metric for v in live)
        return only, f"{legs} all point the same way."
    parts = []
    for label in (BEARISH, BULLISH, MIXED):
        legs = [v.expectation.metric for v in live if v.risk == label]
        if legs:
            parts.append(f"{', '.join(legs)} {label.lower()}")
    return MIXED, "; ".join(parts) + "."
