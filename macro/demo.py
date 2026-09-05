"""End-to-end worked example.

EVERY NUMBER IN THIS MODULE IS SYNTHETIC AND LABELLED AS SUCH.

The demo exists to exercise the engines, not to describe any real market. The
inputs are constructed illustrative values carrying a synthetic source tagged
Tier UNKNOWN, so the confirmation engine correctly refuses to treat any of it
as confirmed. Nothing here should ever be read as a market observation.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from .events import make_event, render_alert
from .liquidity import detect_anomaly
from .noise import filter_item
from .radar import RULE, THIN, Radar
from .reaction import analyse_orders, build_matrix
from .regime import MacroRegime
from .scoring import EventClass
from .setups import Side, build_setup
from .sources import make_source
from .structure import Bar, analyse
from .surprise import Impulse, evaluate
from .calendar_spec import INDICATORS
from .types import Observation, SourceRef, Tier, observed

SYNTHETIC = SourceRef(
    name="SYNTHETIC DEMO INPUT - NOT MARKET DATA",
    tier=Tier.UNKNOWN,
)

BANNER = (
    "!" * 78 + "\n"
    "!  DEMONSTRATION MODE - ALL VALUES BELOW ARE SYNTHETIC AND ILLUSTRATIVE.  !\n"
    "!  They are not market data, not forecasts, and not observations of any   !\n"
    "!  real release. They exist to exercise the engines end to end.           !\n"
    + "!" * 78
)


def _syn(v: float, unit: str, ts: datetime | None = None) -> Observation:
    return Observation(v, unit, as_of=ts, source=SYNTHETIC, note="synthetic demo value")


def _synthetic_bars(n: int = 60) -> list[Bar]:
    """Deterministic path: uptrend, sweep of equal highs, reversal."""
    t0 = datetime(2026, 1, 5, 13, 0, tzinfo=timezone.utc)
    deltas = (
        [0.6, 0.4, -0.3, 0.7, 0.5, -0.4, 0.8, 0.3, -0.5, 0.9] * 2
        + [0.2, -0.6, 0.4, 0.1, -0.3, 0.5, 0.2, -0.2, 0.3, 0.1]
        + [1.8, -1.9, -1.2, -0.8, 0.4, -1.1, -0.6, 0.3, -0.9, -0.4]
        + [-0.2, 0.5, -0.7, 0.2, -0.4, 0.6, -0.3, 0.1, -0.5, 0.2]
    )[:n]
    bars: list[Bar] = []
    px = 2400.0
    for i, d in enumerate(deltas):
        o = px
        c = px + d
        wick = abs(d) * 0.5 + 0.35
        bars.append(Bar(t0 + timedelta(minutes=15 * i), o,
                        max(o, c) + wick, min(o, c) - wick, c, 1000 + 7 * i))
        px = c
    return bars


def run(radar: Radar | None = None) -> str:
    radar = radar or Radar()
    out: list[str] = [BANNER, ""]

    # ---------------------------------------------------------------- state
    radar.state.regime = MacroRegime.INFLATION_DOMINANT
    radar.state.regime_basis = (
        "SYNTHETIC: assumed inflation-dominant for the demo so the 'good news is "
        "sold' branch is exercised. In use this must be established from data."
    )
    now = datetime(2026, 1, 13, 13, 30, tzinfo=timezone.utc)
    radar.state.as_of = now
    for k, v in (("US2Y", 4.28), ("US2Y_PRIOR", 4.16), ("US5Y", 4.19), ("US5Y_PRIOR", 4.12),
                 ("US10Y", 4.42), ("US10Y_PRIOR", 4.36), ("US30Y", 4.66), ("US30Y_PRIOR", 4.62),
                 ("US10Y_REAL", 2.06), ("US10Y_REAL_PRIOR", 2.00),
                 ("US10Y_BREAKEVEN", 2.36), ("US10Y_BREAKEVEN_PRIOR", 2.34)):
        radar.state.put(k, _syn(v, "pct", now))
    for k, v, u in (("DXY", 104.8, "index"), ("DXY_PRIOR", 104.1, "index"),
                    ("VIX", 18.9, "index"), ("SPX", 5720.0, "index"),
                    ("NDX", 20150.0, "index"), ("GOLD", 2404.0, "usd"),
                    ("WTI", 78.4, "usd_bbl"), ("BTC", 61250.0, "usd"),
                    ("HY_OAS", 342.0, "bp"), ("SOFR", 4.33, "pct"), ("IORB", 4.40, "pct")):
        radar.state.put(k, _syn(v, u, now))
    radar.state.changes_z = {"vix": 1.4, "spx_pct": -1.1, "dxy": 1.3, "hy_oas_bp": 0.9}
    radar.state.market_pricing["Federal Reserve"] = (
        "SYNTHETIC: assume 62% priced for a 25bp cut at the next meeting"
    )
    radar.state.session_levels = {
        "prev_day_high": 2418.5, "prev_day_low": 2391.0, "asia_high": 2409.2,
        "london_low": 2396.4,
    }

    # ------------------------------------------------------------- surprise
    spec = INDICATORS["US_CORE_CPI_MOM"]
    sr = evaluate(
        spec,
        actual=_syn(0.4, "pct_mom", now),
        consensus=_syn(0.3, "pct_mom", now),
        previous=_syn(0.3, "pct_mom", now),
        revised_previous=_syn(0.2, "pct_mom", now),
        surprise_history=[0.0, 0.1, -0.1, 0.1, 0.0, -0.1, 0.2, 0.0, -0.1, 0.1, 0.0, 0.1],
    )
    out += [RULE, "1. EXPECTATION VS ACTUAL", RULE, "  " + sr.render()]
    for n in sr.notes:
        out.append(f"    - {n}")

    # ------------------------------------------------------- reaction chain
    rmap = build_matrix(sr.impulse, radar.state.regime,
                        magnitude=abs(sr.standardized_surprise or 1.0),
                        scenario_label="Core CPI hotter than consensus (SYNTHETIC)")
    out += ["", RULE, "2. CROSS-ASSET TRANSMISSION", RULE, rmap.render()]
    out += ["", RULE, "3. SECOND- AND THIRD-ORDER", RULE, analyse_orders(rmap).render()]

    # ------------------------------------------------------------ the event
    noise = filter_item(
        "US core CPI released at 0.4% m/m, above the 0.3% consensus",
        tier=Tier.PRIMARY, published_at=now, now=now, changes_expectations=True,
    )
    ev = make_event(
        "US Core CPI +0.4% m/m vs +0.3% consensus (SYNTHETIC)",
        event_class=EventClass.SCHEDULED_STATISTIC, country="United States",
        summary=("SYNTHETIC: core CPI printed 0.4% m/m against a 0.3% consensus, with "
                 "the prior month revised down to 0.2% from 0.3%."),
        sources=[make_source("BLS", "https://www.bls.gov/news.release/cpi.nr0.htm",
                             published_at=now, is_primary_document=True)],
        when=now, market_impact=92, expected_volatility=86, directional_confidence=68,
        surprise=sr, reaction=rmap, noise=noise, minutes_to_event=0,
        embargoed_release=True,
        market_pricing_before=radar.state.market_pricing["Federal Reserve"],
        key_levels=("prev day high 2418.5", "equal highs cluster near 2418",
                    "prev day low 2391.0"),
        invalidation=("front-end yields give back the move within the session, or the "
                      "downward revision to the prior print is judged to offset the beat"),
    )
    radar.add(ev)

    # a low-quality item, to show the filter working
    junk_noise = filter_item(
        "Analysts say gold could be about to explode higher after CPI shock",
        tier=Tier.SOCIAL, published_at=now, now=now, changes_expectations=False,
    )
    radar.add(make_event(
        "Analysts say gold could be about to explode higher after CPI shock",
        event_class=EventClass.MARKET_EXPECTATION_SHIFT, country="United States",
        summary="SYNTHETIC low-quality item included to demonstrate the noise filter.",
        sources=[make_source("@anon_macro", "https://x.com/anon_macro")],
        when=now, market_impact=70, expected_volatility=60, directional_confidence=20,
        noise=junk_noise, is_unscheduled=True,
    ))

    out += ["", RULE, "4. MACRO ALERT", RULE, render_alert(ev)]

    # ----------------------------------------------------------- structure
    bars = _synthetic_bars()
    struct = analyse(bars, session_levels=radar.state.session_levels)
    radar.structures["XAUUSD"] = struct
    out += ["", RULE, "5. MARKET STRUCTURE (SYNTHETIC SERIES)", RULE, struct.render()]

    # -------------------------------------------------------------- setups
    last = bars[-1].close
    rejected = build_setup(
        asset="XAUUSD", side=Side.LONG, timeframe="15m",
        catalyst="hot core CPI (SYNTHETIC)", structure=struct,
        entry_low=last - 1, entry_high=last + 1, invalidation=last - 6,
        tp1=last + 6, tp2=last + 10, tp3=last + 14,
        liquidity_target="prev day high 2418.5", cost_per_unit=0.35,
        catalyst_aligned=False,
        catalyst_risk="a hot inflation print argues against long gold via real yields",
    )
    accepted = build_setup(
        asset="XAUUSD", side=Side.SHORT, timeframe="15m",
        catalyst="hot core CPI raises real yields (SYNTHETIC)", structure=struct,
        entry_low=last + 1.0, entry_high=last + 2.5, invalidation=last + 6.5,
        tp1=last - 6.0, tp2=last - 12.0, tp3=last - 18.0,
        liquidity_target="sell-side liquidity below the London low 2396.4",
        cost_per_unit=0.35, account_equity=100_000, risk_fraction=0.01,
        catalyst_aligned=True,
        catalyst_risk=("Fed speakers within 24h can discount the print; a downward "
                       "revision to the prior month partially offsets the beat"),
    )
    radar.setups += [accepted, rejected]
    out += ["", RULE, "6. SETUP ENGINE", RULE, accepted.render(), THIN, rejected.render()]

    # ------------------------------------------------------------- anomaly
    flag = detect_anomaly("USDJPY", 3.1, window_minutes=5,
                          headline_found=False, correlated_assets_moved=False, volume_z=1.1)
    out += ["", RULE, "7. UNEXPLAINED-MOVE DETECTOR", RULE, flag.render(),
            "  " + flag.instruction]

    # ----------------------------------------------------------- commands
    radar.overnight = [
        "SYNTHETIC: no overnight items are asserted. In use, this section is "
        "populated from ingested wires, not reconstructed from price.",
    ]
    out += ["", RULE, "8. COMMAND SURFACE", RULE]
    for cmd in ("RADAR", "RISK", "LIQUIDITY", "WHAT MATTERS"):
        out += [radar.dispatch(cmd), ""]

    out += [BANNER]
    return "\n".join(out)


__all__ = ["BANNER", "run"]
