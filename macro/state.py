"""Live market state container.

A field that was never supplied stays UNKNOWN.  Nothing in this container has a
default numeric value, and nothing is carried forward from a previous session
without its timestamp coming with it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from .curve import CurveRead, classify
from .liquidity import ConditionsRead, assess
from .regime import MacroRegime, RiskRegime
from .types import Insufficient, Observation, SourceRef, iso, unknown, utcnow

# Canonical keys.  "_PRIOR" holds the previous session's close for the same key.
CORE_KEYS = (
    "US2Y", "US5Y", "US10Y", "US30Y", "US10Y_REAL", "US10Y_BREAKEVEN",
    "DXY", "EURUSD", "USDJPY", "SPX", "NDX", "VIX", "GOLD", "WTI", "BTC", "ETH",
    "HY_OAS", "IG_OAS", "SOFR", "EFFR", "IORB",
)


@dataclass
class MarketState:
    as_of: datetime = field(default_factory=utcnow)
    regime: MacroRegime = MacroRegime.UNKNOWN
    regime_basis: str = "UNKNOWN - regime has not been established from data"
    observations: dict[str, Observation] = field(default_factory=dict)
    changes_z: dict[str, float] = field(default_factory=dict)
    session_levels: dict[str, float] = field(default_factory=dict)
    market_pricing: dict[str, str] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    def get(self, key: str, unit: str = "?") -> Observation:
        return self.observations.get(key) or unknown(unit, note=f"{key} not supplied")

    def put(self, key: str, obs: Observation) -> None:
        self.observations[key] = obs

    @property
    def coverage(self) -> float:
        known = sum(1 for k in CORE_KEYS if self.get(k).known)
        return known / len(CORE_KEYS)

    def missing_core(self) -> list[str]:
        return [k for k in CORE_KEYS if not self.get(k).known]

    def curve(self) -> CurveRead | Insufficient:
        return classify(
            y2_now=self.get("US2Y", "pct"), y2_prior=self.get("US2Y_PRIOR", "pct"),
            y10_now=self.get("US10Y", "pct"), y10_prior=self.get("US10Y_PRIOR", "pct"),
            y5_now=self.get("US5Y", "pct"), y5_prior=self.get("US5Y_PRIOR", "pct"),
            y30_now=self.get("US30Y", "pct"), y30_prior=self.get("US30Y_PRIOR", "pct"),
            real10_now=self.get("US10Y_REAL", "pct"),
            real10_prior=self.get("US10Y_REAL_PRIOR", "pct"),
            breakeven10_now=self.get("US10Y_BREAKEVEN", "pct"),
            breakeven10_prior=self.get("US10Y_BREAKEVEN_PRIOR", "pct"),
        )

    def conditions(self) -> ConditionsRead | Insufficient:
        levels = {
            "vix": self.get("VIX", "index"),
            "hy_oas_bp": self.get("HY_OAS", "bp"),
            "ig_oas_bp": self.get("IG_OAS", "bp"),
            "dxy": self.get("DXY", "index"),
        }
        spread = unknown("bp")
        s, i = self.get("SOFR", "pct"), self.get("IORB", "pct")
        if s.known and i.known:
            spread = Observation(
                (s.require("sofr") - i.require("iorb")) * 100.0, "bp",
                as_of=s.as_of, note="derived: SOFR - IORB",
            )
        levels["sofr_iorb_spread_bp"] = spread
        return assess(levels=levels, changes_z=self.changes_z)

    def render(self) -> str:
        lines = [
            f"MARKET STATE as of {iso(self.as_of)}",
            f"  Regime: {self.regime.value} - {self.regime_basis}",
            f"  Core coverage: {self.coverage:.0%} ({len(CORE_KEYS) - len(self.missing_core())}"
            f"/{len(CORE_KEYS)} fields)",
        ]
        for k in CORE_KEYS:
            o = self.get(k)
            src = o.source.name if o.source and o.source.name != "unsourced" else "-"
            lines.append(f"    {k:<16} {o.render():>18}   {iso(o.as_of) or '':<21} {src}")
        if self.missing_core():
            lines.append(f"  MISSING: {', '.join(self.missing_core())}")
        for n in self.notes:
            lines.append(f"  note: {n}")
        return "\n".join(lines)


def from_fred(state: MarketState | None = None, *, limit: int = 30) -> tuple[MarketState, list[str]]:
    """Populate a state from FRED where a key is configured. Returns (state, problems)."""
    from .data import fred

    state = state or MarketState()
    problems: list[str] = []
    mapping = {
        "US2Y": "DGS2", "US5Y": "DGS5", "US10Y": "DGS10", "US30Y": "DGS30",
        "US10Y_REAL": "DFII10", "US10Y_BREAKEVEN": "T10YIE", "VIX": "VIXCLS",
        "DXY": "DTWEXBGS", "SPX": "SP500", "WTI": "DCOILWTICO", "SOFR": "SOFR",
        "EFFR": "EFFR", "IORB": "IORB",
    }
    for key, sid in mapping.items():
        s = fred.fetch(sid, limit=limit)
        if not getattr(s, "ok", False):
            problems.append(s.render())          # type: ignore[union-attr]
            continue
        state.put(key, s.latest)                  # type: ignore[union-attr]
        state.put(f"{key}_PRIOR", s.nth_last(1))  # type: ignore[union-attr]
    if problems:
        state.notes.append(
            f"{len(problems)} series unavailable; those fields remain UNKNOWN rather "
            "than being back-filled"
        )
    return state, problems


__all__ = ["CORE_KEYS", "MarketState", "from_fred"]
