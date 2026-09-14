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

from .live import (Earning, Equity, GeoEvent, Gauge, Headline, Liquidations,
                   PriceAnchor, Quote, RELEASE_CLOCK, Snapshot)

__all__ = ["build"]

CLOSE = "2026-09-04T20:00:00Z"      # US cash close, 16:00 ET
CRYPTO = "2026-09-04T11:21:00Z"     # 07:21 ET - crypto prints, PRE-payrolls
SPOT   = "2026-09-07T10:50:00Z"     # live re-scan, 7 September
SENT   = "2026-09-07T10:50:00Z"     # sentiment re-read, 7 September
LIQ = "2026-09-04T03:52:00Z"        # liquidation window close
SESSION = "2026-09-04T21:00:00Z"    # end of the US session
CAPTURE = "2026-09-14T18:17:00Z"    # when this scan CONCLUDED. Deliberately later
CRYPTO14 = "2026-09-14T11:31:00Z"   # 7:31 a.m. ET, a time Yahoo states outright
SPOT14  = "2026-09-14T18:17:00Z"    # 14 Sep re-scan; the oil carriers give a day
                                    # and an intraday level but no quote time
_OLDCAP = "2026-09-13T16:04:00Z"    # the previous scan, kept only as a reference
                                    # point in the notes below
                                    # than the read stamps below: those belong to
                                    # the moment each figure was retrieved and must
                                    # not be dragged forward to match this one.
BTC13  = "2026-09-13T05:22:00Z"     # CoinDesk states 1:22 a.m. EDT - the only
                                    # 13 September crypto read carrying its own time
CLOSE11 = "2026-09-11T20:00:00Z"    # US cash close, Friday 11 September
SPOT13  = "2026-09-13T08:10:00Z"    # 13 Sep re-scan; carriers state no quote time
BRIEF12 = "2026-09-12T12:00:00Z"    # the 12 September Rio Times briefing publishes
                                    # a DATE and no time. 12:00Z is the midday
                                    # convention this board uses for a dated
                                    # briefing and is the one assumption in the
                                    # two quotes that carry it. It is deliberately
                                    # NOT the scan stamp: stamping a 12 September
                                    # figure with a 13 September read time would
                                    # zero the age counter on a day-old number.
SENT13  = "2026-09-13T08:10:00Z"    # sentiment re-read, 13 September
CRYPTO12 = "2026-09-12T01:30:00Z"   # 12 Sep crypto read; 01:30Z is the stamp the
                                    # carrier puts on the market-cap line in the
                                    # same article, the price quote states only
                                    # the date
SPOT8  = "2026-09-08T18:40:00Z"     # 8 Sep re-scan; carriers state no quote time,
                                    # so this is retrieval, not a print time
BTC8   = "2026-09-09T16:15:00Z"     # newest BTC observation, this session's read
SPOT9  = "2026-09-09T16:18:00Z"     # 9 Sep re-scan; carriers state no quote time
SENT9  = "2026-09-09T16:18:00Z"     # sentiment re-read, 9 September

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
_FOOL = "https://www.fool.com/research/largest-companies-by-market-cap/"
_CNBC_MKT = "https://www.cnbc.com/2026/09/03/stock-market-today-live-updates.html"

_Q = [
    # ---- rates ----------------------------------------------------------
    dict(key="US2Y", value=4.63, unit="pct", as_of=CLOSE11,
         source="Search aggregate (11 September Treasury snapshots)", tier=3,
         url="https://streetstats.finance/rates/treasuries", label="UST 2Y",
         confidence=0.6,
         note="RE-SCANNED 13 September for the 11 September close. The board carried "
              "4.42% from the 4 September close, so the front end has repriced 21bp "
              "in a week - the market pricing the hike, not the Fed delivering it. "
              "No session change is shown because the carrier states none, and "
              "deriving one from a board value seven sessions older would be a "
              "number about this file rather than about the market."),
    dict(key="US10Y", value=4.974, unit="pct", as_of=BRIEF12,
         source="Rio Times briefing (12 September)", tier=3,
         url="https://www.riotimesonline.com/global-economy-briefing-september-12-2026/",
         label="UST 10Y", confidence=0.7,
         note="RE-SCANNED 13 September: 4.974%, described as the highest since it "
              "briefly topped 5% in October 2023. The carrier states no quote time, "
              "so this read carries the briefing DATE at the board's midday "
              "convention, not the scan stamp - stamping it 13 September would zero "
              "the age counter on a day-old number. The path "
              "is corroborated rather than assumed: the board held 4.82% on 9 "
              "September, a separate carrier prints a 4.96% CLOSE on 11 September, "
              "and this is the 12 September intraday. Three carriers, one direction, "
              "15bp in three sessions. Five percent is now the level the whole board "
              "trades around."),
    # ---- equities -------------------------------------------------------
    dict(key="SPX", value=7656.98, unit="index", as_of=CLOSE11,
         source="Washington Post / Rio Times briefing", tier=2,
         url="https://www.washingtonpost.com/business/2026/09/11/wall-street-stocks-dow-nasdaq/",
         label="S&P 500", change=0.86, change_unit="pct", confidence=0.9,
         note="11 SEPTEMBER CLOSE. Two independent carriers print 7,656.98 and "
              "+0.86%, agreeing to the cent, which is why this is Tier 2 at 0.9 "
              "rather than the Tier 3 aggregate the board has been carrying for the "
              "index. Wall Street snapped a four-session losing streak on a CPI that "
              "landed broadly in line and oil that fell 2.4%."),
    dict(key="DJIA", value=52573.29, unit="index", as_of=CLOSE11,
         source="Washington Post / Rio Times briefing", tier=2,
         url="https://www.washingtonpost.com/business/2026/09/11/wall-street-stocks-dow-nasdaq/", label="Dow Jones", change=0.98, change_unit="pct", confidence=0.9,
         note="11 September close, +509.19 points. Down from the 53,414.25 the board "
              "carried for 4 September: the week was negative even with Friday's "
              "rebound in it."),
    dict(key="NDX", value=26333.04, unit="index", as_of=CLOSE11,
         source="Washington Post / Rio Times briefing", tier=2,
         url="https://www.washingtonpost.com/business/2026/09/11/wall-street-stocks-dow-nasdaq/", label="Nasdaq Comp", change=0.96, change_unit="pct", confidence=0.9),
    dict(key="VIX", value=15.84, unit="index", as_of=CLOSE11,
         source="Rio Times briefing (12 September)", tier=3,
         url="https://www.riotimesonline.com/global-economy-briefing-september-12-2026/", label="VIX", change=-11.21, change_unit="pct",
         confidence=0.5,
         note="CARRIERS DISAGREE ON THIS ONE AND THE BOARD SAYS SO. Rio Times prints "
              "15.84, down 11.21%; a separate aggregate prints 14.53, UP 1.47%. Not "
              "a rounding gap - opposite signs. The tape decides it: three indices "
              "closed up about 1% and crude fell 2.4%, and a vol index does not rise "
              "into that. The 15.84 read also implies a 17.84 prior, which is what a "
              "four-session losing streak into a CPI looks like. Confidence 0.5 is "
              "the lowest on the board and it is the honest number here."),
    # ---- fx -------------------------------------------------------------
    dict(key="DXY", value=99.095, unit="index", as_of=BRIEF12,
         source="Rio Times briefing (12 September)", tier=3, url="https://www.riotimesonline.com/global-economy-briefing-september-12-2026/",
         label="Dollar index", confidence=0.75,
         note="Described as broadly flat to slightly higher with the 10-year just "
              "below 5%. No session change is shown because the carrier gives none. "
              "The board held 99.16 on 4 September: the dollar has not moved while "
              "the front end repriced 21bp, which is the anomaly on this board - "
              "either the rates market or the currency market is wrong about the "
              "hike. Open this page in a browser and the violet DXY cell is "
              "recomputed from the ECB's own published fixings instead."),
    # ---- commodities ----------------------------------------------------
    dict(key="BRENT", value=108.15, unit="usd_bbl", as_of=SPOT14,
         source="OilPrice / Vantage Markets (14 September)", tier=3, url="https://oilprice.com/Latest-Energy-News/World-News/Brent-at-108-Gulf-States-Halt-Hormuz-Talks-as-Houthis-Strike-Saudi-Airbase.html",
         label="Brent crude", confidence=0.65,
         note="14 SEPTEMBER, AND THE FRIDAY RALLY IS FULLY REVERSED. The board "
              "carried 104.42 from the 11 September close, which was itself a "
              "four-percent selloff on the ANNOUNCEMENT of Iran-GCC talks. Those "
              "talks were POSTPONED late Sunday and Saudi Arabia shut a major crude "
              "pipeline after drone attacks, and Brent reopened more than 2% higher "
              "at 108.15. No session change is shown because the carriers give a "
              "level and a direction, not a settle. Brent is up about 9% on the "
              "week. Confidence 0.65: an intraday level from a headline, not a "
              "close."),
    dict(key="WTI", value=102.64, unit="usd_bbl", as_of=SPOT14,
         source="Vantage Markets (14 September)", tier=3, url="https://oilprice.com/Latest-Energy-News/World-News/Brent-at-108-Gulf-States-Halt-Hormuz-Talks-as-Houthis-Strike-Saudi-Airbase.html",
         label="WTI crude", confidence=0.65,
         note="14 September, a four-month high, against the 100.05 October-contract "
              "settle the board carried for 11 September. The pipeline that was shut "
              "is the East-West line to Yanbu - 7 million barrels a day of capacity "
              "and the ONLY material route that bypasses Hormuz. Traders quoted by "
              "Reuters put up to 4% of global supply at risk if it stays down, which "
              "is why this is no longer a risk-premium story."),
    dict(key="GOLD", value=4408.90, unit="usd_oz", as_of=CLOSE11,
         source="Search aggregate (11 September commodity snapshots)", tier=3,
         url="https://tradingeconomics.com/commodity/gold",
         label="Gold", change=0.04, change_unit="pct", confidence=0.7,
         note="Up 1.60 on the session - flat in all but sign, with real yields at the "
              "highs and the dollar unmoved. Gold is not confirming the inflation "
              "trade the oil price is making. Open this page in a browser and the "
              "amber GOLD cell is replaced by a live PAXGUSDT print, which is a "
              "proxy for spot and labelled as one."),
    # ---- crypto ---------------------------------------------------------
    dict(key="BTC", value=77873.33, unit="usd", as_of=CRYPTO14,
         source="Yahoo Finance", tier=2, url="https://finance.yahoo.com/personal-finance/investing/article/bitcoin-and-ethereum-prices-today-monday-september-14-2026-crypto-prices-trying-to-hold-as-rate-hike-expectations-grow-114245430.html", label="Bitcoin",
         confidence=0.75,
         note="14 SEPTEMBER, 7:31 a.m. ET - a time the carrier STATES, which is why "
              "this is Tier 2 where the last three crypto reads were Tier 3. Monday "
              "opened 76,806.19, 0.6% below Sunday's open, and recovered through the "
              "morning. A second carrier has 77,782 the same day with no time; the "
              "91-dollar gap is recorded rather than resolved. No 24h change is "
              "shown because none was stated. THIS NUMBER IS NOT LIVE: open this "
              "file in a browser and the Binance stream replaces it within a "
              "second."),
    dict(key="ETH", value=2514.09, unit="usd", as_of=CRYPTO14,
         source="Yahoo Finance", tier=2, url="https://finance.yahoo.com/personal-finance/investing/article/bitcoin-and-ethereum-prices-today-monday-september-14-2026-crypto-prices-trying-to-hold-as-rate-hike-expectations-grow-114245430.html", label="Ethereum",
         confidence=0.75,
         note="14 September, 7:31 a.m. ET. Opened 2,475.82, down 2% on Sunday's "
              "open, and recovered with Bitcoin. Ether gave back more than Bitcoin "
              "into the weekend and has recovered less.")
]

