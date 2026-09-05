"""FRED adapter (St. Louis Fed).

Requires ``FRED_API_KEY``.  Without it the adapter reports UNAVAILABLE - it
does not fall back to any bundled numbers, because a stale number rendered as
current is worse than a blank field.

FRED encodes missing observations as the string ".".  Parsing that as zero is a
real and well-known way to silently corrupt a yield series, so it is dropped
explicitly.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from urllib.parse import urlencode

from ..types import SourceRef, Tier, utcnow
from .base import Series, Unavailable, http_json

BASE = "https://api.stlouisfed.org/fred/series/observations"

# Series that matter for this system, with their true units.
CATALOG: dict[str, tuple[str, str]] = {
    "DGS2": ("US 2Y Treasury constant maturity", "pct"),
    "DGS5": ("US 5Y Treasury constant maturity", "pct"),
    "DGS10": ("US 10Y Treasury constant maturity", "pct"),
    "DGS30": ("US 30Y Treasury constant maturity", "pct"),
    "DFII10": ("US 10Y TIPS real yield", "pct"),
    "T10YIE": ("US 10Y breakeven inflation", "pct"),
    "T10Y2Y": ("US 2s10s spread", "pct"),
    "SOFR": ("Secured Overnight Financing Rate", "pct"),
    "EFFR": ("Effective Federal Funds Rate", "pct"),
    "IORB": ("Interest on Reserve Balances", "pct"),
    "BAMLH0A0HYM2": ("ICE BofA US High Yield OAS", "pct"),
    "BAMLC0A0CM": ("ICE BofA US Corporate OAS", "pct"),
    "VIXCLS": ("CBOE VIX", "index"),
    "DTWEXBGS": ("Nominal Broad USD Index", "index"),
    "DEXUSEU": ("USD per EUR", "usd_per_eur"),
    "DEXJPUS": ("JPY per USD", "jpy_per_usd"),
    "WALCL": ("Fed total assets", "usd_mn"),
    "RRPONTSYD": ("Overnight reverse repo volume", "usd_bn"),
    "WRESBAL": ("Reserve balances at Federal Reserve Banks", "usd_bn"),
    "DCOILWTICO": ("WTI crude spot", "usd_bbl"),
    "SP500": ("S&P 500 index", "index"),
    "NFCI": ("Chicago Fed National Financial Conditions Index", "index"),
}

_SRC = SourceRef(
    name="FRED (Federal Reserve Bank of St. Louis)",
    tier=Tier.PRIMARY,
    url="https://fred.stlouisfed.org/",
    is_primary_document=False,
)


def available() -> bool:
    return bool(os.environ.get("FRED_API_KEY"))


def fetch(series_id: str, *, limit: int = 60, api_key: str | None = None) -> Series | Unavailable:
    key = api_key or os.environ.get("FRED_API_KEY")
    if not key:
        return Unavailable(
            "FRED",
            "FRED_API_KEY is not set",
            hint="get a free key at https://fredaccount.stlouisfed.org/apikeys and "
                 "export FRED_API_KEY. No substitute values are bundled.",
        )
    label, unit = CATALOG.get(series_id, (series_id, "unknown_unit"))
    qs = urlencode({
        "series_id": series_id, "api_key": key, "file_type": "json",
        "sort_order": "desc", "limit": max(1, int(limit)),
    })
    payload = http_json(f"{BASE}?{qs}")
    if isinstance(payload, Unavailable):
        return payload
    obs = payload.get("observations")
    if not isinstance(obs, list):
        return Unavailable("FRED", f"unexpected payload shape for {series_id}")

    points: list[tuple[datetime, float]] = []
    dropped = 0
    for row in obs:
        raw = row.get("value")
        if raw in (None, ".", "", "NaN"):
            dropped += 1
            continue
        try:
            v = float(raw)
        except (TypeError, ValueError):
            dropped += 1
            continue
        try:
            ts = datetime.strptime(row["date"], "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except (KeyError, ValueError):
            dropped += 1
            continue
        points.append((ts, v))
    points.sort(key=lambda p: p[0])

    if not points:
        return Unavailable(
            "FRED", f"{series_id} returned no usable observations "
                    f"({dropped} missing markers dropped)"
        )
    src = SourceRef(_SRC.name, _SRC.tier, f"https://fred.stlouisfed.org/series/{series_id}",
                    published_at=points[-1][0], retrieved_at=utcnow())
    return Series(series_id, label, unit, tuple(points), src)


__all__ = ["BASE", "CATALOG", "available", "fetch"]
