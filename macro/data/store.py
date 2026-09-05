"""Local snapshot store.

Snapshots are timestamped.  When one is read back, its age is attached to every
observation so that stale data is visibly stale rather than silently current.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timedelta

from ..types import Observation, SourceRef, Tier, as_dict, iso, utcnow

DEFAULT_DIR = os.environ.get("MACRO_STATE_DIR", "state")


def _path(name: str, directory: str | None = None) -> str:
    d = directory or DEFAULT_DIR
    os.makedirs(d, exist_ok=True)
    safe = "".join(c for c in name if c.isalnum() or c in "-_.")
    return os.path.join(d, f"{safe}.json")


def save(name: str, payload: dict, directory: str | None = None) -> str:
    body = {"saved_at": iso(utcnow()), "payload": as_dict(payload)}
    p = _path(name, directory)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(body, fh, indent=2, sort_keys=True)
    os.replace(tmp, p)   # atomic: a crash mid-write cannot leave a partial snapshot
    return p


@dataclass(frozen=True)
class Snapshot:
    name: str
    saved_at: datetime | None
    payload: dict
    age: timedelta | None

    @property
    def stale(self) -> bool:
        return self.age is None or self.age > timedelta(hours=24)

    def render_header(self) -> str:
        if self.saved_at is None:
            return f"snapshot '{self.name}': timestamp UNKNOWN - treat as unusable"
        hrs = self.age.total_seconds() / 3600 if self.age else 0
        mark = "STALE" if self.stale else "fresh"
        return f"snapshot '{self.name}' saved {iso(self.saved_at)} ({hrs:.1f}h ago, {mark})"


def load(name: str, directory: str | None = None) -> Snapshot | None:
    p = _path(name, directory)
    if not os.path.exists(p):
        return None
    try:
        with open(p, encoding="utf-8") as fh:
            body = json.load(fh)
    except (json.JSONDecodeError, OSError):
        return None
    ts = body.get("saved_at")
    saved = None
    if isinstance(ts, str):
        try:
            saved = datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(
                tzinfo=utcnow().tzinfo
            )
        except ValueError:
            saved = None
    age = (utcnow() - saved) if saved else None
    return Snapshot(name, saved, body.get("payload") or {}, age)


__all__ = ["DEFAULT_DIR", "Snapshot", "load", "save"]
