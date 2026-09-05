"""Market structure and liquidity mapping (spec sections 18 and 20).

Correctness note that matters more than the feature list: a swing point is not
knowable until ``right`` bars have printed after it.  Every structural event in
this module therefore records ``confirmed_at`` and refuses to use a pivot that
was not yet confirmed at the time of the break.  Skipping that is how a
structure engine produces a backtest that cannot be traded.

Not every wick is manipulation.  A sweep requires the close to reject the
level, and a break requires a close beyond it, not a touch.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from .types import Category, Insufficient, insufficient


@dataclass(frozen=True)
class Bar:
    ts: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0

    def __post_init__(self) -> None:
        if self.high < self.low:
            raise ValueError(f"bar {self.ts}: high {self.high} below low {self.low}")
        if not (self.low <= self.open <= self.high):
            raise ValueError(f"bar {self.ts}: open {self.open} outside [{self.low}, {self.high}]")
        if not (self.low <= self.close <= self.high):
            raise ValueError(f"bar {self.ts}: close {self.close} outside [{self.low}, {self.high}]")

    @property
    def range(self) -> float:
        return self.high - self.low

    @property
    def body(self) -> float:
        return abs(self.close - self.open)

    @property
    def body_ratio(self) -> float:
        return 0.0 if self.range <= 0 else self.body / self.range

    @property
    def bullish(self) -> bool:
        return self.close >= self.open


class SwingKind(str, Enum):
    HIGH = "SWING HIGH"
    LOW = "SWING LOW"


@dataclass(frozen=True)
class Swing:
    index: int
    confirmed_at: int          # earliest index at which this pivot was knowable
    kind: SwingKind
    price: float
    ts: datetime


class Trend(str, Enum):
    BULLISH = "BULLISH (HH/HL)"
    BEARISH = "BEARISH (LH/LL)"
    RANGING = "RANGING / UNRESOLVED"


class EventKind(str, Enum):
    BOS_UP = "BOS UP"
    BOS_DOWN = "BOS DOWN"
    CHOCH_UP = "CHoCH UP"
    CHOCH_DOWN = "CHoCH DOWN"
    SWEEP_HIGH = "LIQUIDITY SWEEP (buy-side taken)"
    SWEEP_LOW = "LIQUIDITY SWEEP (sell-side taken)"
    DISPLACEMENT_UP = "DISPLACEMENT UP"
    DISPLACEMENT_DOWN = "DISPLACEMENT DOWN"


@dataclass(frozen=True)
class StructureEvent:
    kind: EventKind
    index: int
    ts: datetime
    price: float
    reference_level: float | None
    detail: str
    category: Category = Category.FACT   # these are measurements of price, not opinions


@dataclass(frozen=True)
class FVG:
    kind: str                  # "bullish" | "bearish"
    index: int                 # index of the third bar
    ts: datetime
    top: float
    bottom: float
    size: float
    filled_at: int | None = None

    @property
    def midpoint(self) -> float:
        return (self.top + self.bottom) / 2.0


@dataclass(frozen=True)
class LiquidityPool:
    kind: str                  # "buy-side" | "sell-side"
    price: float
    touches: int
    indices: tuple[int, ...]
    note: str


@dataclass(frozen=True)
class StructureRead:
    trend: Trend
    swings: tuple[Swing, ...]
    events: tuple[StructureEvent, ...]
    fvgs: tuple[FVG, ...]
    pools: tuple[LiquidityPool, ...]
    atr: float
    last_confirmed_high: Swing | None
    last_confirmed_low: Swing | None
    session_levels: dict[str, float]
    caveats: tuple[str, ...]
    ok: bool = True

    def latest(self, *kinds: EventKind) -> StructureEvent | None:
        for ev in reversed(self.events):
            if not kinds or ev.kind in kinds:
                return ev
        return None

    def render(self) -> str:
        ev = "\n".join(
            f"    [{e.index:>3}] {e.kind.value:<34} @ {e.price:.5g} {e.detail}"
            for e in self.events[-10:]
        )
        return (
            f"TREND {self.trend.value} | ATR {self.atr:.5g} | "
            f"{len(self.swings)} confirmed swings, {len(self.fvgs)} open FVGs, "
            f"{len(self.pools)} liquidity pools\n  RECENT EVENTS\n{ev or '    none'}"
        )


# --------------------------------------------------------------------------

def true_range(prev: Bar, cur: Bar) -> float:
    return max(cur.high - cur.low, abs(cur.high - prev.close), abs(cur.low - prev.close))


def atr(bars: list[Bar], period: int = 14) -> float | None:
    if len(bars) < period + 1:
        return None
    trs = [true_range(bars[i - 1], bars[i]) for i in range(len(bars) - period, len(bars))]
    a = sum(trs) / period
    return a if a > 0 else None


def find_swings(bars: list[Bar], left: int = 2, right: int = 2) -> list[Swing]:
    """Fractal pivots, each tagged with the bar at which it became knowable."""
    out: list[Swing] = []
    n = len(bars)
    if n < left + right + 1:
        return out
    for i in range(left, n - right):
        h, l = bars[i].high, bars[i].low
        is_high = all(bars[i - k].high < h for k in range(1, left + 1)) and all(
            bars[i + k].high <= h for k in range(1, right + 1)
        )
        is_low = all(bars[i - k].low > l for k in range(1, left + 1)) and all(
            bars[i + k].low >= l for k in range(1, right + 1)
        )
        if is_high:
            out.append(Swing(i, i + right, SwingKind.HIGH, h, bars[i].ts))
        if is_low:
            out.append(Swing(i, i + right, SwingKind.LOW, l, bars[i].ts))
    out.sort(key=lambda s: (s.index, s.kind.value))
    return out


def classify_trend(swings: list[Swing]) -> Trend:
    highs = [s for s in swings if s.kind is SwingKind.HIGH][-2:]
    lows = [s for s in swings if s.kind is SwingKind.LOW][-2:]
    if len(highs) < 2 or len(lows) < 2:
        return Trend.RANGING
    hh = highs[-1].price > highs[-2].price
    hl = lows[-1].price > lows[-2].price
    lh = highs[-1].price < highs[-2].price
    ll = lows[-1].price < lows[-2].price
    if hh and hl:
        return Trend.BULLISH
    if lh and ll:
        return Trend.BEARISH
    return Trend.RANGING


def find_fvgs(bars: list[Bar], min_size: float = 0.0) -> list[FVG]:
    """Three-bar imbalance. Bullish: high[i-2] < low[i]."""
    out: list[FVG] = []
    for i in range(2, len(bars)):
        a, c = bars[i - 2], bars[i]
        if c.low > a.high:
            size = c.low - a.high
            if size > min_size:
                out.append(FVG("bullish", i, c.ts, top=c.low, bottom=a.high, size=size))
        elif c.high < a.low:
            size = a.low - c.high
            if size > min_size:
                out.append(FVG("bearish", i, c.ts, top=a.low, bottom=c.high, size=size))
    # mark fills
    filled: list[FVG] = []
    for g in out:
        fill_idx = None
        for j in range(g.index + 1, len(bars)):
            if g.kind == "bullish" and bars[j].low <= g.bottom:
                fill_idx = j
                break
            if g.kind == "bearish" and bars[j].high >= g.top:
                fill_idx = j
                break
        filled.append(
            FVG(g.kind, g.index, g.ts, g.top, g.bottom, g.size, filled_at=fill_idx)
        )
    return filled


def find_equal_levels(
    swings: list[Swing], kind: SwingKind, tolerance: float
) -> list[LiquidityPool]:
    """Cluster same-kind pivots that sit within ``tolerance`` of each other."""
    pts = [s for s in swings if s.kind is kind]
    if len(pts) < 2 or tolerance <= 0:
        return []
    pools: list[LiquidityPool] = []
    used: set[int] = set()
    for i, a in enumerate(pts):
        if i in used:
            continue
        group = [a]
        gidx = {i}
        for j in range(i + 1, len(pts)):
            if j in used:
                continue
            if abs(pts[j].price - a.price) <= tolerance:
                group.append(pts[j])
                gidx.add(j)
        if len(group) >= 2:
            used |= gidx
            price = sum(s.price for s in group) / len(group)
            pools.append(
                LiquidityPool(
                    kind="buy-side" if kind is SwingKind.HIGH else "sell-side",
                    price=price,
                    touches=len(group),
                    indices=tuple(s.index for s in group),
                    note=(
                        f"{len(group)} pivots within {tolerance:.5g}: resting "
                        f"{'stops above' if kind is SwingKind.HIGH else 'stops below'} "
                        "and a magnet for a sweep"
                    ),
                )
            )
    return pools


def analyse(
    bars: list[Bar],
    *,
    left: int = 2,
    right: int = 2,
    atr_period: int = 14,
    displacement_mult: float = 1.5,
    equal_tol_atr: float = 0.15,
    min_penetration_atr: float = 0.10,
    session_levels: dict[str, float] | None = None,
) -> StructureRead | Insufficient:
    """Full structural read of one series.

    ``session_levels`` (prev day/week high-low, Asia/London/NY session extremes)
    is supplied by the caller: this module does not guess a session calendar.
    """
    need = max(left + right + 1, atr_period + 1)
    if len(bars) < need:
        return insufficient(
            f"need at least {need} bars for a structural read, got {len(bars)}", "bars"
        )
    for i in range(1, len(bars)):
        if bars[i].ts < bars[i - 1].ts:
            return insufficient("bars are not in ascending time order", "bar ordering")

    a = atr(bars, atr_period)
    if a is None:
        return insufficient(
            "ATR is zero or undefined (flat series): structure cannot be scaled", "atr"
        )

    swings = find_swings(bars, left, right)
    trend = classify_trend(swings)
    events: list[StructureEvent] = []

    # --- displacement -----------------------------------------------------
    for i in range(atr_period, len(bars)):
        b = bars[i]
        if b.body >= displacement_mult * a and b.body_ratio >= 0.6:
            events.append(
                StructureEvent(
                    EventKind.DISPLACEMENT_UP if b.bullish else EventKind.DISPLACEMENT_DOWN,
                    i, b.ts, b.close, None,
                    f"body {b.body:.5g} = {b.body / a:.2f}x ATR, body/range "
                    f"{b.body_ratio:.0%}: institutional participation is plausible, "
                    "not proven",
                )
            )

    # --- breaks of structure, using only pivots already confirmed ---------
    running_trend = Trend.RANGING
    for i in range(1, len(bars)):
        prior_swings = [s for s in swings if s.confirmed_at < i]
        if not prior_swings:
            continue
        running_trend = classify_trend(prior_swings)
        hi = next((s for s in reversed(prior_swings) if s.kind is SwingKind.HIGH), None)
        lo = next((s for s in reversed(prior_swings) if s.kind is SwingKind.LOW), None)
        c = bars[i].close

        if hi and c > hi.price and (i - 1 < 0 or bars[i - 1].close <= hi.price):
            kind = EventKind.CHOCH_UP if running_trend is Trend.BEARISH else EventKind.BOS_UP
            events.append(StructureEvent(
                kind, i, bars[i].ts, c, hi.price,
                f"close above swing high {hi.price:.5g} (pivot idx {hi.index}, "
                f"confirmed at {hi.confirmed_at})",
            ))
        if lo and c < lo.price and (i - 1 < 0 or bars[i - 1].close >= lo.price):
            kind = EventKind.CHOCH_DOWN if running_trend is Trend.BULLISH else EventKind.BOS_DOWN
            events.append(StructureEvent(
                kind, i, bars[i].ts, c, lo.price,
                f"close below swing low {lo.price:.5g} (pivot idx {lo.index}, "
                f"confirmed at {lo.confirmed_at})",
            ))

    # --- liquidity sweeps: wick through, close rejects ---------------------
    #
    # Two guards, both of which matter. A penetration smaller than
    # `min_penetration_atr` * ATR is spread noise, not a raid on a pool. And a
    # level that has already been swept is no longer resting liquidity, so it
    # is not re-flagged bar after bar - without that, a slow grind through a
    # pivot prints a dozen identical "sweeps" and the signal is worthless.
    min_pen = min_penetration_atr * a
    swept: list[float] = []

    def already_swept(level: float) -> bool:
        return any(abs(level - x) <= equal_tol_atr * a for x in swept)

    for i in range(1, len(bars)):
        prior = [s for s in swings if s.confirmed_at < i]
        b = bars[i]
        for s in prior[-12:]:
            if (
                s.kind is SwingKind.HIGH
                and b.high - s.price >= min_pen
                and b.close < s.price
                and not already_swept(s.price)
            ):
                swept.append(s.price)
                events.append(StructureEvent(
                    EventKind.SWEEP_HIGH, i, b.ts, b.high, s.price,
                    f"wick {b.high:.5g} through {s.price:.5g} by "
                    f"{(b.high - s.price) / a:.2f}x ATR, close {b.close:.5g} "
                    f"back below: buy-side liquidity taken and rejected",
                ))
                break
        for s in prior[-12:]:
            if (
                s.kind is SwingKind.LOW
                and s.price - b.low >= min_pen
                and b.close > s.price
                and not already_swept(s.price)
            ):
                swept.append(s.price)
                events.append(StructureEvent(
                    EventKind.SWEEP_LOW, i, b.ts, b.low, s.price,
                    f"wick {b.low:.5g} through {s.price:.5g} by "
                    f"{(s.price - b.low) / a:.2f}x ATR, close {b.close:.5g} "
                    f"back above: sell-side liquidity taken and rejected",
                ))
                break

    events.sort(key=lambda e: (e.index, e.kind.value))

    fvgs = [g for g in find_fvgs(bars, min_size=0.10 * a) if g.filled_at is None]
    pools = (
        find_equal_levels(swings, SwingKind.HIGH, equal_tol_atr * a)
        + find_equal_levels(swings, SwingKind.LOW, equal_tol_atr * a)
    )

    last_hi = next((s for s in reversed(swings) if s.kind is SwingKind.HIGH), None)
    last_lo = next((s for s in reversed(swings) if s.kind is SwingKind.LOW), None)

    caveats = [
        f"Pivots use a {left}/{right} fractal: the most recent {right} bars cannot "
        "yet contain a confirmed swing, so the newest structure is always provisional.",
        "Displacement indicates an unusually large directional bar. It is consistent "
        "with institutional participation; it does not prove it.",
        f"A sweep requires the wick to clear the pivot by at least "
        f"{min_penetration_atr:.2f}x ATR AND the close to reject it. Wicks alone are "
        "not treated as manipulation, and a level is flagged once - after it is "
        "taken it is no longer resting liquidity.",
    ]
    if session_levels is None:
        caveats.append(
            "No session levels supplied: previous day/week and Asia/London/NY "
            "extremes are UNKNOWN and are not inferred from the bar series."
        )

    return StructureRead(
        trend=trend, swings=tuple(swings), events=tuple(events), fvgs=tuple(fvgs),
        pools=tuple(pools), atr=a, last_confirmed_high=last_hi,
        last_confirmed_low=last_lo, session_levels=dict(session_levels or {}),
        caveats=tuple(caveats),
    )


__all__ = [
    "Bar", "EventKind", "FVG", "LiquidityPool", "StructureEvent", "StructureRead",
    "Swing", "SwingKind", "Trend", "analyse", "atr", "classify_trend",
    "find_equal_levels", "find_fvgs", "find_swings", "true_range",
]
