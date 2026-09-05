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
    "liquidation_ladder",
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


@dataclass
class Snapshot:
    captured: str
    quotes: dict[str, Quote] = field(default_factory=dict)
    headlines: list[Headline] = field(default_factory=list)
    releases: list[dict[str, Any]] = field(default_factory=list)
    policy: dict[str, Any] = field(default_factory=dict)
    gauges: dict[str, Gauge] = field(default_factory=dict)
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
)

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
        snap.liquidations = previous.liquidations
        snap.geo = list(previous.geo)
        snap.flows = list(previous.flows)
        snap.regime = previous.regime
        snap.regime_basis = previous.regime_basis

    heads: list[Headline] = []
    for src in (sources if sources is not None else SOURCES):
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
    if fresh.liquidations is None:
        fresh.liquidations = previous.liquidations
    if not fresh.geo:
        fresh.geo = list(previous.geo)
    if not fresh.flows:
        fresh.flows = list(previous.flows)
    if not fresh.headlines:
        fresh.headlines = list(previous.headlines)
    return fresh
