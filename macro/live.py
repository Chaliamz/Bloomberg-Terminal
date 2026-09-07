"""Live snapshot schema and the 24/7 scanner.

Two halves, deliberately separable:

``Snapshot``  the data contract. Every quote carries value, unit, capture time,
              source name, source tier and a URL. A field with no source is not
              representable — there is no way to put an unattributed number in.

``scan()``    the poller. Hits primary agency endpoints first and wires second,
              because the doctrine is that a release is public at the agency the
              instant it publishes, typically ahead of wire coverage. Anything
              unreachable stays absent rather than stale.

The scanner needs outbound network. Where egress is blocked it reports the
failure per source and leaves the previous value in place *with its original
timestamp*, so the terminal shows the true age rather than a fresh-looking lie.
"""

from __future__ import annotations

import json
import math
import os
import re
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable

from .types import Tier, iso, utcnow

__all__ = [
    "Quote", "Headline", "Gauge", "Liquidations", "GeoEvent", "Snapshot",
    "SOURCES", "RELEASE_CLOCK", "load", "save", "scan", "merge", "age_seconds",
    "liquidation_ladder", "liquidation_heatmap", "PriceAnchor", "HEAT_RAMP",
    "HEAT_RAMPS", "Equity", "Earning", "leverage_tiers", "liquidity_levels",
    "parse_binance_ticker", "CRYPTO_SOURCES",
]

UA = "macro-radar/1.1 (institutional macro terminal; contact: operator)"


# ---------------------------------------------------------------------------
# Data contract
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Quote:
    """One observed number. Source and capture time are mandatory."""

    key: str
    value: float
    unit: str
    as_of: str                 # ISO8601 Z, the moment the value was true
    source: str
    tier: int
    url: str = ""
    label: str = ""
    change: float | None = None       # change vs prior session, same unit
    change_unit: str = ""             # "pct", "bp", "abs"
    note: str = ""
    confidence: float = 1.0           # lowered when sources conflict

    def __post_init__(self) -> None:
        if not self.source.strip():
            raise ValueError(f"{self.key}: a quote without a source is not representable")
        if self.tier not in (1, 2, 3, 4):
            raise ValueError(f"{self.key}: tier must be 1-4, got {self.tier}")
        if not self.unit.strip():
            raise ValueError(f"{self.key}: unit is mandatory")
        try:
            datetime.strptime(self.as_of, "%Y-%m-%dT%H:%M:%SZ")
        except ValueError as exc:
            raise ValueError(f"{self.key}: as_of must be ISO8601 Z: {exc}") from exc
        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError(f"{self.key}: confidence out of range")


@dataclass(frozen=True)
class Headline:
    """One news item, already tiered."""

    title: str
    source: str
    tier: int
    published: str             # ISO8601 Z
    url: str = ""
    impact: int = 50           # 0-100 market impact
    assets: tuple[str, ...] = ()
    summary: str = ""
    primary_confirmed: bool = False

    def __post_init__(self) -> None:
        if self.tier not in (1, 2, 3, 4):
            raise ValueError(f"headline tier must be 1-4: {self.title[:40]}")
        if not (0 <= self.impact <= 100):
            raise ValueError("headline impact out of range")


@dataclass(frozen=True)
class Gauge:
    """A bounded sentiment reading, e.g. a Fear & Greed index."""

    key: str
    label: str
    value: float
    band: str                  # "Extreme Fear" ... "Extreme Greed"
    as_of: str
    source: str
    tier: int
    lo: float = 0.0
    hi: float = 100.0
    url: str = ""
    note: str = ""
    confidence: float = 1.0

    def __post_init__(self) -> None:
        if not self.source.strip():
            raise ValueError(f"{self.key}: a gauge without a source is not representable")
        if not (self.lo <= self.value <= self.hi):
            raise ValueError(f"{self.key}: {self.value} outside [{self.lo}, {self.hi}]")
        if self.tier not in (1, 2, 3, 4):
            raise ValueError(f"{self.key}: tier must be 1-4")
        datetime.strptime(self.as_of, "%Y-%m-%dT%H:%M:%SZ")

    @property
    def pct(self) -> float:
        span = self.hi - self.lo
        return 0.0 if span <= 0 else (self.value - self.lo) / span


@dataclass(frozen=True)
class Liquidations:
    """Observed derivatives liquidations over a stated window."""

    window: str                # e.g. "24h to 03:52 UTC 2026-09-04"
    total_usd: float
    long_usd: float
    short_usd: float
    as_of: str
    source: str
    tier: int
    asset_usd: float | None = None      # the single-asset share, e.g. BTC
    asset_label: str = ""
    asset_short_pct: float | None = None
    url: str = ""
    note: str = ""

    def __post_init__(self) -> None:
        if not self.source.strip():
            raise ValueError("liquidations without a source are not representable")
        for name, v in (("total", self.total_usd), ("long", self.long_usd),
                        ("short", self.short_usd)):
            if v < 0:
                raise ValueError(f"liquidation {name} cannot be negative")
        datetime.strptime(self.as_of, "%Y-%m-%dT%H:%M:%SZ")

    @property
    def short_pct(self) -> float:
        t = self.long_usd + self.short_usd
        return 0.0 if t <= 0 else 100.0 * self.short_usd / t

    @property
    def long_pct(self) -> float:
        return 100.0 - self.short_pct


