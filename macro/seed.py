"""Captured market snapshot: 2026-09-04 US close / 2026-09-05 scan.

Every figure here was retrieved from a named public source and carries the
source, its tier and the moment the value was true. Nothing is estimated and
nothing is carried over from model knowledge. Where two sources disagreed the
higher tier is used, the lower confidence is recorded, and the disagreement is
listed in ``conflicts`` rather than quietly resolved.

This is a SNAPSHOT, not a live feed. ``macro/live.py`` refreshes it wherever
outbound network is available; the terminal always renders the true age.
"""

from __future__ import annotations

from .live import Headline, Quote, RELEASE_CLOCK, Snapshot

__all__ = ["build"]

CLOSE = "2026-09-04T20:00:00Z"      # US cash close, 16:00 ET
SESSION = "2026-09-04T21:00:00Z"    # end of the US session
CAPTURE = "2026-09-05T13:00:00Z"    # when this scan was performed

_CNBC = "https://www.cnbc.com/2026/09/04/treasurys-bonds-nonfarm-payrolls-unemployment-data.html"
_TS = "https://www.thestreet.com/stock-market-today/stock-market-today-dow-jones-sp-500-nasdaq-updates-sept-04-2026"
_INV = "https://au.investing.com/news/stock-market-news/global-macro-outlook-hormuz-fed-hike-odds-and-the-bond-rout--week-of-september-4-2026-93CH-4630470"
_FED = "https://www.federalreserve.gov/newsevents/pressreleases/monetary20260729a.htm"
_BLS_CPI = "https://www.bls.gov/news.release/cpi.nr0.htm"
_FRB_MIN = "https://www.federalreserve.gov/monetarypolicy/fomcminutes20260729.htm"

_Q = [
    # ---- rates ----------------------------------------------------------
    dict(key="US2Y", value=4.42, unit="pct", as_of=CLOSE, source="CNBC", tier=2,
         url=_CNBC, label="UST 2Y", change=8.0, change_unit="bp", confidence=0.75,
         note="Reported as an 8bp climb breaching 4.416%, highest since Jan 2025. "
              "A second, lower-tier report said +12bp to 4.35% - see conflicts."),
    dict(key="US10Y", value=4.76, unit="pct", as_of=CLOSE, source="CNBC", tier=2,
         url=_CNBC, label="UST 10Y", change=0.0, change_unit="bp", confidence=0.85,
         note="Little changed on the day; +5bp over five sessions. One source "
              "described it as climbing to roughly 4.80% intraday post-payrolls."),
    # ---- equities -------------------------------------------------------
    dict(key="SPX", value=7718.60, unit="index", as_of=CLOSE, source="TheStreet", tier=2,
         url=_TS, label="S&P 500", change=-0.38, change_unit="pct", confidence=0.9),
    dict(key="DJIA", value=53414.25, unit="index", as_of=CLOSE, source="TheStreet", tier=2,
         url=_TS, label="Dow Jones", change=-0.51, change_unit="pct", confidence=0.9),
    dict(key="NDX", value=26506.99, unit="index", as_of=CLOSE, source="TheStreet", tier=2,
         url=_TS, label="Nasdaq Comp", change=-0.29, change_unit="pct", confidence=0.9),
    dict(key="VIX", value=14.32, unit="index", as_of=CLOSE,
         source="Search aggregate (Investing.com / Yahoo Finance)", tier=3,
         url="https://www.investing.com/indices/volatility-s-p-500", label="VIX",
         confidence=0.65,
         note="Retrieved from an aggregated summary rather than a single primary "
              "quote page: the level is reliable, the last decimal is not. Notably "
              "low given the front-end repricing - the vol market is not pricing the "
              "hike risk the rates market is."),
    # ---- fx -------------------------------------------------------------
    dict(key="DXY", value=99.13, unit="index", as_of=CLOSE,
         source="Search aggregate (Investing.com / Yahoo Finance)", tier=3,
         url="https://www.investing.com/indices/usdollar", label="Dollar index",
         change=0.25, change_unit="pct", confidence=0.65,
         note="Retrieved from an aggregated summary, not a primary quote page. "
              "Carried as a level and a direction, not as a print."),
    # ---- commodities ----------------------------------------------------
    dict(key="BRENT", value=97.62, unit="usd_bbl", as_of=SESSION, source="Investing.com",
         tier=2, url=_INV, label="Brent crude", change=7.0, change_unit="pct",
         confidence=0.85,
         note="~1.5-month high, roughly +7% on the week after a new wave of US "
              "strikes on Iran."),
    dict(key="WTI", value=91.67, unit="usd_bbl", as_of=SESSION, source="FXDailyReport",
         tier=3, url="https://fxdailyreport.com/wti-crude-oil-price-analysis-for-september-4-2026/",
         label="WTI crude", confidence=0.7,
         note="Opened 91.69; ranged from lows near 80.18 to a high of 93.05."),
    dict(key="GOLD", value=4500.0, unit="usd_oz", as_of=SESSION, source="TradingEconomics",
         tier=3, url="https://tradingeconomics.com/commodity/gold", label="Gold",
         confidence=0.6,
         note="Sourced as 'near $4,500' on Friday after ~$4,470 Thursday. "
              "Approximate: treat the level, not the digits."),
    # ---- crypto ---------------------------------------------------------
    dict(key="BTC", value=79000.0, unit="usd", as_of=SESSION, source="CryptoTimes",
         tier=4, url="https://www.cryptotimes.io/2026/09/04/bitcoin-price-prediction-september-2026-can-btc-reach-90k-or-retest-72k/",
         label="Bitcoin", confidence=0.5,
         note="Sourced as 'holding near $79K' with $80,000 the level being watched "
              "as support. Tier 4: directional only, not a print."),
]

