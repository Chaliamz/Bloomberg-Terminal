"""Command-line entry point:  python -m macro <command> [options]"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone

from .brief import build as build_brief
from .radar import COMMANDS, Radar
from .regime import MacroRegime
from .render.html import render as render_html
from .state import MarketState, from_fred
from .types import Observation, SourceRef, Tier, iso, observed, utcnow

CLI_TO_COMMAND = {
    "radar": "RADAR", "next": "NEXT", "speeches": "SPEECHES", "fed": "FED",
    "ecb": "ECB", "cpi": "CPI", "nfp": "NFP", "risk": "RISK",
    "liquidity": "LIQUIDITY", "market": "MARKET", "setup": "SETUP",
    "alert": "ALERT", "pre-event": "PRE-EVENT", "what-matters": "WHAT MATTERS",
}


def load_state_file(path: str) -> MarketState:
    """Load a market state from JSON.

    Any field absent from the file stays UNKNOWN. Malformed entries are
    reported and skipped rather than coerced to a number.
    """
    with open(path, encoding="utf-8") as fh:
        raw = json.load(fh)

    st = MarketState()
    reg = str(raw.get("regime", "UNKNOWN")).upper().replace("-", "_")
    try:
        st.regime = MacroRegime[reg]
    except KeyError:
        try:
            st.regime = MacroRegime(raw.get("regime"))
        except ValueError:
            st.notes.append(f"unrecognised regime '{raw.get('regime')}': left UNKNOWN")
    st.regime_basis = raw.get("regime_basis") or st.regime_basis

    for key, spec in (raw.get("observations") or {}).items():
        if key.startswith("_"):
            continue
        if not isinstance(spec, dict) or "value" not in spec or "unit" not in spec:
            st.notes.append(f"observation '{key}' skipped: needs both 'value' and 'unit'")
            continue
        if spec["value"] is None:
            # An explicit null is a deliberately empty slot, not a broken row.
            continue
        try:
            value = float(spec["value"])
        except (TypeError, ValueError):
            st.notes.append(f"observation '{key}' skipped: value is not numeric")
            continue
        as_of = None
        if spec.get("as_of"):
            try:
                as_of = datetime.fromisoformat(str(spec["as_of"]).replace("Z", "+00:00"))
            except ValueError:
                st.notes.append(f"observation '{key}': unparseable as_of, timestamp left UNKNOWN")
        src = SourceRef(
            name=spec.get("source", "user-supplied"),
            tier=Tier[spec["tier"]] if spec.get("tier") in Tier.__members__ else Tier.UNKNOWN,
            url=spec.get("url"), published_at=as_of, retrieved_at=utcnow(),
        )
        st.put(key, Observation(value, str(spec["unit"]), as_of=as_of, source=src))

    for k, v in (raw.get("changes_z") or {}).items():
        if k.startswith("_") or v is None:
            continue
        try:
            st.changes_z[k] = float(v)
        except (TypeError, ValueError):
            st.notes.append(f"changes_z['{k}'] skipped: not numeric")
    for k, v in (raw.get("session_levels") or {}).items():
        if k.startswith("_") or v is None:
            continue
        try:
            st.session_levels[k] = float(v)
        except (TypeError, ValueError):
            st.notes.append(f"session_levels['{k}'] skipped: not numeric")
    st.market_pricing.update(
        {str(k): str(v) for k, v in (raw.get("market_pricing") or {}).items()
         if not str(k).startswith("_") and str(v).strip()}
    )
    return st


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="macro",
        description="Institutional macro intelligence & news radar. Reports only "
                    "what it knows; everything else is UNKNOWN.",
    )
    p.add_argument("command",
                   choices=sorted(CLI_TO_COMMAND) + ["demo", "selftest", "coverage", "board"],
                   help="command to run")
    p.add_argument("arg", nargs="?", help="argument (e.g. a release code for pre-event)")
    p.add_argument("--state", help="path to a market-state JSON file")
    p.add_argument("--fetch", action="store_true",
                   help="populate the state from FRED (requires FRED_API_KEY)")
    p.add_argument("--html", metavar="OUT", help="also write the single-file HTML terminal")
    p.add_argument("--json", action="store_true", help="emit machine-readable JSON where supported")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.command == "selftest":
        return _selftest()
    if args.command == "board":
        from .board import main as board_main
        return board_main(args.arg or "board/cold-start-terminal.html")
    if args.command == "coverage":
        from .calendar_spec import RELEASES, coverage_report
        print(f"{len(RELEASES)} releases modelled")
        for country, n in coverage_report().items():
            print(f"  {n:>3}  {country}")
        return 0

    radar = Radar()
    if args.state:
        if not os.path.exists(args.state):
            print(f"state file not found: {args.state}", file=sys.stderr)
            return 2
        radar.state = load_state_file(args.state)
    if args.fetch:
        radar.state, problems = from_fred(radar.state)
        for p in problems:
            print(f"# {p}", file=sys.stderr)

    if args.command == "demo":
        from .demo import run
        out = run(radar)
    else:
        out = radar.dispatch(CLI_TO_COMMAND[args.command], arg=args.arg)

    print(out)

    if args.html:
        html = render_html(radar, build_brief(radar.state, radar.events,
                                              overnight=radar.overnight,
                                              geopolitical=radar.geopolitical))
        os.makedirs(os.path.dirname(os.path.abspath(args.html)) or ".", exist_ok=True)
        with open(args.html, "w", encoding="utf-8") as fh:
            fh.write(html)
        print(f"\n# HTML terminal written to {args.html}", file=sys.stderr)
    return 0


def _selftest() -> int:
    import unittest
    loader = unittest.TestLoader()
    suite = loader.discover("tests", top_level_dir=".")
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
