"""US Treasury daily par yield curve adapter (no API key required).

Source: home.treasury.gov XML/CSV feed - Tier 1 primary for the US curve.
"""

from __future__ import annotations

import csv
import io
from datetime import datetime, timezone

from ..types import Observation, SourceRef, Tier, utcnow
from .base import Series, Unavailable, http_get

CSV_URL = (
    "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/"
    "daily-treasury-rates.csv/{year}/all?type=daily_treasury_yield_curve"
    "&field_tdr_date_value={year}&page&_format=csv"
)

TENOR_COLUMNS = {
    "1 Mo": "1M", "1.5 Month": "6W", "2 Mo": "2M", "3 Mo": "3M", "4 Mo": "4M",
    "6 Mo": "6M", "1 Yr": "1Y", "2 Yr": "2Y", "3 Yr": "3Y", "5 Yr": "5Y",
    "7 Yr": "7Y", "10 Yr": "10Y", "20 Yr": "20Y", "30 Yr": "30Y",
}

_SRC = SourceRef(
    name="US Department of the Treasury - Daily Par Yield Curve",
    tier=Tier.PRIMARY,
    url="https://home.treasury.gov/resource-center/data-chart-center/interest-rates/",
    is_primary_document=True,
)


def fetch_curve(year: int | None = None) -> dict[str, Series] | Unavailable:
    """Return one Series per tenor, in percent, ascending by date."""
    year = year or utcnow().year
    raw = http_get(CSV_URL.format(year=year))
    if isinstance(raw, Unavailable):
        return raw
    try:
        rows = list(csv.DictReader(io.StringIO(raw)))
    except Exception as e:  # noqa: BLE001
        return Unavailable("US Treasury", f"CSV parse failed: {type(e).__name__}: {e}")
    if not rows:
        return Unavailable("US Treasury", f"no rows returned for {year}")
    if "Date" not in rows[0]:
        return Unavailable(
            "US Treasury",
            "response did not contain a Date column (endpoint shape may have changed)",
            hint="verify the CSV endpoint at home.treasury.gov before relying on it",
        )

    buckets: dict[str, list[tuple[datetime, float]]] = {v: [] for v in TENOR_COLUMNS.values()}
    for row in rows:
        try:
            d = datetime.strptime(row["Date"].strip(), "%m/%d/%Y").replace(tzinfo=timezone.utc)
        except (KeyError, ValueError, AttributeError):
            continue
        for col, tenor in TENOR_COLUMNS.items():
            cell = (row.get(col) or "").strip()
            if not cell or cell in ("N/A", "."):
                continue
            try:
                buckets[tenor].append((d, float(cell)))
            except ValueError:
                continue

    out: dict[str, Series] = {}
    for tenor, pts in buckets.items():
        if not pts:
            continue
        pts.sort(key=lambda p: p[0])
        src = SourceRef(_SRC.name, _SRC.tier, _SRC.url,
                        published_at=pts[-1][0], retrieved_at=utcnow(),
                        is_primary_document=True)
        out[tenor] = Series(f"UST_{tenor}", f"US Treasury par yield {tenor}", "pct",
                            tuple(pts), src)
    if not out:
        return Unavailable("US Treasury", "no usable tenor data parsed from the CSV")
    return out


__all__ = ["CSV_URL", "TENOR_COLUMNS", "fetch_curve"]