_H = [
    # ---- 14 September ----------------------------------------------------
    dict(title="Iran-GCC Hormuz talks POSTPONED; Brent reopens above $108",
         summary="Oman's foreign minister deferred Monday's Salalah meeting late "
                 "Sunday 'in the interest of consensus'. Saudi Arabia had filed "
                 "amendments objecting that the Iran-Oman wording would establish a "
                 "new status quo; Bahrain said it would not attend. Friday's "
                 "four-percent selloff was priced on this meeting happening.",
         source="Oman FM via CNN / Al Jazeera", tier=2,
         published="2026-09-13T20:00:00Z", impact=93, url="https://www.aljazeera.com/news-analysis/2026/9/14/temporary-hormuz-solution-deferred-as-iran-arab-summit-falls-through",
         primary_confirmed=True,
         assets=("Brent", "WTI", "Gold", "Breakevens", "UST 10Y")),
    dict(title="Saudi Arabia shuts the East-West pipeline to Yanbu after drone attacks",
         summary="The 7 million barrel a day line is the only material route that "
                 "bypasses the Strait of Hormuz. Traders quoted by Reuters put up to "
                 "4% of global supply at risk if it stays down. This removes barrels "
                 "rather than pricing the risk of removal - the distinction the "
                 "whole energy leg of this board turns on.",
         source="Reuters via OilPrice", tier=3,
         published="2026-09-14T12:00:00Z", impact=95, url="https://oilprice.com/Latest-Energy-News/World-News/Brent-at-108-Gulf-States-Halt-Hormuz-Talks-as-Houthis-Strike-Saudi-Airbase.html",
         assets=("Brent", "WTI", "Breakevens", "UST 10Y", "S&P 500")),
    dict(title="Brent $108.15, WTI $102.64 - a four-month high, up about 9% on the week",
         summary="Both benchmarks jumped more than 2% at the Monday reopen on the "
                 "postponed talks and the pipeline closure. The carriers give a "
                 "level and a direction, not a settle, so no session change is "
                 "carried on the board.",
         source="OilPrice / Vantage Markets", tier=3,
         published="2026-09-14T12:00:00Z", impact=90, url="https://oilprice.com/Latest-Energy-News/World-News/Brent-at-108-Gulf-States-Halt-Hormuz-Talks-as-Houthis-Strike-Saudi-Airbase.html",
         assets=("Brent", "WTI", "Breakevens")),
    dict(title="September hike odds 86.5%, up from 69.4% on Friday morning",
         summary="Two days out from the decision. The board also carries CME "
                 "FedWatch at 85.5% on 12 September and the prediction venues at "
                 "48-49%; all four readings are on the page and none is picked. An "
                 "oil shock arriving 48 hours before an FOMC is the worst possible "
                 "sequencing for a committee that has three dissents already "
                 "favouring a hike.",
         source="Yahoo Finance", tier=2, published="2026-09-14T11:31:00Z", impact=92,
         url="https://finance.yahoo.com/personal-finance/investing/article/bitcoin-and-ethereum-prices-today-monday-september-14-2026-crypto-prices-trying-to-hold-as-rate-hike-expectations-grow-114245430.html", assets=("UST 2Y", "USD", "S&P 500", "BTC")),
    dict(title="Bitcoin $77,873 and ether $2,514 as rate-hike expectations grow",
         summary="Bitcoin opened 76,806.19, down 0.6% on Sunday's open, and "
                 "recovered through the morning; ether opened 2,475.82, down 2%. "
                 "Crypto is holding rather than breaking, which is more than the "
                 "rates market can say.",
         source="Yahoo Finance", tier=2, published="2026-09-14T11:31:00Z", impact=68,
         url="https://finance.yahoo.com/personal-finance/investing/article/bitcoin-and-ethereum-prices-today-monday-september-14-2026-crypto-prices-trying-to-hold-as-rate-hike-expectations-grow-114245430.html", assets=("BTC", "ETH")),
    dict(title="SEPTEMBER CPI CONSENSUS ALREADY SET AT 3.7% FOR THE 14 OCTOBER PRINT",
         summary="A 30bp acceleration from August's 3.4% is what the street already "
                 "expects - the energy shock arriving in the print rather than a "
                 "surprise waiting to happen. Nowflation's own nowcast is 3.47%, a "
                 "23bp gap to the street. The release panel carries both, marked "
                 "AWAITING with no verdict, because a consensus is not a result.",
         source="Nowflation", tier=3, published="2026-09-14T18:00:00Z", impact=76,
         url="https://nowflation.com/cpi-release-dates", assets=("UST 2Y", "UST 10Y", "USD", "S&P 500")),
    dict(title="UN General Assembly 81 High-Level Week runs 22-28 September",
         summary="The General Debate opens Tuesday 22 September. The one scheduled "
                 "venue where the parties to the Hormuz crisis are in the same "
                 "building; it is the diary entry to watch rather than the event to "
                 "trade.",
         source="United Nations", tier=1, published="2026-09-14T18:00:00Z", impact=58,
         url="https://www.un.org/en/high-level-week-2026", primary_confirmed=True, assets=("Brent", "WTI", "Gold")),
    # ---- 10-13 September: the week the inflation data landed ------------
    dict(title="US CPI holds at 3.4% but core runs hot at 0.3% m/m; hike odds jump",
         summary="Headline y/y 3.4% against 3.4% expected and headline m/m 0.4% "
                 "against 0.4%, both exactly on consensus. Core m/m 0.3% against "
                 "0.2% is the leg that moved the curve: core strips the energy the "
                 "headline is absorbing, so the overshoot is pass-through rather "
                 "than oil. Last inflation print before the FOMC.",
         source="BLS via CNBC", tier=1, published="2026-09-11T12:30:00Z", impact=96,
         url="https://www.cnbc.com/2026/09/11/cpi-inflation-report-august-2026.html", primary_confirmed=True,
         assets=("UST 2Y", "UST 10Y", "USD", "S&P 500", "BTC", "Gold")),
    dict(title="August PPI 5.4% y/y against 5.3% expected; core undershoots at 0.2%",
         summary="Final demand m/m 0.4% exactly on consensus, with goods +1.1% and "
                 "services +0.1% - the whole monthly move is the energy shock "
                 "arriving at the factory gate. Core m/m 0.2% against 0.3% expected "
                 "is the one cool leg of the week. Producer inflation is running "
                 "2pp above consumer inflation: unabsorbed margin pressure that "
                 "resolves into either CPI or earnings.",
         source="BLS via CNBC", tier=1, published="2026-09-10T12:30:00Z", impact=88,
         url="https://www.cnbc.com/2026/09/10/ppi-inflation-report-august-2026.html", primary_confirmed=True,
         assets=("Breakevens", "S&P 500", "UST 10Y")),
    dict(title="ECB raises the deposit rate 25bp to 2.50%, its second hike since the war began",
         summary="Main refinancing rate to 2.65%. All 65 economists in the Reuters "
                 "poll had +25bp, so the decision itself carried no information - "
                 "euro-area HICP at 3.3% in August, a three-year high, is what "
                 "forced it. Two central banks now tightening into the same oil "
                 "shock.",
         source="ECB via Trading Economics", tier=1, published="2026-09-10T12:15:00Z",
         impact=87, url="https://tradingeconomics.com/euro-area/interest-rate",
         primary_confirmed=True, assets=("EUR", "Bunds", "DXY")),
    dict(title="Initial jobless claims 206k against 205k expected; no crack in the labour market",
         summary="Down 1k from a revised 207k. A 1k miss is inside survey noise and "
                 "the board treats it as in line. A labour market with no crack in "
                 "it is precisely what lets a central bank hike into an oil shock.",
         source="DOL via FXStreet", tier=1, published="2026-09-10T12:30:00Z", impact=70,
         url="https://www.dol.gov/ui/data.pdf", primary_confirmed=True,
         assets=("UST 2Y", "USD")),
    dict(title="CME FedWatch puts a 25bp September hike at 85.5%; Kalshi 48% and Polymarket 49% do not",
         summary="THE LARGEST UNRESOLVED DISAGREEMENT ON THIS BOARD. Futures pricing "
                 "and the two prediction venues are nearly forty points apart on the "
                 "same binary event four days out. The board carries the "
                 "disagreement rather than the convenient number; one of these "
                 "venues is about to be very wrong.",
         source="Search aggregate (CME FedWatch / Kalshi / Polymarket)", tier=3,
         published="2026-09-12T12:00:00Z", impact=93, url="https://www.forbes.com/sites/digital-assets/2026/08/31/cme-fedwatch-provides-a-66-chance-fed-will-hike-rates-in-september/",
         assets=("UST 2Y", "USD", "S&P 500", "BTC")),
    dict(title="10-year Treasury yield at 4.974%, the highest since it briefly topped 5% in October 2023",
         summary="Futures curves have shifted to embed a higher terminal rate and a "
                 "longer plateau, tightening global financial conditions before any "
                 "formal move. The front end has repriced 21bp in a week while the "
                 "dollar has not moved at all.",
         source="Rio Times briefing", tier=3, published="2026-09-12T12:00:00Z",
         impact=90, url="https://www.riotimesonline.com/global-economy-briefing-september-12-2026/", assets=("UST 10Y", "UST 2Y", "Gold", "S&P 500")),
    dict(title="Wall Street snaps a four-session losing streak: Dow +0.98%, S&P +0.86%, Nasdaq +0.96%",
         summary="7,656.98 on the S&P, 52,573.29 on the Dow, 26,333.04 on the "
                 "Nasdaq. The rally was oil falling, not inflation cooling - and the "
                 "week was still negative with Friday's rebound in it.",
         source="Washington Post / Rio Times briefing", tier=2,
         published="2026-09-11T20:00:00Z", impact=80, url="https://www.washingtonpost.com/business/2026/09/11/wall-street-stocks-dow-nasdaq/",
         assets=("S&P 500", "Dow Jones", "Nasdaq Comp")),
    dict(title="Brent reverses from a 108.92 open to a 104.42 close as Hormuz talks are announced",
         summary="A four-percent intraday reversal on the announcement that GCC "
                 "foreign ministers would meet Iran's in Oman on a temporary "
                 "shipping arrangement. WTI settled 100.05. The oil market is now "
                 "trading the diplomacy, not the barrels.",
         source="Trading Economics / Fortune", tier=3,
         published="2026-09-11T20:00:00Z", impact=89, url="https://fortune.com/article/price-of-oil-09-11-2026/",
         assets=("Brent", "WTI", "Breakevens", "UST 10Y")),
    dict(title="Pezeshkian: the Strait of Hormuz reopens if the US ends its naval blockade",
         summary="The first stated price for reopening the chokepoint. It converts "
                 "an open-ended supply risk into a bounded, tradeable condition - "
                 "which is exactly why crude sold off into it.",
         source="Iran International / CBS News", tier=3,
         published="2026-09-12T12:00:00Z", impact=91, url="https://www.iranintl.com/en/liveblog/202609050975",
         assets=("Brent", "WTI", "Gold", "Breakevens")),
    dict(title="US Fifth Fleet base in Bahrain heavily damaged; the Abraham Lincoln has no port to pull into",
         summary="Acting Navy Secretary Hung Cao's own words. Loss of forward basing "
                 "degrades escort capacity in the strait, which is the mechanism "
                 "that turns a risk premium into an actual supply disruption.",
         source="US Navy via CBS News", tier=2, published="2026-09-12T12:00:00Z",
         impact=90, url="https://www.cbsnews.com/live-updates/iran-war-us-strait-of-hormuz-oil-gas-price-strikes/", primary_confirmed=True,
         assets=("Brent", "Defence", "Gold", "CHF")),
    dict(title="CARRIERS DISAGREE: Friday's VIX close is either 15.84 (-11.21%) or 14.53 (+1.47%)",
         summary="Opposite signs on the same session, not a rounding gap. The board "
                 "carries 15.84 at confidence 0.5 because three indices closed up "
                 "about 1% and crude fell 2.4%, and a volatility index does not rise "
                 "into that. Both readings are recorded in the conflicts panel.",
         source="Rio Times briefing vs search aggregate", tier=3,
         published="2026-09-12T12:00:00Z", impact=62, url="https://www.riotimesonline.com/global-economy-briefing-september-12-2026/",
         assets=("VIX", "S&P 500")),
    dict(title="UST 10-year reaches 4.818%, a level not seen since November 2023",
         summary="Japan's 10y is at its highest since 1996 and the Bund at a 2011 high. "
                 "A global term-premium repricing, not a US-only story.",
         source="CNBC", tier=2, published="2026-09-07T10:00:00Z", impact=89,
         url="https://www.cnbc.com/2026/09/01/stock-market-today-live-updates.html",
         assets=("UST 10Y", "Bunds", "JGBs", "2s10s")),
    dict(title="NY Fed's Williams: the yield surge is a strong economy, not market "
               "dysfunction",
         summary="Explicitly rules out the intervention narrative. Removes the "
                 "'Fed put on duration' bid that a dysfunction framing would imply.",
         source="Federal Reserve / CNBC", tier=1, published="2026-09-07T09:30:00Z",
         impact=80, url="https://www.federalreserve.gov/newsevents/speeches.htm",
         assets=("UST 10Y", "USD", "S&P 500"), primary_confirmed=True),
    dict(title="Fed's Waller 'inclined to support' holding at 3.50-3.75% on 15-16 September",
         summary="The clearest steer yet from a governor against the hike the front end "
                 "has been pricing. Sets up a live meeting either way.",
         source="Federal Reserve / CNBC", tier=1, published="2026-09-07T09:00:00Z",
         impact=87, url="https://www.federalreserve.gov/newsevents/speeches.htm",
         assets=("UST 2Y", "USD", "BTC"), primary_confirmed=True),
    dict(title="US and Iran exchange strikes near the Strait of Hormuz for the first "
               "time in weeks; crude rises on supply risk",
         summary="Transit risk is the transmission channel: insurance, then freight, "
                 "then headline CPI, then the policy path.",
         source="T. Rowe Price global markets update", tier=3,
         published="2026-09-07T08:00:00Z", impact=88,
         url="https://www.troweprice.com/personal-investing/resources/insights/global-markets-weekly-update.html",
         assets=("Brent", "WTI", "Breakevens")),
    dict(title="Brent tops $100 a barrel as US-Iran escalation continues",
         summary="The level was crossed, not settled at: the last precise mark was a "
                 "97.92 settle on 8 September, up about 1%, and roughly 99 after that "
                 "close. Energy is now the binding input to the inflation leg.",
         source="Search aggregate (9 September market wraps)", tier=3,
         published="2026-09-09T16:18:00Z", impact=91,
         url="https://www.thestreet.com/stock-market-today/stock-market-today-dow-jones-sp-500-nasdaq-updates-sept-08-2026",
         assets=("Brent", "WTI", "Breakevens", "UST 10Y")),
    dict(title="UST 10-year at 4.82%, its highest closing level since 2023, with oil the driver",
         summary="The term-premium move now has an energy engine behind it rather than "
                 "a growth one. That is the combination the September meeting has to "
                 "price.",
         source="Search aggregate (9 September market wraps)", tier=3,
         published="2026-09-09T16:18:00Z", impact=88,
         url="https://tradingeconomics.com/united-states/government-bond-yield",
         assets=("UST 10Y", "2s10s", "Breakevens")),
    dict(title="Ongoing Middle East escalation keeps a lid on crypto; bitcoin holds the high-78s",
         summary="Yahoo puts bitcoin at 78,824.54 at 7:11 a.m. ET, having opened "
                 "0.8% below Tuesday's open - the open itself carries no stated time, "
                 "so it is not held as an observation and is not printed here. A later "
                 "ticker read has it at 79,263, up 1.67% over 24h: the session ground "
                 "higher, it did not break out.",
         source="Yahoo Finance", tier=3,
         published="2026-09-09T11:11:00Z", impact=66,
         url="https://finance.yahoo.com/personal-finance/investing/article/bitcoin-and-ethereum-prices-today-wednesday-september-9-2026-ongoing-escalations-in-the-middle-east-are-keeping-a-lid-on-crypto-112541573.html",
         assets=("BTC", "ETH")),
    dict(title="Crypto sentiment eases to Greed at 66 from 69 on the day",
         summary="The board carried 71 from 7 September. The band has not turned - this "
                 "is drift within GREED, and the source states its own 69-to-66 path "
                 "rather than the move being inferred from the board.",
         source="Crypto Fear & Greed Index", tier=3,
         published="2026-09-09T16:18:00Z", impact=54,
         url="https://cfgi.io/",
         assets=("BTC", "ETH")),
    dict(title="Bitcoin trades near $79.5K, roughly 2% below the 4 September print",
         summary="Carriers spread 79,458-79,899 with a 24h range of 79,081-80,494. The "
                 "post-payrolls squeeze has given back most of its gain.",
         source="Search aggregate (CoinGecko / Coinbase / Bybit)", tier=3,
         published="2026-09-07T10:50:00Z", impact=64,
         url="https://www.coingecko.com/en/coins/bitcoin",
         assets=("BTC", "ETH")),
    dict(title="Crypto sentiment deepens to Greed at 71 while equity sentiment "
               "recovers to Neutral at 54",
         summary="Both gauges moved a full band since the last read. The divergence "
                 "that opened on 4 September has closed from the equity side.",
         source="CFGI / CNN Business", tier=3, published="2026-09-07T10:50:00Z",
         impact=57, url="https://cfgi.io/",
         assets=("BTC", "S&P 500")),
    dict(title="Tesla falls more than 6% after the Cybercab launch, its worst session "
               "since 23 July",
         source="CNBC", tier=2, published="2026-09-04T20:00:00Z", url=_CNBC_MKT,
         impact=70, assets=("TSLA", "Nasdaq"),
         summary="A single-name event, but a large one: Tesla is a meaningful index "
                 "weight and the move was the day's biggest mega-cap dislocation."),
    dict(title="NVIDIA rises 1.8% on a $12.9bn acquisition of AI platform Hugging Face",
         source="CNBC", tier=2, published="2026-09-04T20:00:00Z", url=_CNBC_MKT,
         impact=76, assets=("NVDA", "Nasdaq", "AI complex"),
         summary="The largest listed company in the world buying the default open-source "
                 "model hub. Consolidation at the platform layer, not the chip layer."),
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
    "THE SCHEDULED HOURLY ROUTINE HAS BEEN DELETED, and this is the record of why. "
    "It fired every hour, it succeeded, and it republished the page - but it could "
    "never push to git, because the trigger carried allowed_push_branches: []. "
    "Every run therefore started from the last commit, re-derived the same "
    "environment limits, spent a full model context doing it, published its finds "
    "and lost them when the container went. Its work accumulated INSIDE one run "
    "and never across runs, so each run's cost bought nothing the next run could "
    "use. Scanning is now on demand: one session, one scan, one commit, and the "
    "finds persist because a session with a checkout can push. What the loop was "
    "genuinely for - a price that keeps moving between scans - is served by the "
    "live client in this page instead, which costs nothing and is real time to "
    "the second.",
    "THE REASON A SNAPSHOT IS BEHIND, stated plainly. Every number below came "
    "through WebSearch, which returns cached page summaries, and a snapshot cannot "
    "be anything but behind. The fix is not a better search: this file carries a "
    "live client that opens a Binance combined stream in your own browser. Opened "
    "from disk it is real time to the second for BTC, ETH and a gold proxy. Viewed "
    "as a published artifact the sandbox blocks the connection and you get exactly "
    "what you see here, honestly aged. The badge at the top of the LIVE panel says "
    "which.",
    "VIX, 11 SEPTEMBER, AND THE CARRIERS DO NOT AGREE ON THE SIGN. Rio Times "
    "prints 15.84, down 11.21%; a separate aggregate prints 14.53, up 1.47%. Not a "
    "rounding gap - opposite directions on the same session. The board carries "
    "15.84 at confidence 0.5, the lowest on the board, on the tape: three indices "
    "closed up about 1% and crude fell 2.4%, and a volatility index does not rise "
    "into that. The 14.53 reading is also arithmetically consistent with a 14.32 "
    "prior, which is the value THIS BOARD held for 4 September - a coincidence "
    "worth naming, because a carrier agreeing with our own stale number is not "
    "corroboration.",
    "FOMC HIKE ODDS, AND THIS IS THE LARGEST UNRESOLVED DISAGREEMENT ON THE PAGE. "
    "CME FedWatch is quoted at 85.5% for a 25bp hike on 12 September. Kalshi is "
    "quoted at 48% and Polymarket at 49%. Nearly forty points apart on the same "
    "binary event four days out. A futures-implied probability and a prediction "
    "market are not the same statistic and the gap may partly be that, but not "
    "forty points of it. No number is picked; all three are carried.",
    "WTI, 11 September: 100.05 on the October contract (Washington Post) against "
    "99.99 (Trading Economics). Six cents, recorded rather than averaged away, "
    "because the discipline that keeps a six-cent gap visible is the same one that "
    "keeps a forty-point gap visible.",
    "BRENT, 11 September: the close is 104.42 and the open is 108.92, and the "
    "stated -2.98% implies a 107.63 prior close. All three are consistent with a "
    "four-percent intraday reversal on the Hormuz talks announcement, but the "
    "board holds only the close as a number and the open as prose, because an "
    "intraday path built from two carriers is a chart, not an observation.",
    "US RETAIL SALES DATE CORRECTED. The board carried 15 September. Two carriers "
    "independently state the Census advance report for August lands 16 September "
    "at 08:30 ET, the same day as the FOMC and five and a half hours before it. A "
    "wrong date on a countdown is worse than no countdown, and this one was ticking "
    "confidently toward the wrong day.",
    "CRYPTO FEAR & GREED, 13 September: 66 (feargreedmeter), 69 (a daily view of "
    "the same index) and 48 NEUTRAL (cfgi.io's Bitcoin-specific gauge) on the same "
    "day. The BAND is what three of the four agree on; the digit is not. 66 is "
    "carried at confidence 0.55 and the spread is recorded.",
    "ETHEREUM, 12 September: the same article's headline says +2.6% where its body "
    "says +2.8%. The body figure is carried. A publication disagreeing with itself "
    "inside one page is the cheapest possible reminder of what a Tier 3 source is.",
    "BITCOIN, 13 September: four carriers in one retrieval gave 77,242.79, "
    "77,207.90, 77,155.41 and 77,115.78 - a 127-dollar cluster, which is a normal "
    "cross-venue spread rather than a disagreement about fact. The CoinDesk quote "
    "is carried ONLY because it is the one that states its own time (05:22Z); the "
    "other three are timeless and a timeless price cannot be aged. That is the "
    "whole reason this page carries a live client: in a browser none of this "
    "matters, because the Binance stream replaces the cell within a second.",
    "THE RELEASE CLOCK NOW RUNS TO 17 DECEMBER, and that is deliberate rather "
    "than decorative. Scheduled release dates are PUBLISHED IN ADVANCE and do "
    "not move, so eighteen pending events can be loaded in one pass and the "
    "countdown panel never runs dry - two days ago it held two, both on the same "
    "Wednesday. What still needs a human scan is the ACTUALS, and those only "
    "exist on the days they print. This is the whole argument against a "
    "scheduled loop: the calendar is static and the actuals are rare.",
    "FOMC HIKE ODDS, FOUR READINGS AND NO RESOLUTION. Yahoo puts them at 86.5% on "
    "14 September, up from 69.4% on Friday morning. CME FedWatch was quoted at "
    "85.5% on the 12th. Kalshi was 48% and Polymarket 49%. The futures-implied "
    "readings agree with each other and the prediction venues agree with each "
    "other, and the two camps are nearly forty points apart two days before the "
    "decision. All four are on the page.",
    "PAYROLLS DATE: one carrier put the September employment report on 3 October, "
    "which is a SATURDAY. 2 October is carried - first Friday, the published "
    "cadence - and the bad date is recorded here rather than silently corrected, "
    "because a carrier that gets a weekday wrong is telling you something about "
    "its other dates.",
    "US RETAIL SALES AFTER SEPTEMBER IS NOT ON THIS BOARD. Census has moved its "
    "economic indicator calendar from October onward to TBA following a lapse in "
    "federal funding. The 16 September release is dated and carried; the ones "
    "after it are genuinely unscheduled, and an invented date on a countdown is "
    "worse than an absent row.",
    "BITCOIN, 14 September: 77,873.33 at a stated 7:31 a.m. ET against 77,782 "
    "from a carrier that states no time. Ninety-one dollars, recorded. The timed "
    "quote is carried for the same reason as yesterday's: a price with no "
    "timestamp cannot be aged.",
    "CRYPTO LIQUIDATIONS: a later read reverses the side but cannot be carried. "
    "COINOTAG gives $444.82m over 24 hours with longs at 79% and Bitcoin longs at "
    "$111.34m against $9.37m of shorts - the mirror of the 4 September window the "
    "board holds, where shorts were 87%. No carrier states when that newer window "
    "ends, and a liquidation total with no window end cannot be aged or placed "
    "against a price, so the precisely-dated older window stays and the newer "
    "direction is recorded in the panel note instead of replacing it.",
    "MEGACAP EQUITIES were re-scanned to the WEEK of 7-11 September, which is the "
    "only basis any carrier stated. NVIDIA -4.45%, Microsoft -2.84%, Apple +1.24%. "
    "The board had been carrying NVIDIA at +7.0% for the previous week: two "
    "consecutive weekly reads pointing opposite ways, which is a fact about the "
    "tape rather than an error in either read. Market caps are from a separate "
    "early-September carrier and are NOT on the same basis as the weekly moves - "
    "stated here because a cap and a change sitting in one row invite the "
    "assumption that they share a timestamp.",
    "EQUITY AND CRYPTO SENTIMENT NOW POINT OPPOSITE WAYS. The CNN gauge reads 35, "
    "FEAR, for the 10 September session; the crypto gauge reads 66, GREED, on the "
    "13th. Both are sourced, neither is wrong, and the divergence is the "
    "observation - it is not reconciled into a single mood.",
    "CORROBORATION, for once rather than conflict. The loop and this session "
    "searched independently and both returned bitcoin at 78,824.54 for 7:11 a.m. "
    "ET on 9 September, and both returned 78,893.77 at 04:30Z. Two independent "
    "retrievals agreeing on price AND time is the strongest evidence this "
    "environment can produce, and it is worth recording as such - the file is "
    "otherwise a catalogue of carriers disagreeing.",
    "CORRECTION, mine. This session read the same Coinpedia page at 18:40Z and "
    "stamped it with its own retrieval time, not knowing the loop had already "
    "read it at 06:37Z. Same page, same price, one observation. The later stamp "
    "was removed rather than kept, because two anchors would double-count it and "
    "put a liquidity level at 18:40Z that nothing was observed at. The earlier "
    "read is the evidence and is what the board carries.",
    "BTC 8 September: the carriers were further apart than on any previous scan - "
    "78,345.81, 78,564.71, 79,109 and 79,115, and one summary described the "
    "cross-feed range as 79,055-80,055, which does not even contain two of those "
    "quotes. No number in that set can be called the price. 78,564.71 is carried "
    "because it is the only one that arrived with its own 24h change (-1.55%) and a "
    "stated cause, so it can be checked; it is Tier 3 at confidence 0.6 and the "
    "spread is recorded here rather than resolved.",
    "The 7 September operator ticker read of 79,170.00 was superseded, not "
    "corrected. It was accurate when reported and outranked search at the time. It "
    "is a day old now, which is precisely the failure mode the live client exists "
    "to end.",
    "Brent 8 September is a THRESHOLD, not a print: the source states only \"above "
    "$98 a barrel\". It is carried at 98.0 with no change figure, because the "
    "session move was not reported and inventing one would be fabrication. "
    "Confidence 0.55 is the lowest on the board and says so.",
    "BTC 7 September: carriers quoted 79,458.00, 79,571.82 and 79,899.09 within the "
    "same retrieval, with a reported 24h range of 79,081-80,494. That is a normal "
    "cross-venue spread rather than a disagreement about fact. The middle quote is "
    "carried at Tier 3 with the spread stated, and no carrier published a quote time "
    "so the stamp is the retrieval time.",
    "The board previously carried BTC at 81,240.29 from 4 September and showed it for "
    "three days. It was not wrong when captured; it was stale, which the age counter "
    "said and the number did not. Re-scanned to 79,571.82 on 7 September.",
    "Crypto Fear & Greed on 7 September: trackers spread 60 to 74 on the same day. The "
    "band (GREED) is robust, the digit is not. 71 is carried at reduced confidence and "
    "the spread is recorded rather than resolved to the most convenient reading.",
    "NVIDIA market cap: one carrier gives $5.58tn, another $5.42tn at $224.41 a share "
    "in the same week. Both are carried in the note; the larger is shown and the "
    "disagreement is not hidden.",
    "Broadcom and Meta were searched for and WITHHELD: no market cap or session move "
    "could be attributed to a named carrier, so no number is shown. The gap is "
    "recorded here rather than filled with an estimate.",
    "Bitcoin was initially carried at ~$79,000 from a Tier-4 description. That was "
    "WRONG: two Tier-2 sources price it at $81,240 after a 5% short squeeze. The "
    "corrected figure is carried and the error is recorded rather than erased.",
    "Gold was initially carried at ~$4,500 from a descriptive summary. The 5 September "
    "briefing prints 4,429 with a -1.14% session; the corrected figure is carried.",
    "US 10Y: CNBC described the close as 'little changed at 4.76%'; the 5 September "
    "briefing prints 4.789%, corroborating a separate account of a climb toward 4.80% "
    "after payrolls. The higher, corroborated figure is carried at 0.80 confidence.",
    "BTC 10 August: this capture reads Fortune's article for that date at "
    "$65,003.57 (7:30 a.m. ET, quoted directly). An earlier capture carried "
    "$64,848.91 from the same outlet and date. Both cannot be the session's "
    "price. The directly quoted, precisely timed figure is carried and the "
    "earlier one is recorded here rather than quietly overwritten.",
    "Fortune price articles were previously stamped 20:00Z as though they were "
    "closes. They are morning prints and each states its own Eastern time, "
    "ranging 4:00-9:00 a.m. ET across the series. Every stamp is now taken from "
    "its own article. The heatmap places anchors on a time axis, so an 8-hour "
    "error moved them.",
    "The liquidation heatmap is built from 21 dated BTC observations, not a "
    "continuous series. Between observations nothing is known, so the pending-level "
    "field is held constant and the price track marks only the instants actually "
    "observed. The time resolution is the data's, not the renderer's.",
    "BTC 4 September carries two observations: Fortune at 04:00 ET ($79,697) and "
    "Yahoo at 07:21 ET ($81,240.29). Both are pre-payrolls and both are kept - "
    "they are the only intraday range in the series, not a contradiction.",
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
        "market_priced": "VENUES DISAGREE on a 25bp hike for 16 September: CME "
                         "FedWatch 85.5% on 12 September, Kalshi 48%, Polymarket "
                         "49%. Nearly forty points apart four days out. The August "
                         "CPI core monthly at 0.3% against 0.2% expected is what "
                         "moved the futures leg.",
        "source": _FRB_MIN, "tier": 1,
    },
    "ecb": {
        "target": "2.50% (deposit), 2.65% (main refi)",
        "last_action": "HIKED 25bp, 10 September 2026",
        "dissents": "n/a",
        "chair": "Lagarde", "next": "",
        "market_priced": "Fully anticipated - all 65 economists in the Reuters poll "
                         "had +25bp, so the decision itself carried no information. "
                         "Second hike since the war began. The next meeting date has "
                         "not been sourced and is therefore not shown.",
        "source": "https://tradingeconomics.com/euro-area/interest-rate",
        "tier": 1,
    },
    "inflation": {
        "us_cpi_yoy": "3.4% (August, released 11 Sep) - unchanged, in line",
        "us_core_cpi_yoy": "2.4% (August) - in line, a full point BELOW headline",
        "us_cpi_mom": "+0.4% (August, after +0.1% in July) - in line",
        "us_core_cpi_mom": "+0.3% (August) vs +0.2% expected - the hot leg",
        "peak": "3.8% y/y in April 2026",
        "ez_hicp_yoy": "3.3% (August, from 2.9% in July) - a three-year high",
        "source": _BLS_CPI, "tier": 1,
    },
    "labor": {
        "nfp": "+162k (August) vs +53k expected",
        "unemployment": "4.1%, unchanged and as expected",
        "claims": "206k for the week to 5 Sep vs 205k expected, from a revised 207k",
        "source": "https://www.bls.gov/news.release/empsit.nr0.htm", "tier": 1,
    },
}

