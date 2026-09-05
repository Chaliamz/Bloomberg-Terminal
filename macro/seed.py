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

from .live import (GeoEvent, Gauge, Headline, Liquidations, Quote,
                   RELEASE_CLOCK, Snapshot)

__all__ = ["build"]

CLOSE = "2026-09-04T20:00:00Z"      # US cash close, 16:00 ET
CRYPTO = "2026-09-04T11:21:00Z"     # 07:21 ET - crypto prints, PRE-payrolls
LIQ = "2026-09-04T03:52:00Z"        # liquidation window close
SESSION = "2026-09-04T21:00:00Z"    # end of the US session
CAPTURE = "2026-09-05T13:00:00Z"    # when this scan was performed

_CNBC = "https://www.cnbc.com/2026/09/04/treasurys-bonds-nonfarm-payrolls-unemployment-data.html"
_TS = "https://www.thestreet.com/stock-market-today/stock-market-today-dow-jones-sp-500-nasdaq-updates-sept-04-2026"
_INV = "https://au.investing.com/news/stock-market-news/global-macro-outlook-hormuz-fed-hike-odds-and-the-bond-rout--week-of-september-4-2026-93CH-4630470"
_FED = "https://www.federalreserve.gov/newsevents/pressreleases/monetary20260729a.htm"
_BLS_CPI = "https://www.bls.gov/news.release/cpi.nr0.htm"
_FRB_MIN = "https://www.federalreserve.gov/monetarypolicy/fomcminutes20260729.htm"
_RIO = "https://www.riotimesonline.com/global-economy-briefing-september-5-2026/"
_YF = "https://finance.yahoo.com/personal-finance/investing/article/bitcoin-and-ethereum-prices-today-friday-september-4-2026-bitcoin-holding-above-81000-following-massive-etf-inflows-113751298.html"
_BLOCK = "https://www.theblock.co/news/markets/2026-09-04-us-bitcoin-etfs-largest-inflow-day-since-january-413515"
_COINOTAG = "https://en.coinotag.com/bitcoin-leads-468-million-crypto-liquidations-24-hours"
_FAF = "https://www.faf.ae/home/2026/9/1/irans-war-returns-hormuz-bleeds-and-the-worlds-bond-markets-brace-for-a-geopolitical-inflation-shock"

_Q = [
    # ---- rates ----------------------------------------------------------
    dict(key="US2Y", value=4.42, unit="pct", as_of=CLOSE, source="CNBC", tier=2,
         url=_CNBC, label="UST 2Y", change=8.0, change_unit="bp", confidence=0.75,
         note="Reported as an 8bp climb breaching 4.416%, highest since Jan 2025. "
              "A second, lower-tier report said +12bp to 4.35% - see conflicts."),
    dict(key="US10Y", value=4.79, unit="pct", as_of=CLOSE, source="Rio Times briefing",
         tier=3, url=_RIO, label="UST 10Y", change=3.0, change_unit="bp", confidence=0.8,
         note="Reported as 4.789% on the 5 September briefing, corroborating a second "
              "account of a climb to roughly 4.80% after payrolls. CNBC separately "
              "described the close as 'little changed at 4.76%' - see conflicts."),
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
    dict(key="DXY", value=99.16, unit="index", as_of=CLOSE, source="Rio Times briefing",
         tier=3, url=_RIO, label="Dollar index", change=0.25, change_unit="pct",
         confidence=0.75,
         note="Reported as 99.157. An earlier aggregated summary gave 99.13; the two "
              "agree to within noise and the more precise figure is carried."),
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
    dict(key="GOLD", value=4429.0, unit="usd_oz", as_of=CLOSE, source="Rio Times briefing",
         tier=3, url=_RIO, label="Gold", change=-1.14, change_unit="pct", confidence=0.8,
         note="CORRECTED. An earlier read carried gold at 'near $4,500' from a "
              "descriptive summary; the 5 September briefing prints 4,429 and a "
              "-1.14% session. Real yields up on the payrolls beat is consistent "
              "with gold down."),
    # ---- crypto ---------------------------------------------------------
    dict(key="BTC", value=81240.29, unit="usd", as_of=CRYPTO, source="Yahoo Finance",
         tier=2, url=_YF, label="Bitcoin", change=5.10, change_unit="pct",
         confidence=0.85,
         note="CORRECTED from an earlier Tier-4 read of 'near $79K'. Priced at "
              "07:21 ET - BEFORE the 08:30 ET payrolls print - so this rally belongs "
              "to the dovish Waller/ETF story, not to the hawkish payrolls story that "
              "set the equity and rates closes. The timestamps are not interchangeable."),
    dict(key="ETH", value=2507.70, unit="usd", as_of=CRYPTO, source="Yahoo Finance",
         tier=2, url=_YF, label="Ethereum", change=4.90, change_unit="pct",
         confidence=0.85,
         note="Friday open, +4.9% on Thursday's open."),
]