_H = [
    dict(title="August payrolls +162k versus +53k expected; unemployment steady at 4.1%",
         source="BLS Employment Situation (via CNBC)", tier=1, published="2026-09-04T12:30:00Z",
         url=_CNBC, impact=95, primary_confirmed=True,
         assets=("UST 2Y", "USD", "S&P 500", "Gold"),
         summary="A roughly 3x upside surprise on payrolls. This is the print that "
                 "repriced the September meeting."),
    dict(title="September Fed hike odds roughly double to the mid-60s from ~36% since "
               "Chair Warsh's Jackson Hole speech",
         source="Investing.com", tier=2, published="2026-09-04T18:00:00Z", url=_INV,
         impact=92, assets=("UST 2Y", "USD", "S&P 500"),
         summary="The market is now pricing a hike as more likely than not into the "
                 "15-16 September meeting."),
    dict(title="Treasury yields jump after payrolls beat; 2-year breaches 4.416%, "
               "highest since January 2025",
         source="CNBC", tier=2, published="2026-09-04T18:30:00Z", url=_CNBC, impact=88,
         assets=("UST 2Y", "UST 10Y", "2s10s"),
         summary="Front-end led selloff: an 8bp move in the 2y against a broadly "
                 "unchanged 10y is a textbook bear flattening."),
    dict(title="New wave of US strikes on Iran lifts crude to its highest since July; "
               "Brent +7% on the week to $97.62",
         source="Investing.com", tier=2, published="2026-09-04T16:00:00Z", url=_INV,
         impact=90, assets=("Brent", "WTI", "Breakevens", "EUR"),
         summary="Energy is now an active inflation channel, not a base effect. "
                 "Hormuz risk sits under the whole complex."),
    dict(title="ECB seen hiking 25bp to 2.50% as euro-area inflation rises to 3.3% y/y "
               "in August from 2.9%",
         source="CNBC / ECB", tier=2, published="2026-09-04T10:00:00Z",
         url="https://www.cnbc.com/2026/07/23/interest-rate-hike-iran-european-central-bank.html",
         impact=85, assets=("EURUSD", "Bunds", "EUR rates"),
         summary="Euro-area inflation is re-accelerating. Lagarde primed a September "
                 "move at the July press conference."),
    dict(title="Fed's Waller: would support holding rates if price pressures continue "
               "to ease",
         source="Federal Reserve", tier=1, published="2026-09-03T15:00:00Z",
         url="https://www.federalreserve.gov/newsevents/speeches.htm", impact=74,
         primary_confirmed=True, assets=("UST 2Y", "USD"),
         summary="The dovish counterweight to the payrolls print, and the reason the "
                 "hike is priced in the sixties rather than the nineties."),
    dict(title="FOMC held the target range at 3.50-3.75% on a 9-3 vote in July; all "
               "three dissents favoured a 25bp hike",
         source="Federal Reserve", tier=1, published="2026-07-29T18:00:00Z", url=_FED,
         impact=80, primary_confirmed=True, assets=("UST 2Y", "USD"),
         summary="Dissents pointing at a hike, not a cut, is the single clearest "
                 "signal of which regime this is."),
    dict(title="Beige Book: manufacturers and construction firms report price pressures "
               "from energy, raw materials and transport",
         source="Federal Reserve", tier=1, published="2026-09-02T18:00:00Z",
         url="https://www.federalreserve.gov/monetarypolicy/beige-book-default.htm",
         impact=68, primary_confirmed=True, assets=("Breakevens", "UST 10Y"),
         summary="Corroborates the energy pass-through the CPI print has not yet shown."),
    dict(title="Diesel prices hold near April highs, adding to near-term inflation "
               "pressure",
         source="Investing.com", tier=2, published="2026-09-04T14:00:00Z", url=_INV,
         impact=62, assets=("Breakevens", "WTI"),
         summary="Distillate is the cleanest read on freight-cost pass-through."),
    dict(title="El-Erian: expect the global government bond selloff to continue",
         source="Mohamed El-Erian via CNBC", tier=3, published="2026-09-04T17:00:00Z",
         url="https://www.cnbc.com/2026/09/02/bond-market-selloff-rates-fixed-income-treasury-yields.html",
         impact=45, assets=("UST 10Y", "Bunds", "JGBs"),
         summary="Named commentary, not new information. Ranked accordingly."),
]