REGIME = "INFLATION-DOMINANT"
REGIME_BASIS = (
    "Established from the tape, and RE-ESTABLISHED on 11 September against newer "
    "evidence than the payrolls print it originally rested on. The August CPI "
    "landed with the headline exactly on consensus and core monthly 10bp hot, and "
    "the market traded the CORE leg: hike odds rose within the hour and the 10-year "
    "reached 4.974%, the highest since it briefly topped 5% in October 2023. A "
    "3x upside payrolls surprise had already been SOLD in equities a week earlier "
    "while the front end sold off. Good news is bad news, so the policy path is the "
    "binding constraint. The energy shock is feeding the inflation leg directly - "
    "Brent traded 108.92 before closing 104.42 on 11 September and WTI settled at "
    "100.05 - and the ECB delivered its second hike of the war on 10 September, "
    "which points the same way from the other side of the Atlantic. The one piece "
    "of evidence pointing elsewhere is the dollar: 99.10 and unmoved while the "
    "front end repriced 21bp, which is carried on the board rather than argued away."
)


GAUGES = [
    dict(key="CNN_FG", label="Equity Fear & Greed", value=35.0, band="FEAR",
         as_of=SENT13, source="CNN Business, via finhacker historical series", tier=3,
         url="https://edition.cnn.com/markets/fear-and-greed", confidence=0.6,
         note="RE-READ 13 September: 35, FEAR, for the 10 September session - the "
              "freshest DATED value any carrier states, which is why the stamp is "
              "the read and the session is named here rather than invented into it. "
              "The board carried 54 NEUTRAL for 4 September: nineteen points in six "
              "sessions and the band has turned. Note what it did NOT do - it did "
              "not recover on Friday's 1% rally, because the index is built on "
              "breadth, momentum and spreads and those did not repair."),
    dict(key="CRYPTO_FG", label="Crypto Fear & Greed", value=66.0, band="GREED",
         as_of=SENT13, source="Crypto Fear & Greed Index (feargreedmeter)", tier=3,
         url="https://feargreedmeter.com/crypto-fear-and-greed-index", confidence=0.55,
         note="RE-READ 13 September: 66, GREED, unchanged from the 9 September read. "
              "PROVIDERS DISAGREE AND THE DIGIT IS THE WEAK PART: a daily view of "
              "the same index reads 69 and cfgi.io's Bitcoin-specific gauge reads 48 "
              "NEUTRAL on the same day. The band - greed, not fear - is what three "
              "of the four agree on, and it is the only part carried with "
              "confidence. Worth holding beside the equity gauge at 35 FEAR: crypto "
              "and equity sentiment are pointing in opposite directions."),
]