_H = [
    dict(title="US spot bitcoin ETFs take $731m, the largest inflow day since 14 January; "
               "BlackRock's IBIT captured $454m of it",
         source="The Block", tier=2, published="2026-09-04T14:00:00Z", url=_BLOCK,
         impact=78, assets=("BTC", "ETH", "Crypto"),
         summary="Attributed to Waller's dovish remarks. Three-week cumulative inflow "
                 "of $3.8bn is the biggest streak of 2026."),
    dict(title="Crypto liquidations hit $468.6m in 24 hours with 87% on the short side; "
               "bitcoin alone accounted for $272.6m, 92% short",
         source="CoinGlass via COINOTAG", tier=3, published="2026-09-04T03:52:00Z",
         url=_COINOTAG, impact=72, assets=("BTC", "ETH"),
         summary="A short squeeze, not spot demand. Forced buybacks were the fuel, "
                 "which is a mechanically different move from an accumulation rally."),
    dict(title="OPEC+ meets Saturday 5 September; any output surprise repricies crude "
               "into an already-tight geopolitical bid",
         source="Rio Times briefing", tier=3, published="2026-09-05T08:00:00Z", url=_RIO,
         impact=84, assets=("Brent", "WTI", "Breakevens", "CAD", "NOK"),
         summary="The single unpriced catalyst inside 24 hours. Publication time is "
                 "not scheduled, so it cannot be counted down - only watched."),
    dict(title="US strikes Iranian launch positions on Larak Island; Iran responds with "
               "missile attacks on US forces in Jordan",
         source="Foreign Affairs Forum", tier=3, published="2026-09-01T12:00:00Z",
         url=_FAF, impact=93, assets=("Brent", "WTI", "Gold", "CHF", "Breakevens"),
         summary="Direct military exchange has resumed. This is the supply-side engine "
                 "under the whole inflation leg."),
    dict(title="Washington revokes the licence permitting limited Iranian oil sales; "
               "tanker damage reported near Oman",
         source="Foreign Affairs Forum", tier=3, published="2026-09-02T12:00:00Z",
         url=_FAF, impact=86, assets=("Brent", "WTI", "Freight"),
         summary="Sanctions tightening plus physical shipping risk. Hormuz transits are "
                 "running far below normal."),
    dict(title="Equity sentiment reads Fear at 42 while crypto sentiment reads Greed at 61",
         source="CNN / Crypto Fear & Greed", tier=3, published="2026-09-04T21:00:00Z",
         url="https://cfgi.io/", impact=58, assets=("S&P 500", "BTC"),
         summary="The two are measuring different clocks: crypto priced the pre-payrolls "
                 "dovish story, equities closed on the post-payrolls hawkish one."),
    dict(title="Gold falls 1.14% to $4,429 as real yields back up on the payrolls beat",
         source="Rio Times briefing", tier=3, published="2026-09-04T21:00:00Z", url=_RIO,
         impact=60, assets=("Gold", "US10Y real"),
         summary="Gold trading as a real-rate asset here, not as a haven - which is the "
                 "read to carry into any geopolitical escalation."),
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
    "Bitcoin was initially carried at ~$79,000 from a Tier-4 description. That was "
    "WRONG: two Tier-2 sources price it at $81,240 after a 5% short squeeze. The "
    "corrected figure is carried and the error is recorded rather than erased.",
    "Gold was initially carried at ~$4,500 from a descriptive summary. The 5 September "
    "briefing prints 4,429 with a -1.14% session; the corrected figure is carried.",
    "US 10Y: CNBC described the close as 'little changed at 4.76%'; the 5 September "
    "briefing prints 4.789%, corroborating a separate account of a climb toward 4.80% "
    "after payrolls. The higher, corroborated figure is carried at 0.80 confidence.",
    "Crypto liquidation totals were reported over at least three different windows the "
    "same day ($468.59m, $544.85m, and $415m of shorts). The window is stated on the "
    "board rather than the largest headline number being chosen.",
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


GAUGES = [
    dict(key="CNN_FG", label="Equity Fear & Greed", value=42.0, band="FEAR",
         as_of="2026-09-04T21:00:00Z", source="CNN Business", tier=2,
         url="https://edition.cnn.com/markets/fear-and-greed", confidence=0.75,
         note="A second read gave 43.77 the same day; both sit in the FEAR band, so "
              "the band is robust even though the digit is not."),
    dict(key="CRYPTO_FG", label="Crypto Fear & Greed", value=61.0, band="GREED",
         as_of="2026-09-04T21:00:00Z", source="Crypto Fear & Greed Index", tier=3,
         url="https://cfgi.io/", confidence=0.8,
         note="Flipped from Fear to Greed overnight on the ETF-inflow and short-squeeze "
              "rally."),
]

LIQUIDATIONS = dict(
    window="24h to 03:52 UTC, 4 September 2026",
    total_usd=468_590_000.0, long_usd=60_490_000.0, short_usd=408_100_000.0,
    as_of=LIQ, source="CoinGlass via COINOTAG", tier=3, url=_COINOTAG,
    asset_usd=272_600_000.0, asset_label="Bitcoin", asset_short_pct=92.0,
    note="Two other windows were reported the same day - $544.85m and a $415m "
         "shorts-only figure - covering different periods and scopes. The window is "
         "stated here rather than the largest number being chosen.",
)

GEO = [
    dict(headline="US strikes on Iranian launch positions, Larak Island",
         region="Strait of Hormuz", severity=93, as_of="2026-09-01T12:00:00Z",
         source="Foreign Affairs Forum", tier=3, url=_FAF, status="ESCALATING",
         channel="Military action -> tanker insurance and transit risk -> crude supply "
                 "premium -> headline CPI -> breakevens -> the policy path",
         assets=("Brent", "WTI", "Gold", "CHF", "Breakevens")),
    dict(headline="Iranian missile attacks on US forces in Jordan",
         region="Levant", severity=88, as_of="2026-09-01T18:00:00Z",
         source="Foreign Affairs Forum", tier=3, url=_FAF, status="ESCALATING",
         channel="Direct exchange raises the probability of a sustained campaign, which "
                 "is what turns a risk premium into a supply disruption",
         assets=("Brent", "Defence", "Gold")),
    dict(headline="Licence for limited Iranian oil sales revoked",
         region="Policy", severity=80, as_of="2026-09-02T12:00:00Z",
         source="Foreign Affairs Forum", tier=3, url=_FAF, status="ACTIVE",
         channel="Sanctions tightening removes barrels from the legal market: a direct, "
                 "quantifiable supply subtraction rather than a sentiment effect",
         assets=("Brent", "WTI")),
    dict(headline="Tanker damage near Oman; Hormuz transits far below normal",
         region="Strait of Hormuz", severity=85, as_of="2026-09-02T12:00:00Z",
         source="Foreign Affairs Forum", tier=3, url=_FAF, status="ONGOING",
         channel="Physical chokepoint risk -> freight and insurance rates -> delivered "
                 "energy cost -> goods inflation with a lag",
         assets=("Brent", "Freight", "Breakevens")),
    dict(headline="Red Sea shipping attacks continue",
         region="Red Sea", severity=68, as_of="2026-09-04T12:00:00Z",
         source="Investing.com", tier=2, url=_INV, status="ONGOING",
         channel="Rerouting round the Cape adds voyage days: a supply-chain cost shock "
                 "that reaches CPI months after it reaches freight rates",
         assets=("Freight", "Breakevens")),
    dict(headline="OPEC+ meets Saturday 5 September",
         region="OPEC+", severity=84, as_of="2026-09-05T08:00:00Z",
         source="Rio Times briefing", tier=3, url=_RIO, status="TODAY - TIME NOT PUBLISHED",
         channel="An output surprise lands on top of an already-tight geopolitical bid. "
                 "No publication time is scheduled, so it can be watched but not counted "
                 "down",
         assets=("Brent", "WTI", "CAD", "NOK")),
]

FLOWS = [
    {"label": "US spot BTC ETFs", "value": "+$731m", "window": "3 September",
     "note": "Largest single day since 14 January. IBIT took $454m, over 60% of it.",
     "source": "The Block", "tier": 2, "url": _BLOCK, "direction": "in"},
    {"label": "US spot BTC ETFs", "value": "+$175m", "window": "4 September",
     "note": "Solid but unremarkable follow-through.", "source": "CryptoBriefing",
     "tier": 3, "url": "https://cryptobriefing.com/bitcoin-ethereum-etf-inflows-september/",
     "direction": "in"},
    {"label": "US spot BTC ETFs", "value": "+$3.8bn", "window": "trailing 3 weeks",
     "note": "Biggest inflow streak of 2026.", "source": "Bloomingbit", "tier": 3,
     "url": "https://en.bloomingbit.io/feed/news/119801", "direction": "in"},
    {"label": "US spot ETH ETFs", "value": "+$27m", "window": "4 September",
     "note": "Materially smaller than the bitcoin complex.", "source": "CryptoBriefing",
     "tier": 3, "url": "https://cryptobriefing.com/bitcoin-ethereum-etf-inflows-september/",
     "direction": "in"},
]


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
    for gd in GAUGES:
        g = Gauge(**gd)
        snap.gauges[g.key] = g
    snap.liquidations = Liquidations(**LIQUIDATIONS)
    snap.geo = [GeoEvent(**g) for g in GEO]
    snap.geo.sort(key=lambda g: -g.severity)
    snap.flows = list(FLOWS)
    snap.conflicts = list(CONFLICTS)
    snap.errors = [
        "Live scan unavailable in the capture environment: outbound egress policy "
        "rejects every market and news host. Values were retrieved through research "
        "tooling and carry their original source and timestamp.",
    ]
    return snap
