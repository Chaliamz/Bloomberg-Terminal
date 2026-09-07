"""Append-only store for observations found by a scheduled re-scan.

The seed in ``macro/seed.py`` is the captured baseline and is edited by hand.
Anything a later scan finds lands here instead, as data rather than as code, so
an unattended run never rewrites Python.

Every entry goes through ``PriceAnchor``, which rejects a missing source, tier
or timestamp, so the no-fabrication contract holds on this path too. The store
is append-only and de-duplicated on (date, source): re-running a scan that finds
the same print again is a no-op, and a scan that finds nothing changes nothing.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone

from .live import PriceAnchor

STORE = os.path.join("state", "observations.json")
LOG = os.path.join("state", "refresh-log.jsonl")


def _parse(stamp: str) -> datetime:
    return datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def load(path: str = STORE) -> list[dict]:
    """Read the store. A missing or corrupt file is an empty store, not a crash."""
    try:
        with open(path, encoding="utf-8") as fh:
            raw = json.load(fh)
    except (OSError, ValueError):
        return []
    if not isinstance(raw, list):
        return []
    out = []
    for row in raw:
        if not isinstance(row, dict):
            continue
        try:
            PriceAnchor(**row)          # validates; the dict is what we keep
        except (TypeError, ValueError):
            continue
        out.append(row)
    return out


def add(date: str, price: float, source: str, tier: int, url: str = "",
        note: str = "", path: str = STORE) -> tuple[bool, str]:
    """Validate and append one observation.

    Returns ``(added, reason)``. A duplicate (date, source) is refused rather
    than appended, so the store cannot grow on repeated scans of the same page.
    A price that is not finite and positive is refused: a zero or a NaN reaching
    the heatmap would silently poison every level derived from it.
    """
    try:
        price = float(price)
    except (TypeError, ValueError):
        return False, "price is not a number"
    if not (price > 0) or price != price or price in (float("inf"), float("-inf")):
        return False, "price must be finite and positive"
    try:
        anchor = PriceAnchor(date=date, price=price, source=source, tier=int(tier),
                             url=url, note=note)
    except (TypeError, ValueError) as exc:
        return False, str(exc)

    now = datetime.now(timezone.utc)
    try:
        when = _parse(anchor.date)
    except ValueError:
        return False, "date must be YYYY-MM-DDTHH:MM:SSZ"
    if when > now:
        # A future stamp would make the page read fresher than reality.
        return False, "observation is stamped in the future"

    rows = load(path)
    for row in rows:
        if row.get("date") == anchor.date and row.get("source") == anchor.source:
            return False, "already stored"
    rows.append({"date": anchor.date, "price": anchor.price, "source": anchor.source,
                 "tier": anchor.tier, "url": anchor.url, "note": anchor.note})
    rows.sort(key=lambda r: r["date"])
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(rows, fh, indent=1, ensure_ascii=False)
    os.replace(tmp, path)               # atomic: a crash never truncates the store
    return True, "added"


def merge(anchors: list[PriceAnchor], path: str = STORE) -> list[PriceAnchor]:
    """Baseline anchors plus anything a later scan stored, de-duplicated."""
    seen = {(a.date, a.source) for a in anchors}
    out = list(anchors)
    for row in load(path):
        if (row["date"], row["source"]) in seen:
            continue
        seen.add((row["date"], row["source"]))
        out.append(PriceAnchor(**row))
    out.sort(key=lambda a: a.date)
    return out


def heartbeat(note: str, found: int = 0, path: str = LOG) -> str:
    """Append one line recording that a scheduled run happened.

    A run that finds nothing must not touch the page - that is what keeps the
    age counter honest - but it must still leave a trace, or a loop that has
    silently died looks exactly like a loop with nothing to report. This is that
    trace, and it is the only way to tell the two apart from outside.

    Append-only JSON Lines: a corrupt or partial line costs one record, not the
    file, which matters for something written unattended every hour.
    """
    row = {"at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "found": int(found), "note": str(note)[:400]}
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    return row["at"]


def log_tail(n: int = 20, path: str = LOG) -> list[dict]:
    """Read back the last n runs. A bad line is skipped, never fatal."""
    try:
        with open(path, encoding="utf-8") as fh:
            lines = fh.readlines()
    except OSError:
        return []
    out = []
    for line in lines[-n:]:
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict) and "at" in row:
            out.append(row)
    return out