LIQUIDATIONS = dict(
    window="24h to 03:52 UTC, 4 September 2026",
    total_usd=468_590_000.0, long_usd=60_490_000.0, short_usd=408_100_000.0,
    as_of=LIQ, source="CoinGlass via COINOTAG", tier=3, url=_COINOTAG,
    asset_usd=272_600_000.0, asset_label="Bitcoin", asset_short_pct=92.0,
    note="Two other windows were reported the same day - $544.85m and a $415m "
         "shorts-only figure - covering different periods and scopes. The window is "
         "stated here rather than the largest number being chosen. "
         "STALE, AND DELIBERATELY NOT REPLACED. A later COINOTAG read gives $444.82m "
         "over 24 hours with LONGS at $350.87m, 79% of the total, and Bitcoin longs "
         "at $111.34m against just $9.37m of shorts - the mirror image of the window "
         "below. It is not carried because no carrier states when that window ENDS, "
         "and a liquidation figure without a window end cannot be aged or placed "
         "against a price. The 4 September window is kept because it has one "
         "(03:52 UTC). The direction of the newer read is the thing to take from "
         "this: the squeeze that cleared shorts in early September has reversed, and "
         "it is longs being carried out into the CPI.",
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
    dict(headline="OPEC+ met Saturday 5 September",
         region="OPEC+", severity=60, as_of="2026-09-05T08:00:00Z",
         source="Rio Times briefing", tier=3, url=_RIO,
         status="HELD 5 SEPTEMBER - OUTCOME NOT SOURCED",
         channel="An output surprise would have landed on top of an already-tight "
                 "geopolitical bid. The meeting has since happened and no carrier read "
                 "since has stated its outcome, so the severity is cut and the status "
                 "says what is actually known rather than leaving a stale 'today' on "
                 "the board",
         assets=("Brent", "WTI", "CAD", "NOK")),
    # ---- 12 September ---------------------------------------------------
    dict(headline="US Fifth Fleet base in Bahrain heavily damaged; the Abraham Lincoln "
                  "has no port to pull into",
         region="Persian Gulf", severity=92, as_of="2026-09-12T12:00:00Z",
         source="Acting US Navy Secretary Hung Cao, via CBS News", tier=2,
         url="https://www.cbsnews.com/live-updates/iran-war-us-strait-of-hormuz-oil-gas-price-strikes/",
         status="ESCALATING",
         channel="Loss of forward basing degrades escort capacity inside the strait -> "
                 "convoy frequency falls -> war-risk insurance and freight rise -> "
                 "delivered energy cost -> goods CPI with a lag. This is the mechanism "
                 "that turns a risk premium into an actual supply disruption, and it is "
                 "the most severe item on this board",
         assets=("Brent", "WTI", "Gold", "CHF", "Defence")),
    dict(headline="Pezeshkian: the Strait of Hormuz reopens if the US ends its naval blockade",
         region="Strait of Hormuz", severity=90, as_of="2026-09-12T12:00:00Z",
         source="Iran International / CBS News", tier=3,
         url="https://www.iranintl.com/en/liveblog/202609050975",
         status="CONDITION STATED",
         channel="The first stated PRICE for reopening the chokepoint. It converts an "
                 "open-ended supply risk into a bounded, tradeable condition, which is "
                 "why crude sold off four percent into it rather than rallying on the "
                 "reminder that the strait is shut",
         assets=("Brent", "WTI", "Gold", "Breakevens")),
    dict(headline="Iran-GCC Hormuz talks in Salalah POSTPONED; Saudi amendments, "
                  "Bahrain refused to attend",
         region="Strait of Hormuz", severity=91, as_of="2026-09-13T20:00:00Z",
         source="Oman FM Badr Al Busaidi, via CNN / Al Jazeera", tier=2, url="https://www.aljazeera.com/news-analysis/2026/9/14/temporary-hormuz-solution-deferred-as-iran-arab-summit-falls-through",
         status="POSTPONED - NO NEW DATE",
         channel="THE BOARD CALLED THIS ONE AND IT BROKE THE OTHER WAY. Brent fell "
                 "four percent on Friday on the ANNOUNCEMENT of this meeting and the "
                 "board said the meeting itself was the largest event risk into "
                 "Monday's open. It was deferred late Sunday 'in the interest of "
                 "consensus' - Saudi Arabia filed amendments objecting that the "
                 "Iran-Oman wording would establish a new status quo, and Bahrain "
                 "said it would not attend. Brent reopened above 108. No new date "
                 "has been published, so there is nothing to count down to",
         assets=("Brent", "WTI", "Gold", "Breakevens", "UST 10Y")),
    # ---- 14 September ---------------------------------------------------
    dict(headline="Saudi Arabia shuts the East-West pipeline to Yanbu after drone "
                  "attacks; up to 4% of global supply at risk",
         region="Saudi Arabia", severity=94, as_of="2026-09-14T12:00:00Z",
         source="Reuters via OilPrice / Trading Economics", tier=3, url="https://oilprice.com/Latest-Energy-News/World-News/Brent-at-108-Gulf-States-Halt-Hormuz-Talks-as-Houthis-Strike-Saudi-Airbase.html",
         status="ESCALATING",
         channel="THE HIGHEST-SEVERITY ITEM ON THIS BOARD, because it is the only "
                 "one that removes barrels rather than pricing the risk of it. The "
                 "East-West line carries 7 million barrels a day to the Red Sea port "
                 "of Yanbu and is the ONLY material route that bypasses Hormuz. "
                 "Shutting it does not add a premium to the waterborne barrel - it "
                 "deletes the hedge against the strait itself, which is why crude "
                 "went to a four-month high on it",
         assets=("Brent", "WTI", "Breakevens", "UST 10Y", "S&P 500")),
    dict(headline="Houthi strike on a Saudi airbase",
         region="Red Sea", severity=83, as_of="2026-09-14T12:00:00Z",
         source="OilPrice", tier=3, url="https://oilprice.com/Latest-Energy-News/World-News/Brent-at-108-Gulf-States-Halt-Hormuz-Talks-as-Houthis-Strike-Saudi-Airbase.html", status="ESCALATING",
         channel="Widens the conflict from a chokepoint dispute to strikes on the "
                 "territory of the swing producer. The transmission is the same as "
                 "the pipeline: what was a transit risk is becoming a production "
                 "risk",
         assets=("Brent", "WTI", "Defence")),
    dict(headline="UN General Assembly 81: General Debate and High-Level Week",
         region="Diplomacy", severity=64, as_of="2026-09-22T00:00:00Z",
         source="United Nations", tier=1, url="https://www.un.org/en/high-level-week-2026",
         status="SCHEDULED 22-28 SEPTEMBER - TIMES NOT PUBLISHED PER SESSION",
         channel="The one scheduled venue where the parties to this conflict are in "
                 "the same building. It resolves nothing by itself, but every "
                 "de-escalation in this crisis so far has been announced around a "
                 "meeting rather than at one - so it is the diary entry to watch, "
                 "not the event to trade",
         assets=("Brent", "WTI", "Gold")),
]

