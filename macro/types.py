"""Core value types and the no-fabrication contract.

Design rule enforced here rather than in prose: every number that enters an
engine carries its provenance and its timestamp.  An engine that lacks an
input returns :class:`Insufficient` instead of a plausible-looking number.
There is deliberately no default value anywhere in this module.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Iterable, Sequence


# --------------------------------------------------------------------------
# Epistemic labelling (spec section 28: FACT / INTERPRETATION / SCENARIO /
# SPECULATION must never be mixed).
# --------------------------------------------------------------------------


class Category(str, Enum):
    FACT = "FACT"
    INTERPRETATION = "INTERPRETATION"
    SCENARIO = "SCENARIO"
    SPECULATION = "SPECULATION"


class Tier(int, Enum):
    """Source hierarchy (spec section 14).  Lower is more reliable."""

    PRIMARY = 1          # central banks, statistical agencies, official filings
    INSTITUTIONAL = 2    # Bloomberg / Reuters / FT / WSJ / exchange notices
    PROFESSIONAL = 3     # named economists, strategists, credible journalists
    SOCIAL = 4           # X, Telegram, Reddit, blogs, anonymous accounts
    UNKNOWN = 9

    @property
    def label(self) -> str:
        return {
            Tier.PRIMARY: "TIER 1 - PRIMARY",
            Tier.INSTITUTIONAL: "TIER 2 - INSTITUTIONAL",
            Tier.PROFESSIONAL: "TIER 3 - PROFESSIONAL",
            Tier.SOCIAL: "TIER 4 - SOCIAL/ALTERNATIVE",
            Tier.UNKNOWN: "TIER ? - UNCLASSIFIED",
        }[self]


class Verification(str, Enum):
    CONFIRMED = "CONFIRMED"                      # primary source in hand
    OFFICIAL_PENDING = "OFFICIAL - PENDING TEXT"  # official but text not parsed
    PRELIMINARY = "PRELIMINARY"                  # flash / advance / provisional
    REPORTED = "REPORTED"                        # institutional report, 1 source
    UNCONFIRMED = "UNCONFIRMED - REQUIRES VERIFICATION"
    DISPUTED = "DISPUTED"


class AssetClass(str, Enum):
    FX = "FX"
    RATES = "RATES"
    EQUITY = "EQUITY"
    CREDIT = "CREDIT"
    COMMODITY = "COMMODITY"
    CRYPTO = "CRYPTO"
    VOL = "VOL"


# --------------------------------------------------------------------------
# Sources and observations
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class SourceRef:
    name: str
    tier: Tier = Tier.UNKNOWN
    url: str | None = None
    published_at: datetime | None = None
    retrieved_at: datetime | None = None
    is_primary_document: bool = False

    def describe(self) -> str:
        stamp = iso(self.published_at) or "no publication timestamp"
        return f"{self.name} [{self.tier.label}] ({stamp})"


UNSOURCED = SourceRef(name="unsourced", tier=Tier.UNKNOWN)


@dataclass(frozen=True)
class Observation:
    """A single measured quantity.  ``value is None`` means genuinely unknown.

    ``unit`` is mandatory and is compared strictly by the engines: a unit
    mismatch (e.g. CPI m/m against CPI y/y) is a silent-wrong-answer class of
    bug, so it raises rather than degrading.
    """

    value: float | None
    unit: str
    as_of: datetime | None = None
    source: SourceRef = UNSOURCED
    category: Category = Category.FACT
    note: str = ""

    @property
    def known(self) -> bool:
        return self.value is not None and not (
            isinstance(self.value, float) and math.isnan(self.value)
        )

    def require(self, what: str) -> float:
        if not self.known:
            raise MissingInput(what)
        return float(self.value)  # type: ignore[arg-type]

    def render(self, digits: int = 2) -> str:
        if not self.known:
            return "UNKNOWN"
        return f"{self.value:.{digits}f} {self.unit}".strip()


def unknown(unit: str, note: str = "") -> Observation:
    return Observation(value=None, unit=unit, note=note)


def observed(
    value: float,
    unit: str,
    source: SourceRef = UNSOURCED,
    as_of: datetime | None = None,
    category: Category = Category.FACT,
    note: str = "",
) -> Observation:
    return Observation(value, unit, as_of, source, category, note)


class MissingInput(Exception):
    """Raised internally when a required Observation is unknown."""


def same_unit(*obs: Observation) -> None:
    """Raise if two *known* quantities in one calculation carry different units.

    Unknown observations are skipped: an UNKNOWN placeholder carries a nominal
    unit only so that it renders, and must not manufacture a mismatch.
    """
    units = {o.unit for o in obs if o is not None and o.known}
    if len(units) > 1:
        raise UnitMismatch(f"incompatible units in one calculation: {sorted(units)}")


class UnitMismatch(Exception):
    pass


# --------------------------------------------------------------------------
# Engine results: every engine returns something with `.ok`
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Insufficient:
    """Returned instead of a number when inputs are missing or degenerate."""

    reason: str
    missing: tuple[str, ...] = ()
    ok: bool = False

    def render(self) -> str:
        miss = f" missing={list(self.missing)}" if self.missing else ""
        return f"INSUFFICIENT DATA: {self.reason}{miss}"


@dataclass(frozen=True)
class Ok:
    ok: bool = True


def insufficient(reason: str, *missing: str) -> Insufficient:
    return Insufficient(reason=reason, missing=tuple(missing))


# --------------------------------------------------------------------------
# Small shared helpers
# --------------------------------------------------------------------------


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def clamp(x: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, x))


def stdev(xs: Sequence[float]) -> float | None:
    """Sample standard deviation; None when it cannot be defined."""
    n = len(xs)
    if n < 2:
        return None
    mean = sum(xs) / n
    var = sum((x - mean) ** 2 for x in xs) / (n - 1)
    if var <= 0:
        return None
    return math.sqrt(var)


def as_dict(obj: Any) -> Any:
    """JSON-safe projection used by the renderers."""
    from dataclasses import asdict, is_dataclass

    if is_dataclass(obj) and not isinstance(obj, type):
        return {k: as_dict(v) for k, v in asdict(obj).items()}
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, datetime):
        return iso(obj)
    if isinstance(obj, dict):
        return {str(k): as_dict(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [as_dict(v) for v in obj]
    if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
        return None
    return obj


__all__ = [
    "AssetClass", "Category", "Insufficient", "MissingInput", "Observation",
    "Ok", "SourceRef", "Tier", "UNSOURCED", "UnitMismatch", "Verification",
    "as_dict", "clamp", "insufficient", "iso", "observed", "replace",
    "same_unit", "stdev", "unknown", "utcnow",
]
