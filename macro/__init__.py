"""Institutional Macro Intelligence & News Radar.

A macro event-intelligence system built to one non-negotiable rule: it reports
what it actually knows, with provenance, and returns UNKNOWN everywhere else.
It never fabricates a source, a timestamp, a consensus, a market level or a
market reaction, and it never claims non-public access to anything.

Engines
-------
surprise      expectation vs actual, standardised only against supplied history
scoring       urgency / information latency / credibility / priority
calendar_spec global release metadata (semantics and clocks, never values)
centralbank   policy-language tone and statement diffing
curve         yield-curve regime classification
liquidity     funding conditions and the unexplained-move detector
reaction      derived cross-asset transmission maps and second-order analysis
structure     swings, BOS/CHoCH, sweeps, FVGs, displacement - no lookahead
setups        R:R-gated setup construction and the whipsaw protocol
sources       source tiering and the confirmation engine
noise         does this change what the market already believed?
preevent      T-60 / T-30 / T-15 / T-5 preparation
brief         the daily 12-section institutional dashboard
radar         the event book and the command surface
"""

__version__ = "1.0.0"

from . import (
    brief, calendar_spec, centralbank, curve, events, liquidity, noise,
    preevent, radar, reaction, regime, scoring, setups, sources, state,
    structure, surprise, types,
)

__all__ = [
    "__version__", "brief", "calendar_spec", "centralbank", "curve", "events",
    "liquidity", "noise", "preevent", "radar", "reaction", "regime", "scoring",
    "setups", "sources", "state", "structure", "surprise", "types",
]