# Observed BTC closes. The liquidation heatmap is built from these and nothing
# else: no price between two anchors is interpolated or invented, so the field
# is coarse in time by construction. Window high/low bound the price axis and
# are themselves sourced.
_FA = "https://fortune.com/article/price-of-bitcoin-%s-2026/"

# Every dated BTC observation that could be attributed to a named carrier with a
# stated time. Fortune publishes one article per day and states the Eastern time
# in the copy; the time VARIES by article (4:00 to 9:00 a.m. ET), so each stamp is
# taken from its own article rather than assumed. August-September 2026 is EDT,
# so ET + 4h = UTC.
#
# The earlier capture carried only five of these and stamped the Fortune ones at
# 20:00Z, which was wrong by eight hours - Fortune quotes a morning print, not a
# close. Fixed here; the heatmap places anchors on a time axis, so the error
# was visible in the chart, not merely cosmetic.
PRICE_ANCHORS = [
    dict(date="2026-08-03T11:00:00Z", price=62706.56, source="Fortune", tier=3,
         url=_FA % "08-03", note="7:00 a.m. ET print."),
    dict(date="2026-08-04T20:00:00Z", price=63465.20, source="YCharts", tier=3,
         url="https://ycharts.com/indicators/bitcoin_price",
         note="Daily close. Time of day not stated by the carrier; 20:00Z is the "
              "US close convention and is the one assumption in this series."),
    dict(date="2026-08-05T09:45:00Z", price=64137.26, source="Fortune", tier=3,
         url=_FA % "08-05", note="5:45 a.m. ET print."),
    dict(date="2026-08-10T11:30:00Z", price=65003.57, source="Fortune", tier=3,
         url=_FA % "08-10",
         note="7:30 a.m. ET print. CORRECTS an earlier read of 64,848.91 for this "
              "same date and outlet - see conflicts."),
    dict(date="2026-08-14T10:45:00Z", price=62829.48, source="Fortune", tier=3,
         url=_FA % "08-14", note="6:45 a.m. ET print."),
    dict(date="2026-08-17T10:15:00Z", price=63260.20, source="Fortune", tier=3,
         url=_FA % "08-17", note="6:15 a.m. ET print."),
    dict(date="2026-08-18T10:45:00Z", price=64135.48, source="Fortune", tier=3,
         url=_FA % "08-18", note="6:45 a.m. ET print."),
    dict(date="2026-08-19T10:30:00Z", price=64339.33, source="Fortune", tier=3,
         url=_FA % "08-19", note="6:30 a.m. ET print, the session before the jump."),
    dict(date="2026-08-20T10:15:00Z", price=71970.80, source="Fortune", tier=3,
         url=_FA % "08-20",
         note="6:15 a.m. ET print. +11.9% on the previous observation - the "
              "Treasury-buyback short squeeze Fortune covered separately on 23 Aug."),
    dict(date="2026-08-21T12:00:00Z", price=76712.47, source="Fortune", tier=3,
         url=_FA % "08-21", note="8:00 a.m. ET print."),
    dict(date="2026-08-24T13:00:00Z", price=78976.18, source="Fortune", tier=3,
         url=_FA % "08-24", note="9:00 a.m. ET print."),
    dict(date="2026-08-26T11:15:00Z", price=78745.95, source="Fortune", tier=3,
         url=_FA % "08-26", note="7:15 a.m. ET print."),
    dict(date="2026-08-27T11:15:00Z", price=79707.18, source="Fortune", tier=3,
         url=_FA % "08-27", note="7:15 a.m. ET print."),
    dict(date="2026-08-28T10:30:00Z", price=79132.61, source="Fortune", tier=3,
         url=_FA % "08-28", note="6:30 a.m. ET print."),
    dict(date="2026-08-31T12:30:00Z", price=78414.14, source="Fortune", tier=3,
         url=_FA % "08-31", note="8:30 a.m. ET print."),
    dict(date="2026-09-01T12:00:00Z", price=78154.66, source="Fortune", tier=3,
         url=_FA % "09-01", note="8:00 a.m. ET print."),
    dict(date="2026-09-02T12:00:00Z", price=76672.01, source="Fortune", tier=3,
         url=_FA % "09-02", note="8:00 a.m. ET print."),
    dict(date="2026-09-03T12:00:00Z", price=77934.11, source="Fortune", tier=3,
         url=_FA % "09-03", note="8:00 a.m. ET print."),
    dict(date="2026-09-04T08:00:00Z", price=79697.00, source="Fortune", tier=3,
         url=_FA % "09-04", note="4:00 a.m. ET print, before the payrolls release."),
    dict(date="2026-09-04T11:21:00Z", price=81240.29, source="Yahoo Finance", tier=2,
         url=_YF,
         note="07:21 ET print, still before the 08:30 ET payrolls release. Second "
              "observation of the same day and the only intraday range in the set."),
    dict(date="2026-09-05T18:27:00Z", price=80018.94, source="Search aggregate "
         "(Investing.com / YCharts)", tier=3,
         url="https://www.investing.com/crypto/bitcoin/historical-data",
         note="2:27 p.m. ET. The carrier could not be narrowed to one page, so it "
              "is tiered as an aggregate. Sits inside a separately reported "
              "79,465-80,195 range for the day, which is corroboration, not proof."),
]