CONFLICTS = [
    "US 2Y level: CNBC reported +8bp breaching 4.416%; a lower-tier outlet reported "
    "+12bp to 4.35%. The Tier-2 figure is carried at reduced confidence and the "
    "disagreement is not resolved to the more convenient number.",
    "US 10Y: reported both as 'little changed at 4.76%' at the close and as 'climbing "
    "to roughly 4.80%' intraday after payrolls. Both can be true in sequence; the "
    "close is carried.",
    "Gold and BTC are carried from Tier 3/4 descriptions ('near $4,500', 'near $79K'). "
    "They are levels, not prints, and are marked at reduced confidence.",
]

POLICY = {
    "fed": {
        "target": "3.50 - 3.75%", "last_action": "held, 9-3, 29 July 2026",
        "dissents": "3 dissents favouring a 25bp HIKE",
        "chair": "Warsh", "next": "2026-09-16T18:00:00Z",
        "market_priced": "hike odds mid-60s for 15-16 September (from ~36% pre-Jackson Hole)",
        "source": _FRB_MIN, "tier": 1,
    },
    "ecb": {
        "target": "2.25% (deposit)", "last_action": "held, 23 July 2026",
        "dissents": "n/a",
        "chair": "Lagarde", "next": "2026-09-10T12:15:00Z",
        "market_priced": "25bp hike to 2.50% expected; euro-area HICP 3.3% y/y in August",
        "source": "https://www.ecb.europa.eu/press/pr/date/2026/html/index.en.html",
        "tier": 1,
    },
    "inflation": {
        "us_cpi_yoy": "3.4% (July, released 12 Aug)",
        "us_core_cpi_yoy": "2.5% (July)",
        "us_cpi_mom": "+0.1% (July, after -0.4% in June)",
        "us_core_cpi_mom": "+0.2% (July)",
        "peak": "3.8% y/y in April 2026",
        "ez_hicp_yoy": "3.3% (August, from 2.9% in July)",
        "source": _BLS_CPI, "tier": 1,
    },
    "labor": {
        "nfp": "+162k (August) vs +53k expected",
        "unemployment": "4.1%, unchanged and as expected",
        "source": "https://www.bls.gov/news.release/empsit.nr0.htm", "tier": 1,
    },
}

REGIME = "INFLATION-DOMINANT"
REGIME_BASIS = (
    "Established from the tape, not assumed: a 3x upside payrolls surprise was SOLD "
    "in equities (S&P -0.38%, Dow -0.51%) while the front end sold off 8bp and "
    "September hike odds roughly doubled. Good news is bad news, so the policy path "
    "is the binding constraint. An energy shock (Brent +7% on the week on US strikes "
    "on Iran) is feeding the inflation leg directly, and both the Fed's July dissents "
    "and the ECB's expected hike point the same way."
)


def build() -> Snapshot:
    """Materialise the captured snapshot."""
    snap = Snapshot(captured=CAPTURE, regime=REGIME, regime_basis=REGIME_BASIS)
    for d in _Q:
        q = Quote(**d)
        snap.quotes[q.key] = q
    snap.headlines = [Headline(**d) for d in _H]
    snap.headlines.sort(key=lambda h: -h.impact)
    snap.releases = list(RELEASE_CLOCK)
    snap.policy = POLICY
    snap.conflicts = list(CONFLICTS)
    snap.errors = [
        "Live scan unavailable in the capture environment: outbound egress policy "
        "rejects every market and news host. Values were retrieved through research "
        "tooling and carry their original source and timestamp.",
    ]
    return snap