@dataclass(frozen=True)
class GeoEvent:
    """A geopolitical development with an identified market channel."""

    headline: str
    region: str
    severity: int              # 0-100
    as_of: str
    source: str
    tier: int
    channel: str = ""          # the transmission path into markets
    assets: tuple[str, ...] = ()
    status: str = "ONGOING"
    url: str = ""

    def __post_init__(self) -> None:
        if not (0 <= self.severity <= 100):
            raise ValueError("severity out of range")
        if self.tier not in (1, 2, 3, 4):
            raise ValueError("geo event tier must be 1-4")
        datetime.strptime(self.as_of, "%Y-%m-%dT%H:%M:%SZ")


def liquidation_ladder(price: float, levels=(5, 10, 25, 50, 100)) -> list[dict]:
    """Exact liquidation prices for a position opened at ``price``.

    long_liq  = price * (1 - 1/N)     short_liq = price * (1 + 1/N)

    This is arithmetic, not observed exchange data: it excludes maintenance
    margin and fees, so a real venue triggers marginally earlier. It is NOT a
    heatmap of where open interest actually sits - that requires per-exchange
    position data. The page must say so.
    """
    if price <= 0:
        return []
    out = []
    for n in levels:
        if n <= 1:
            continue
        out.append({
            "leverage": n,
            "long_liq": price * (1 - 1.0 / n),
            "short_liq": price * (1 + 1.0 / n),
            "move_pct": 100.0 / n,
        })
    return out


@dataclass(frozen=True)
class PriceAnchor:
    """One observed price with its date. The heatmap is built only from these."""

    date: str                  # ISO8601 Z
    price: float
    source: str
    tier: int
    url: str = ""
    note: str = ""

    def __post_init__(self) -> None:
        if self.price <= 0:
            raise ValueError("price anchor must be positive")
        if not self.source.strip():
            raise ValueError("a price anchor without a source is not representable")
        if self.tier not in (1, 2, 3, 4):
            raise ValueError("anchor tier must be 1-4")
        datetime.strptime(self.date, "%Y-%m-%dT%H:%M:%SZ")


# Sequential magnitude ramps. Every one is verified monotonic in OKLab lightness
# with step-gap ratios under 2.0 (tests/test_live.py asserts it). Sequential is
# the right family here because the heatmap encodes magnitude, not identity.
HEAT_RAMPS: dict[str, tuple[str, ...]] = {
    "viridis": ("#440154", "#482878", "#3E4A89", "#31688E", "#26828E",
                "#1F9E89", "#35B779", "#6DCD59", "#B4DE2C", "#FDE725"),
    "magma": ("#000004", "#1C1044", "#4F127B", "#812581", "#B5367A",
              "#E55064", "#FB8761", "#FEC287", "#FCFDBF"),
    "ice": ("#04122B", "#0B2C55", "#12497E", "#1A69A0", "#2E8BB8",
            "#54ACC9", "#8ACBD8", "#C6E6EC"),
    "ember": ("#180A12", "#3E1030", "#6B1240", "#9A2140", "#C44536",
              "#E27235", "#F2A93C", "#FADF6B"),
}
HEAT_RAMP = HEAT_RAMPS["viridis"]


def leverage_tiers(lo: int = 2, hi: int = 125) -> tuple[int, ...]:
    """Every integer leverage tier in [lo, hi].

    Modelling four round tiers was the earlier simplification and it is what made
    the field look like a handful of stripes. Venues offer the whole spectrum and
    traders use it, so every tier gets a level. The density that results near the
    price is emergent - at high leverage consecutive tiers are only
    ``P/(n(n+1))`` apart, so dozens land in one price bin - rather than imposed
    by a weighting fudge.
    """
    lo = max(2, int(lo))
    hi = max(lo, int(hi))
    return tuple(range(lo, hi + 1))