# Sourced window extremes, computed from the observations above rather than taken
# from a third-party summary: the observed set is now dense enough to define its
# own range, and a bound that disagrees with the points inside it is a bug.
_PX = [a["price"] for a in PRICE_ANCHORS]
BTC_WINDOW = {"lo": round(min(_PX) * 0.985, 2), "hi": round(max(_PX) * 1.015, 2),
              "avg": round(sum(_PX) / len(_PX), 2),
              "span": "3 August - 5 September 2026",
              "source": "computed from %d sourced observations" % len(_PX), "tier": 3,
              "url": "https://fortune.com/article/price-of-bitcoin-09-04-2026/"}

# Largest listings by market value, September 2026.
EQUITIES = [
    dict(ticker="NVDA", name="NVIDIA", mktcap_usd=5.58e12, change_pct=-4.45,
         as_of=CLOSE11, source="Trading Strategy Guides weekly recap", tier=3,
         url="https://tradingstrategyguides.com/weekly-market-recap-september-7-september-11-2026-indices-slide-as-tech-leaders-diverge/",
         note="RE-SCANNED 13 September, and the sign has FLIPPED. The change shown "
              "is the WEEK of 7-11 September: -4.45% to $218.29, the biggest "
              "laggard of the megacaps. The board was carrying +7.0% for the week "
              "to 4 September at $224.41 - two consecutive weekly reads, opposite "
              "directions, and the six-dollar round trip in the share price is what "
              "that costs. Still the largest listed company in the world at $5.58tn; "
              "a second carrier put the cap at $5.42tn and the spread is recorded, "
              "not resolved."),
    dict(ticker="AAPL", name="Apple", mktcap_usd=4.70e12, change_pct=1.24,
         as_of=CLOSE11, source="Trading Strategy Guides weekly recap", tier=3,
         url="https://tradingstrategyguides.com/weekly-market-recap-september-7-september-11-2026-indices-slide-as-tech-leaders-diverge/",
         note="Week of 7-11 September: +1.24% to $332.27, the only megacap up on a "
              "week the S&P fell 1.15%. Tech leadership is diverging rather than "
              "moving as a block, which is what a rate shock does to a complex "
              "priced on duration."),
    dict(ticker="GOOGL", name="Alphabet", mktcap_usd=4.10e12,
         as_of=CLOSE, source="Motley Fool", tier=3, url=_FOOL,
         note="Session move not sourced; the market cap is."),
    dict(ticker="MSFT", name="Microsoft", mktcap_usd=3.71e12, change_pct=-2.84,
         as_of=CLOSE11, source="Trading Strategy Guides weekly recap", tier=3,
         url="https://tradingstrategyguides.com/weekly-market-recap-september-7-september-11-2026-indices-slide-as-tech-leaders-diverge/",
         note="Week of 7-11 September: -2.84% to $495.63."),
    dict(ticker="TSLA", name="Tesla", change_pct=-6.00,
         as_of=CLOSE, source="CNBC", tier=2, url=_CNBC_MKT,
         note="Fell more than 6% after the Cybercab launch, its worst session since "
              "23 July. Market cap not sourced at this timestamp."),
    dict(ticker="AMZN", name="Amazon", mktcap_usd=2.78e12,
         as_of=SPOT, source="Motley Fool", tier=3, url=_FOOL,
         note="Fifth largest listing. Session move not sourced; the market cap is."),
    dict(ticker="AVGO", name="Broadcom",
         as_of=SPOT, source="Search aggregate", tier=4, url=_FOOL,
         note="WITHHELD. Named in the scan but no market cap or session move could be "
              "attributed to a carrier, so nothing is carried. Listed here only so the "
              "gap is visible rather than silently absent."),
    dict(ticker="META", name="Meta Platforms",
         as_of=SPOT, source="Search aggregate", tier=4, url=_FOOL,
         note="WITHHELD for the same reason as AVGO: searched, not attributable, so "
              "no number is invented."),
]
# Entries that carry neither a market cap nor a session move are a record of a
# known gap, not data. They are dropped before the board is built - the note
# survives in the source, the empty row never reaches the page.
EQUITIES = [x for x in EQUITIES
            if x.get("mktcap_usd") is not None or x.get("change_pct") is not None]

