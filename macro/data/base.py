"""Data-source contract.

The single rule: an adapter returns real data with provenance, or it returns
:class:`Unavailable`.  It never returns a placeholder, a last-known-good value
presented as current, or a zero.  Downstream engines already handle UNKNOWN;
they cannot handle a lie.
"""

from __future__ import annotations

import json
import os
import ssl
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from ..types import Observation, SourceRef, Tier, utcnow

USER_AGENT = "macro-radar/1.0 (+institutional macro intelligence; contact: operator)"
DEFAULT_TIMEOUT = 15.0


@dataclass(frozen=True)
class Unavailable:
    source: str
    reason: str
    hint: str = ""
    ok: bool = False

    def render(self) -> str:
        h = f" | {self.hint}" if self.hint else ""
        return f"DATA UNAVAILABLE [{self.source}]: {self.reason}{h}"


@dataclass(frozen=True)
class Series:
    """A dated series with provenance attached to the whole series."""

    series_id: str
    label: str
    unit: str
    points: tuple[tuple[datetime, float], ...]
    source: SourceRef
    ok: bool = True

    @property
    def latest(self) -> Observation:
        if not self.points:
            return Observation(None, self.unit, note=f"{self.series_id}: empty series")
        ts, v = self.points[-1]
        return Observation(v, self.unit, as_of=ts, source=self.source)

    def nth_last(self, n: int = 1) -> Observation:
        if len(self.points) <= n:
            return Observation(
                None, self.unit,
                note=f"{self.series_id}: only {len(self.points)} points, cannot look back {n}",
            )
        ts, v = self.points[-1 - n]
        return Observation(v, self.unit, as_of=ts, source=self.source)

    def changes(self) -> list[float]:
        return [
            self.points[i][1] - self.points[i - 1][1] for i in range(1, len(self.points))
        ]


def _ssl_context() -> ssl.SSLContext:
    """Honour the environment's CA bundle. TLS verification is never disabled."""
    for var in ("SSL_CERT_FILE", "REQUESTS_CA_BUNDLE", "CURL_CA_BUNDLE"):
        path = os.environ.get(var)
        if path and os.path.exists(path):
            return ssl.create_default_context(cafile=path)
    for path in ("/root/.ccr/ca-bundle.crt", "/etc/ssl/certs/ca-certificates.crt"):
        if os.path.exists(path):
            try:
                return ssl.create_default_context(cafile=path)
            except Exception:
                break
    return ssl.create_default_context()


def http_get(url: str, timeout: float = DEFAULT_TIMEOUT) -> str | Unavailable:
    """Plain GET honouring proxy env vars and the system CA bundle."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_ssl_context()) as r:
            if r.status != 200:
                return Unavailable(url, f"HTTP {r.status}")
            return r.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return Unavailable(url, f"HTTP {e.code} {e.reason}")
    except urllib.error.URLError as e:
        return Unavailable(
            url, f"network error: {e.reason}",
            hint="check outbound access / proxy configuration; no cached value is "
                 "substituted for live data",
        )
    except Exception as e:  # noqa: BLE001 - adapters must never raise into engines
        return Unavailable(url, f"{type(e).__name__}: {e}")


def http_json(url: str, timeout: float = DEFAULT_TIMEOUT) -> Any | Unavailable:
    raw = http_get(url, timeout)
    if isinstance(raw, Unavailable):
        return raw
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        return Unavailable(url, f"response was not valid JSON: {e}")


__all__ = ["DEFAULT_TIMEOUT", "Series", "Unavailable", "http_get", "http_json"]