def liquidity_levels(
    anchors: list["PriceAnchor"],
    *,
    levels: tuple[int, ...] | None = None,
    bands: int = 24,
    lo: float | None = None,
    hi: float | None = None,
) -> dict[str, Any]:
    """Where unswept liquidation levels sit, and what leverage puts them there.

    Same model as the heatmap, reported as data instead of pixels. A position
    opened at observed price P at leverage n liquidates at ``P*(1-1/n)`` long and
    ``P*(1+1/n)`` short; the level stays pending until price is later OBSERVED to
    have swept through it, at which point it is removed because the liquidation
    has happened.

    What comes back is the surviving pending set, bucketed into price bands, with
    the leverage tiers that put a level in each band. That answers the two
    questions a chart only gestures at: where is the liquidity, and how levered
    is it.

    Counts are (observation, tier, side) contributions. They are NOT open
    interest and NOT dollars - no per-exchange position data is reachable here,
    and inventing a notional would be the whole contract broken. The count says
    how many distinct leverage tiers put a level in that band, which is a real
    statement about clustering and nothing more.
    """
    if levels is None:
        levels = leverage_tiers()
    if not levels:
        return {"ok": False, "reason": "no leverage tiers in the model"}
    pts = sorted(anchors, key=lambda a: a.date)
    if len(pts) < 2:
        return {"ok": False, "reason": "need at least two dated price anchors"}
    if bands < 2:
        return {"ok": False, "reason": "need at least two bands"}

    pending: list[tuple[float, int, str]] = []
    last_price = pts[0].price
    for a in pts:
        span_lo, span_hi = min(last_price, a.price), max(last_price, a.price)
        pending = [p for p in pending if not (span_lo <= p[0] <= span_hi)]
        for n in levels:
            pending.append((a.price * (1 - 1.0 / n), n, "long"))
            pending.append((a.price * (1 + 1.0 / n), n, "short"))
        last_price = a.price

    spot = pts[-1].price
    prices = [a.price for a in pts]
    lo = lo if lo is not None else min(prices) * 0.985
    hi = hi if hi is not None else max(prices) * 1.015
    if hi <= lo:
        return {"ok": False, "reason": "degenerate price range"}
    inside = [p for p in pending if lo <= p[0] <= hi]
    if not inside:
        return {"ok": False, "reason": "no pending levels fell inside the price range"}

    width = (hi - lo) / bands
    buckets: dict[int, dict[str, Any]] = {}
    for level, n, side in inside:
        # floor(x+0.5) is NOT wanted here: a band is a half-open interval, so
        # plain floor is correct and the top edge is clamped into the last band.
        i = min(bands - 1, int((level - lo) / width))
        b = buckets.setdefault(i, {"tiers": [], "long": 0, "short": 0, "levels": []})
        b["tiers"].append(n)
        b[side] += 1
        b["levels"].append(level)

    peak = max(len(b["tiers"]) for b in buckets.values())
    out = []
    for i, b in sorted(buckets.items(), reverse=True):
        tiers = sorted(b["tiers"])
        out.append({
            "lo": lo + i * width,
            "hi": lo + (i + 1) * width,
            "mid": lo + (i + 0.5) * width,
            "count": len(tiers),
            "share": math.floor(len(tiers) / peak * 1e4 + 0.5) / 1e4,
            "lev_lo": tiers[0],
            "lev_hi": tiers[-1],
            "lev_median": tiers[len(tiers) // 2],
            "long": b["long"],
            "short": b["short"],
            "side": "long" if b["long"] > b["short"] else
                    ("short" if b["short"] > b["long"] else "mixed"),
            "from_spot_pct": (lo + (i + 0.5) * width - spot) / spot * 100.0,
        })
    return {"ok": True, "spot": spot, "spot_at": pts[-1].date,
            "spot_source": pts[-1].source, "lo": lo, "hi": hi, "bands": bands,
            "peak": peak, "pending_total": len(inside),
            "levels": list(levels), "rows": out}


def liquidation_heatmap(
    anchors: list["PriceAnchor"],
    *,
    levels: tuple[int, ...] | None = None,
    columns: int = 36,
    rows: int = 34,
    t0: str | None = None,
    t1: str | None = None,
    lo: float | None = None,
    hi: float | None = None,
) -> dict[str, Any]:
    """Cumulative pending-liquidation field over price and time.

    The model, stated so it can be argued with:

    1.  At each observed price, positions opened there at leverage N would
        liquidate at ``P*(1-1/N)`` (longs) and ``P*(1+1/N)`` (shorts), for every
        integer tier in the modelled leverage range. Those levels are added to a
        pending set, each weighted equally.
    2.  A pending level is REMOVED when price is later observed to have swept
        through it - that is the liquidation actually occurring.
    3.  Between two observations nothing is known, so the pending set is held
        constant rather than interpolated. Price itself is never interpolated.

    Column intensity is the binned density of the pending set, normalised to
    the busiest cell. This is the published *shape* of a liquidation heatmap
    computed from real observed prices; it is NOT open-interest-weighted,
    because that needs per-exchange position data. Both facts belong on the page.
    """
    # omitted -> the full spectrum; explicitly empty -> a refusal, not a silent
    # substitution. The JS port draws the same distinction, or the two engines
    # would disagree on levels=[].
    if levels is None:
        levels = leverage_tiers()
    if not levels:
        return {"ok": False, "reason": "no leverage tiers in the model"}
    pts = sorted(anchors, key=lambda a: a.date)
    if len(pts) < 2 or columns < 2 or rows < 2:
        return {"ok": False, "reason": "need at least two dated price anchors"}

    prices = [a.price for a in pts]
    lo = lo if lo is not None else min(prices) * 0.97
    hi = hi if hi is not None else max(prices) * 1.03
    if hi <= lo:
        return {"ok": False, "reason": "degenerate price range"}

    # The time axis defaults to the first and last observation, but the caller
    # may widen it to bar boundaries so the field and the drawn bars share one
    # grid: without that the edge bars are half off-canvas and render as runts.
    _t0 = t0 if t0 is not None else pts[0].date
    _t1 = t1 if t1 is not None else pts[-1].date
    try:
        t0 = datetime.strptime(_t0, "%Y-%m-%dT%H:%M:%SZ")
        t1 = datetime.strptime(_t1, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return {"ok": False, "reason": "unparseable time bounds"}
    span = (t1 - t0).total_seconds()
    if span <= 0:
        return {"ok": False, "reason": "all anchors share one timestamp"}

    def col_of(dt_iso: str) -> int:
        t = datetime.strptime(dt_iso, "%Y-%m-%dT%H:%M:%SZ")
        f = (t - t0).total_seconds() / span
        # floor(x + 0.5), NOT round(): Python rounds halves to even and
        # JavaScript rounds them up, so round() would make the two
        # implementations disagree on exact .5 boundaries.
        return max(0, min(columns - 1, int(f * (columns - 1) + 0.5)))

    def row_of(price: float) -> int:
        f = (price - lo) / (hi - lo)
        return max(0, min(rows - 1, int(f * rows)))

    grid = [[0.0] * rows for _ in range(columns)]
    pending: list[tuple[float, int, str]] = []      # (level, leverage, side)
    last_price = pts[0].price
    anchor_cols = {col_of(a.date): a for a in pts}

    for c in range(columns):
        a = anchor_cols.get(c)
        if a is not None:
            # sweep: any pending level between the previous and current price
            # has been crossed, so it is gone
            span_lo, span_hi = min(last_price, a.price), max(last_price, a.price)
            pending = [p for p in pending if not (span_lo <= p[0] <= span_hi)]
            for n in levels:
                pending.append((a.price * (1 - 1.0 / n), n, "long"))
                pending.append((a.price * (1 + 1.0 / n), n, "short"))
            last_price = a.price
        for level, _n, _side in pending:
            if lo <= level <= hi:
                # Uniform weight per (anchor, tier, side). Any leverage-dependent
                # weight would be an invented distribution of open interest; the
                # bright band near price comes from tier spacing alone.
                grid[c][row_of(level)] += 1.0

    peak = max((v for col in grid for v in col), default=0.0)
    if peak <= 0:
        return {"ok": False, "reason": "no pending levels fell inside the price range"}
    # floor(x+0.5), NOT round() and NOT JS Math.round(): Python rounds halves
    # to even and Math.round mishandles 0.49999999999999994. With integer cell
    # counts a tie is reachable (peak=32, v=1 -> 312.5), so the two engines
    # would land in different colour buckets. Both now use this exact form.
    norm = [[math.floor(v / peak * 1e4 + 0.5) / 1e4 for v in col] for col in grid]

    return {
        "ok": True, "columns": columns, "rows": rows, "lo": lo, "hi": hi,
        "grid": norm, "peak": peak, "levels": list(levels),
        "t0": _t0, "t1": _t1,
        "anchors": [{"col": col_of(a.date), "row": row_of(a.price), "price": a.price,
                     "date": a.date, "source": a.source, "tier": a.tier}
                    for a in pts],
    }


@dataclass(frozen=True)
class Equity:
    """A large-cap listing with its market value and session move."""

    ticker: str
    name: str
    as_of: str
    source: str
    tier: int
    mktcap_usd: float | None = None
    change_pct: float | None = None
    url: str = ""
    note: str = ""

    def __post_init__(self) -> None:
        if not self.ticker.strip():
            raise ValueError("equity needs a ticker")
        if not self.source.strip():
            raise ValueError(f"{self.ticker}: an equity without a source is not representable")
        if self.tier not in (1, 2, 3, 4):
            raise ValueError(f"{self.ticker}: tier must be 1-4")
        if self.mktcap_usd is not None and self.mktcap_usd <= 0:
            raise ValueError(f"{self.ticker}: market cap must be positive")
        datetime.strptime(self.as_of, "%Y-%m-%dT%H:%M:%SZ")


@dataclass(frozen=True)
class Earning:
    """A scheduled or reported earnings event.

    ``when`` is empty when the exact datetime is not published: the board then
    shows the stated window and no countdown, rather than inventing an hour.
    """

    ticker: str
    name: str
    source: str
    tier: int
    when: str = ""             # ISO8601 Z, or "" when only a window is known
    window: str = ""           # human window, e.g. "week of 7-11 September"
    session: str = "UNKNOWN"   # BMO | AMC | UNKNOWN
    status: str = "SCHEDULED"  # SCHEDULED | REPORTED
    time_confirmed: bool = False   # False => day-granularity countdown only
    url: str = ""
    note: str = ""

    def __post_init__(self) -> None:
        if not self.ticker.strip():
            raise ValueError("earnings event needs a ticker")
        if not self.source.strip():
            raise ValueError(f"{self.ticker}: earnings without a source is not representable")
        if self.tier not in (1, 2, 3, 4):
            raise ValueError(f"{self.ticker}: tier must be 1-4")
        if self.session not in ("BMO", "AMC", "UNKNOWN"):
            raise ValueError(f"{self.ticker}: session must be BMO, AMC or UNKNOWN")
        if not self.when and not self.window:
            raise ValueError(f"{self.ticker}: needs either an exact time or a window")
        if self.when:
            datetime.strptime(self.when, "%Y-%m-%dT%H:%M:%SZ")


@dataclass
class Snapshot:
    captured: str
    quotes: dict[str, Quote] = field(default_factory=dict)
    headlines: list[Headline] = field(default_factory=list)
    releases: list[dict[str, Any]] = field(default_factory=list)
    policy: dict[str, Any] = field(default_factory=dict)
    gauges: dict[str, Gauge] = field(default_factory=dict)
    price_anchors: list[PriceAnchor] = field(default_factory=list)
    btc_window: dict[str, Any] = field(default_factory=dict)
    equities: list[Equity] = field(default_factory=list)
    earnings: list[Earning] = field(default_factory=list)
    liquidations: Liquidations | None = None
    geo: list[GeoEvent] = field(default_factory=list)
    flows: list[dict[str, Any]] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    regime: str = "UNKNOWN"
    regime_basis: str = ""

    def q(self, key: str) -> Quote | None:
        return self.quotes.get(key)

    def to_json(self) -> str:
        return json.dumps({
            "captured": self.captured,
            "regime": self.regime,
            "regime_basis": self.regime_basis,
            "quotes": {k: asdict(v) for k, v in self.quotes.items()},
            "headlines": [asdict(h) for h in self.headlines],
            "gauges": {k: asdict(v) for k, v in self.gauges.items()},
            "price_anchors": [asdict(a) for a in self.price_anchors],
            "btc_window": self.btc_window,
            "equities": [asdict(x) for x in self.equities],
            "earnings": [asdict(x) for x in self.earnings],
            "liquidations": asdict(self.liquidations) if self.liquidations else None,
            "geo": [asdict(g) for g in self.geo],
            "flows": self.flows,
            "releases": self.releases,
            "policy": self.policy,
            "conflicts": self.conflicts,
            "errors": self.errors,
        }, indent=2, ensure_ascii=False, default=list)


def _quote_from(d: dict) -> Quote:
    return Quote(**{k: v for k, v in d.items() if k in Quote.__dataclass_fields__})


def _gauge_from(d: dict) -> Gauge:
    return Gauge(**{k: v for k, v in d.items() if k in Gauge.__dataclass_fields__})


def _geo_from(d: dict) -> GeoEvent:
    data = {k: v for k, v in d.items() if k in GeoEvent.__dataclass_fields__}
    if isinstance(data.get("assets"), list):
        data["assets"] = tuple(data["assets"])
    return GeoEvent(**data)


def _liq_from(d: dict) -> Liquidations:
    return Liquidations(**{k: v for k, v in d.items()
                           if k in Liquidations.__dataclass_fields__})


def _headline_from(d: dict) -> Headline:
    data = {k: v for k, v in d.items() if k in Headline.__dataclass_fields__}
    if isinstance(data.get("assets"), list):
        data["assets"] = tuple(data["assets"])
    return Headline(**data)


def load(path: str) -> Snapshot | None:
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8") as fh:
            raw = json.load(fh)
    except (json.JSONDecodeError, OSError):
        return None
    try:
        return Snapshot(
            captured=raw["captured"],
            regime=raw.get("regime", "UNKNOWN"),
            regime_basis=raw.get("regime_basis", ""),
            quotes={k: _quote_from(v) for k, v in (raw.get("quotes") or {}).items()},
            headlines=[_headline_from(h) for h in (raw.get("headlines") or [])],
            gauges={k: _gauge_from(v) for k, v in (raw.get("gauges") or {}).items()},
            price_anchors=[PriceAnchor(**{k: v for k, v in a.items()
                                          if k in PriceAnchor.__dataclass_fields__})
                           for a in (raw.get("price_anchors") or [])],
            btc_window=dict(raw.get("btc_window") or {}),
            equities=[Equity(**{k: v for k, v in x.items()
                                if k in Equity.__dataclass_fields__})
                      for x in (raw.get("equities") or [])],
            earnings=[Earning(**{k: v for k, v in x.items()
                                 if k in Earning.__dataclass_fields__})
                      for x in (raw.get("earnings") or [])],
            liquidations=(_liq_from(raw["liquidations"])
                          if raw.get("liquidations") else None),
            geo=[_geo_from(g) for g in (raw.get("geo") or [])],
            flows=list(raw.get("flows") or []),
            releases=list(raw.get("releases") or []),
            policy=dict(raw.get("policy") or {}),
            conflicts=list(raw.get("conflicts") or []),
            errors=list(raw.get("errors") or []),
        )
    except (KeyError, TypeError, ValueError):
        return None


def save(snap: Snapshot, path: str) -> str:
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(snap.to_json())
    os.replace(tmp, path)          # atomic: a reader never sees a half-written file
    return path


def age_seconds(ts: str, now: datetime | None = None) -> float | None:
    try:
        t = datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return None
    return ((now or utcnow()) - t).total_seconds()


# ---------------------------------------------------------------------------
# Source registry: primary first, wires second
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Source:
    name: str
    tier: int
    url: str
    kind: str                  # "curve" | "fred" | "rss" | "schedule"
    interval: int              # seconds between polls
    provides: tuple[str, ...] = ()


SOURCES: tuple[Source, ...] = (
    # -- Tier 1: the institution that creates the number ---------------------
    Source("US Treasury par yield curve", 1,
           "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/"
           "daily-treasury-rates.csv/{year}/all?type=daily_treasury_yield_curve"
           "&field_tdr_date_value={year}&page&_format=csv",
           "curve", 900, ("US2Y", "US5Y", "US10Y", "US30Y")),
    Source("FRED", 1, "https://api.stlouisfed.org/fred/series/observations", "fred", 900,
           ("US2Y", "US10Y", "US10Y_REAL", "US10Y_BE", "VIX", "DXY", "WTI", "HY_OAS")),
    Source("Federal Reserve press releases", 1,
           "https://www.federalreserve.gov/feeds/press_all.xml", "rss", 60),
    Source("Federal Reserve speeches", 1,
           "https://www.federalreserve.gov/feeds/speeches.xml", "rss", 120),
    Source("ECB press", 1, "https://www.ecb.europa.eu/rss/press.html", "rss", 120),
    Source("BLS news releases", 1, "https://www.bls.gov/feed/bls_latest.rss", "rss", 60),
    Source("BEA news", 1, "https://www.bea.gov/rss.xml", "rss", 300),
    Source("EIA petroleum", 1, "https://www.eia.gov/rss/todayinenergy.xml", "rss", 900),
    # -- Tier 2: wires -------------------------------------------------------
    Source("Reuters business", 2, "https://feeds.reuters.com/reuters/businessNews", "rss", 120),
    Source("CNBC markets", 2, "https://www.cnbc.com/id/100003114/device/rss/rss.html", "rss", 120),
    Source("WSJ markets", 2, "https://feeds.a.dj.com/rss/RSSMarketsMain.xml", "rss", 180),
    # -- crypto: the venue itself, which is Tier 1 for its own last trade -----
    Source("Binance BTCUSDT", 1,
           "https://api.binance.com/api/v3/ticker/24hr?symbol=BTCUSDT",
           "crypto", 30, ("BTC",)),
    Source("Binance ETHUSDT", 1,
           "https://api.binance.com/api/v3/ticker/24hr?symbol=ETHUSDT",
           "crypto", 30, ("ETH",)),
)

# The exchange is the primary source for its own last traded price, so these are
# Tier 1. They are listed separately because they are the only sources in the
# set that are reachable often enough to make `python -m macro live` worth
# running: everything else moves daily at best.
CRYPTO_SOURCES: tuple[Source, ...] = tuple(x for x in SOURCES if x.kind == "crypto")

# A live poll every 30s would append a price anchor every 30s and the series
# would grow without bound - 2,880 a day, and the liquidity map recomputes over
# all of them. One anchor per this many seconds is enough to keep the map
# current while the series stays a series rather than a log.
ANCHOR_MIN_GAP = 900

# Scheduled primary releases: the exact moment a number becomes public, and the
# URL that carries it first. Polling this at T+0 is how the terminal sees a
# print before wire coverage clears - the whole point of section 16.
RELEASE_CLOCK: tuple[dict[str, Any], ...] = (
    {"code": "US_CPI", "label": "US CPI (Aug)", "when": "2026-09-11T12:30:00Z",
     "agency": "BLS", "tier": 1,
     "url": "https://www.bls.gov/news.release/cpi.nr0.htm",
     "note": "Locked-file embargo lifts at 08:30 ET; the agency page is the first "
             "public carrier."},
    {"code": "US_PPI", "label": "US PPI (Aug)", "when": "2026-09-10T12:30:00Z",
     "agency": "BLS", "tier": 1,
     "url": "https://www.bls.gov/news.release/ppi.nr0.htm", "note": ""},
    {"code": "US_CLAIMS", "label": "US Initial Jobless Claims", "when": "2026-09-10T12:30:00Z",
     "agency": "DOL/ETA", "tier": 1,
     "url": "https://www.dol.gov/ui/data.pdf", "note": "Weekly, every Thursday."},
    {"code": "ECB_DECISION", "label": "ECB monetary policy decision", "when": "2026-09-10T12:15:00Z",
     "agency": "ECB", "tier": 1,
     "url": "https://www.ecb.europa.eu/press/pr/date/2026/html/index.en.html",
     "note": "Press conference 45 minutes later. Verify the date against the ECB "
             "calendar before trading it."},
    {"code": "FOMC", "label": "FOMC decision + SEP", "when": "2026-09-16T18:00:00Z",
     "agency": "Federal Reserve", "tier": 1,
     "url": "https://www.federalreserve.gov/newsevents/pressreleases/monetary20260916a.htm",
     "note": "Statement 14:00 ET, press conference 14:30 ET. Quarterly SEP lands "
             "with the statement."},
    {"code": "US_RETAIL", "label": "US Retail Sales (Aug)", "when": "2026-09-15T12:30:00Z",
     "agency": "Census", "tier": 1,
     "url": "https://www.census.gov/retail/index.html", "note": ""},
)


# ---------------------------------------------------------------------------
# Scanner
# ---------------------------------------------------------------------------


def parse_binance_ticker(body: str, *, symbol: str = "BTCUSDT") -> dict | None:
    """Parse Binance ``GET /api/v3/ticker/24hr``.

    This is the live crypto adapter. The scanner had no crypto source at all,
    which is why running it never moved Bitcoin: it was polling Treasury, FRED
    and RSS and nothing else.

    Binance returns every numeric field as a STRING and the times as millisecond
    epochs. Everything is validated rather than trusted: a malformed body, a
    missing field, a non-numeric string, the wrong symbol, a non-finite or
    non-positive price, or a close time in the future all return None, because
    an adapter that guesses is worse than one that reports nothing.
    """
    try:
        raw = json.loads(body)
    except (ValueError, TypeError):
        return None
    if isinstance(raw, list):               # symbol-less call returns an array
        raw = next((x for x in raw
                    if isinstance(x, dict) and x.get("symbol") == symbol), None)
    if not isinstance(raw, dict):
        return None
    if str(raw.get("symbol", "")).upper() != symbol.upper():
        return None

    def num(key: str) -> float | None:
        v = raw.get(key)
        if v is None:
            return None
        try:
            f = float(v)
        except (TypeError, ValueError):
            return None
        return f if math.isfinite(f) else None

    price = num("lastPrice")
    if price is None or price <= 0:
        return None

    close_ms = num("closeTime")
    if close_ms is None or close_ms <= 0:
        return None
    # Binance sends milliseconds. A seconds-epoch value here would put the
    # stamp in 1970 and the age counter would read decades.
    when = datetime.fromtimestamp(close_ms / 1000.0, tz=timezone.utc)
    now = utcnow()
    if when > now + timedelta(minutes=5):
        return None                          # clock skew
    # A seconds-epoch sent where milliseconds are expected parses cleanly and
    # lands in 1970 - the guard above does not catch it, and the age counter
    # would read decades. A live ticker is seconds old, so anything older than
    # a week is the wrong unit or a stale mirror either way.
    if when < now - timedelta(days=7):
        return None

    out = {"symbol": symbol.upper(), "price": price,
           "as_of": when.strftime("%Y-%m-%dT%H:%M:%SZ")}
    for key, field in (("change_pct", "priceChangePercent"), ("open", "openPrice"),
                       ("high", "highPrice"), ("low", "lowPrice"),
                       ("volume", "volume")):
        v = num(field)
        if v is not None:
            out[key] = v
    # A high below the low is a corrupt payload, not a market condition.
    if "high" in out and "low" in out and out["high"] < out["low"]:
        return None
    return out


def _http(url: str, timeout: float = 12.0) -> str | None:
    import ssl
    import urllib.error
    import urllib.request

    ctx = ssl.create_default_context()
    for var in ("SSL_CERT_FILE", "REQUESTS_CA_BUNDLE"):
        p = os.environ.get(var)
        if p and os.path.exists(p):
            ctx = ssl.create_default_context(cafile=p)
            break
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
            if r.status != 200:
                return None
            return r.read().decode("utf-8", errors="replace")
    except Exception:                      # adapters never raise into the loop
        return None


_ITEM = re.compile(r"<item\b.*?</item>|<entry\b.*?</entry>", re.S | re.I)
_TITLE = re.compile(r"<title[^>]*>(.*?)</title>", re.S | re.I)
_LINK = re.compile(r"<link[^>]*>(.*?)</link>|<link[^>]*href=[\"'](.*?)[\"']", re.S | re.I)
_DATE = re.compile(r"<(?:pubDate|published|updated|dc:date)[^>]*>(.*?)</", re.S | re.I)


def _clean(x: str) -> str:
    x = re.sub(r"<!\[CDATA\[(.*?)\]\]>", r"\1", x, flags=re.S)
    x = re.sub(r"<[^>]+>", "", x)
    import html as _h
    return _h.unescape(x).strip()


def parse_rss(xml: str, source: str, tier: int, limit: int = 12) -> list[Headline]:
    """Minimal RSS/Atom reader. Returns [] on anything it cannot parse."""
    out: list[Headline] = []
    for block in _ITEM.findall(xml or "")[:limit]:
        t = _TITLE.search(block)
        if not t:
            continue
        title = _clean(t.group(1))
        if not title:
            continue
        lm = _LINK.search(block)
        link = _clean(lm.group(1) or lm.group(2) or "") if lm else ""
        dm = _DATE.search(block)
        published = _parse_date(_clean(dm.group(1))) if dm else iso(utcnow())
        out.append(Headline(
            title=title, source=source, tier=tier,
            published=published or iso(utcnow()), url=link,
            impact=60 if tier == 1 else 45,
            primary_confirmed=(tier == 1),
        ))
    return out


_FMTS = ("%a, %d %b %Y %H:%M:%S %z", "%a, %d %b %Y %H:%M:%S %Z",
         "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d %H:%M:%S")


def _parse_date(s: str) -> str | None:
    s = (s or "").strip().replace("GMT", "+0000").replace("UTC", "+0000")
    for f in _FMTS:
        try:
            d = datetime.strptime(s, f)
            if d.tzinfo is None:
                d = d.replace(tzinfo=timezone.utc)
            return iso(d)
        except ValueError:
            continue
    return None


def parse_treasury_csv(csv_text: str) -> dict[str, tuple[float, str]]:
    """Latest row of the par-yield CSV -> {tenor: (yield_pct, date_iso)}."""
    import csv as _csv
    import io

    rows = list(_csv.DictReader(io.StringIO(csv_text or "")))
    if not rows or "Date" not in rows[0]:
        return {}
    best_d, best = None, None
    for row in rows:
        try:
            d = datetime.strptime(row["Date"].strip(), "%m/%d/%Y").replace(tzinfo=timezone.utc)
        except (ValueError, AttributeError, KeyError):
            continue
        if best_d is None or d > best_d:
            best_d, best = d, row
    if best is None:
        return {}
    stamp = iso(best_d)
    out: dict[str, tuple[float, str]] = {}
    for col, key in (("2 Yr", "US2Y"), ("5 Yr", "US5Y"),
                     ("10 Yr", "US10Y"), ("30 Yr", "US30Y")):
        cell = (best.get(col) or "").strip()
        if not cell or cell in ("N/A", "."):
            continue
        try:
            out[key] = (float(cell), stamp)
        except ValueError:
            continue
    return out


def scan(previous: Snapshot | None = None, *, now: datetime | None = None,
         sources: Iterable[Source] | None = None) -> Snapshot:
    """One polling pass. Unreachable sources leave prior values untouched."""
    now = now or utcnow()
    snap = Snapshot(captured=iso(now))
    if previous:
        snap.quotes = dict(previous.quotes)
        snap.policy = dict(previous.policy)
        snap.gauges = dict(previous.gauges)
        snap.price_anchors = list(previous.price_anchors)
        snap.btc_window = dict(previous.btc_window)
        snap.equities = list(previous.equities)
        snap.earnings = list(previous.earnings)
        snap.liquidations = previous.liquidations
        snap.geo = list(previous.geo)
        snap.flows = list(previous.flows)
        snap.regime = previous.regime
        snap.regime_basis = previous.regime_basis

    heads: list[Headline] = []
    for src in (sources if sources is not None else SOURCES):
        if src.kind == "crypto":
            body = _http(src.url)
            if body is None:
                snap.errors.append(f"{src.name}: unreachable")
                continue
            key = (src.provides or ("BTC",))[0]
            sym = "ETHUSDT" if key == "ETH" else "BTCUSDT"
            got = parse_binance_ticker(body, symbol=sym)
            if got is None:
                snap.errors.append(f"{src.name}: unparseable ticker")
                continue
            label = {"BTC": "Bitcoin", "ETH": "Ethereum"}.get(key, key)
            snap.quotes[key] = Quote(
                key=key, value=got["price"], unit="usd", as_of=got["as_of"],
                source=src.name, tier=src.tier, url=src.url, label=label,
                change=got.get("change_pct"),
                change_unit="pct" if "change_pct" in got else "",
                confidence=0.95,
                note=("Last traded price on the venue itself. 24h range "
                      f"{got['low']:,.2f}-{got['high']:,.2f}."
                      if "high" in got and "low" in got
                      else "Last traded price on the venue itself."))
            if key == "BTC":
                # Feed the liquidity map, but only when the series has room:
                # see ANCHOR_MIN_GAP.
                last = max((a for a in snap.price_anchors), key=lambda a: a.date,
                           default=None)
                gap = None
                if last is not None:
                    try:
                        gap = (datetime.strptime(got["as_of"], "%Y-%m-%dT%H:%M:%SZ")
                               - datetime.strptime(last.date, "%Y-%m-%dT%H:%M:%SZ")
                               ).total_seconds()
                    except ValueError:
                        gap = None
                if last is None or gap is None or gap >= ANCHOR_MIN_GAP:
                    if not any(a.date == got["as_of"] and a.source == src.name
                               for a in snap.price_anchors):
                        snap.price_anchors.append(PriceAnchor(
                            date=got["as_of"], price=got["price"],
                            source=src.name, tier=src.tier, url=src.url,
                            note="Live last trade."))
                        snap.price_anchors.sort(key=lambda a: a.date)
            continue
        if src.kind == "curve":
            body = _http(src.url.format(year=now.year))
            if body is None:
                snap.errors.append(f"{src.name}: unreachable")
                continue
            got = parse_treasury_csv(body)
            if not got:
                snap.errors.append(f"{src.name}: no parseable rows")
                continue
            for key, (val, stamp) in got.items():
                prior = snap.quotes.get(key)
                chg = None
                if prior and prior.as_of != stamp:
                    chg = round((val - prior.value) * 100, 1)
                snap.quotes[key] = Quote(
                    key=key, value=val, unit="pct", as_of=stamp, source=src.name,
                    tier=src.tier, url=src.url.split("?")[0], label=f"UST {key[2:]}",
                    change=chg, change_unit="bp" if chg is not None else "",
                )
        elif src.kind == "rss":
            body = _http(src.url)
            if body is None:
                snap.errors.append(f"{src.name}: unreachable")
                continue
            found = parse_rss(body, src.name, src.tier)
            if not found:
                snap.errors.append(f"{src.name}: no items parsed")
            heads.extend(found)
        elif src.kind == "fred":
            if not os.environ.get("FRED_API_KEY"):
                snap.errors.append(f"{src.name}: FRED_API_KEY not set")
                continue
            from .data import fred
            for series, key, unit, label in (
                ("DGS2", "US2Y", "pct", "UST 2Y"), ("DGS10", "US10Y", "pct", "UST 10Y"),
                ("DFII10", "US10Y_REAL", "pct", "10Y real"),
                ("T10YIE", "US10Y_BE", "pct", "10Y breakeven"),
                ("VIXCLS", "VIX", "index", "VIX"),
                ("DCOILWTICO", "WTI", "usd_bbl", "WTI"),
                ("BAMLH0A0HYM2", "HY_OAS", "pct", "HY OAS"),
            ):
                s = fred.fetch(series, limit=3)
                if not getattr(s, "ok", False):
                    continue
                latest = s.latest                                # type: ignore[union-attr]
                prior = s.nth_last(1)                            # type: ignore[union-attr]
                if not latest.known:
                    continue
                chg = None
                if prior.known:
                    delta = latest.value - prior.value           # type: ignore[operator]
                    chg = round(delta * 100, 1) if unit == "pct" else round(delta, 3)
                snap.quotes[key] = Quote(
                    key=key, value=float(latest.value), unit=unit,  # type: ignore[arg-type]
                    as_of=iso(latest.as_of) or iso(now), source="FRED", tier=1,
                    url=f"https://fred.stlouisfed.org/series/{series}", label=label,
                    change=chg, change_unit="bp" if unit == "pct" else "abs",
                )

    if heads:
        snap.headlines = dedupe(heads)
    elif previous:
        snap.headlines = list(previous.headlines)
    if previous:
        snap.conflicts = list(previous.conflicts)
        snap.releases = list(previous.releases) or list(RELEASE_CLOCK)
    else:
        snap.releases = list(RELEASE_CLOCK)
    return snap


def dedupe(items: list[Headline], threshold: float = 0.7) -> list[Headline]:
    """Collapse the same story reported by many outlets into one event.

    Keeps the highest-tier carrier, because twenty wires repeating one agency
    release is one information event, not twenty.
    """
    def toks(s: str) -> set[str]:
        return set(re.sub(r"[^a-z0-9 ]", " ", s.lower()).split())

    kept: list[Headline] = []
    for h in sorted(items, key=lambda x: (x.tier, -x.impact)):
        th = toks(h.title)
        if not th:
            continue
        dup = False
        for k in kept:
            tk = toks(k.title)
            if tk and len(th & tk) / len(th | tk) >= threshold:
                dup = True
                break
        if not dup:
            kept.append(h)
    kept.sort(key=lambda h: (h.tier, -h.impact, h.published), reverse=False)
    return kept


def merge(previous: Snapshot | None, fresh: Snapshot) -> Snapshot:
    """Fresh wins per field; anything fresh lacks keeps its original timestamp."""
    if previous is None:
        return fresh
    for key, q in previous.quotes.items():
        fresh.quotes.setdefault(key, q)
    for key, g in previous.gauges.items():
        fresh.gauges.setdefault(key, g)
    if not fresh.price_anchors:
        fresh.price_anchors = list(previous.price_anchors)
    if not fresh.btc_window:
        fresh.btc_window = dict(previous.btc_window)
    if not fresh.equities:
        fresh.equities = list(previous.equities)
    if not fresh.earnings:
        fresh.earnings = list(previous.earnings)
    if fresh.liquidations is None:
        fresh.liquidations = previous.liquidations
    if not fresh.geo:
        fresh.geo = list(previous.geo)
    if not fresh.flows:
        fresh.flows = list(previous.flows)
    if not fresh.headlines:
        fresh.headlines = list(previous.headlines)
    return fresh