# Earnings. Where only a date is published the countdown runs at day granularity
# and says so; where only a week is published there is no countdown at all.
EARNINGS = [
    dict(ticker="ORCL", name="Oracle", when="2026-09-10T00:00:00Z",
         session="UNKNOWN", status="SCHEDULED", time_confirmed=False,
         source="Investing.com", tier=3,
         url="https://www.investing.com/equities/oracle-corp-earnings",
         note="Date published; the hour is not, so the countdown is day-granularity."),
    dict(ticker="ADBE", name="Adobe", window="week of 7-11 September 2026",
         session="UNKNOWN", status="SCHEDULED", source="MarketScreener", tier=3,
         url="https://www.marketscreener.com/news/weekly-earnings-calendar-oracle-vs-adobe-a-battle-of-old-hands-ce785bdad08cf02d",
         note="Only the week is published. No countdown is shown for a window."),
    dict(ticker="NVDA", name="NVIDIA", when="2026-11-17T00:00:00Z",
         session="AMC", status="SCHEDULED", time_confirmed=False,
         source="Wall Street Horizon", tier=3,
         url="https://www.wallstreethorizon.com/nvidia-earnings-calendar",
         note="Confirmed for Tuesday 17 November, after market. The largest single "
              "scheduled equity event on the board."),
    dict(ticker="AVGO", name="Broadcom", when="2026-09-02T00:00:00Z",
         session="AMC", status="REPORTED", time_confirmed=False,
         source="Broadcom investor relations", tier=1,
         url="https://investors.broadcom.com/news-releases/news-release-details/broadcom-inc-announce-third-quarter-fiscal-year-2026-financial",
         note="Q3 FY2026, announced by the company itself - Tier 1."),
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
    from .observe import merge as _merge
    # Baseline plus whatever a later unattended scan stored. The store is
    # data, not code, so a scheduled run never edits this file.
    snap.price_anchors = _merge([PriceAnchor(**a) for a in PRICE_ANCHORS])
    snap.btc_window = dict(BTC_WINDOW)
    snap.equities = [Equity(**x) for x in EQUITIES]
    snap.earnings = [Earning(**x) for x in EARNINGS]
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
