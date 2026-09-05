"""Global macro calendar: structural release metadata (spec section 3).

What this module contains and does not contain
----------------------------------------------
CONTAINS: which agency publishes what, in which unit, on which clock, under
which recurrence rule, and how a surprise in that series should be read
(growth impulse vs inflation impulse).  These are stable institutional facts.

DOES NOT CONTAIN: any actual, consensus, previous or forecast value, and no
hardcoded future dates for releases whose dates are set by a published
agency schedule rather than by a rule.  Those must be ingested
(``macro.data.calendar_feed``) or supplied by the user.

Every entry carries ``confidence`` and ``verify`` so the clock time can be
checked against the issuing agency before it is traded.
"""

from __future__ import annotations

import calendar as _cal
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from enum import Enum
from zoneinfo import ZoneInfo

from .scoring import EventClass
from .surprise import IndicatorSpec


class Recurrence(str, Enum):
    WEEKLY = "WEEKLY"                    # rule-derivable
    NTH_WEEKDAY = "NTH_WEEKDAY"          # rule-derivable, e.g. first Friday
    NTH_BUSINESS_DAY = "NTH_BUSINESS_DAY"  # rule-derivable (ex-holidays)
    LAST_WEEKDAY = "LAST_WEEKDAY"        # rule-derivable
    AGENCY_SCHEDULE = "AGENCY_SCHEDULE"  # published date list: must be ingested
    EVENT_DRIVEN = "EVENT_DRIVEN"        # unscheduled by nature


@dataclass(frozen=True)
class Release:
    code: str
    label: str
    country: str
    agency: str
    event_class: EventClass
    tz: str
    clock: str | None                    # local HH:MM, None = no fixed time
    recurrence: Recurrence
    # rule parameters, meaningful per recurrence type
    weekday: int | None = None           # 0=Mon .. 6=Sun
    ordinal: int | None = None           # 1=first, -1=last
    tier_impact: int = 2                 # 1 = top tier mover, 3 = background
    indicator: IndicatorSpec | None = None
    confidence: float = 0.8              # confidence in the clock/recurrence
    verify: str = ""
    notes: str = ""

    @property
    def zone(self) -> ZoneInfo:
        return ZoneInfo(self.tz)

    def local_time(self) -> time | None:
        if not self.clock:
            return None
        hh, mm = self.clock.split(":")
        return time(int(hh), int(mm), tzinfo=self.zone)

    def next_occurrences(self, after: date, count: int = 3) -> list[datetime] | str:
        """Rule-derived upcoming datetimes, or a string explaining why not.

        Never guesses a date for an agency-scheduled release.
        """
        if self.recurrence in (Recurrence.AGENCY_SCHEDULE, Recurrence.EVENT_DRIVEN):
            return (
                f"UNKNOWN - {self.label} dates are set by {self.agency}'s published "
                f"schedule, not by a rule. Ingest the official calendar."
            )
        t = self.local_time()
        if t is None:
            return f"UNKNOWN - {self.label} has no fixed publication time."
        out: list[datetime] = []
        d = after
        guard = 0
        while len(out) < count and guard < 800:
            guard += 1
            d += timedelta(days=1)
            if self._matches(d):
                out.append(datetime.combine(d, t))
        return out

    def _matches(self, d: date) -> bool:
        if self.recurrence is Recurrence.WEEKLY:
            return d.weekday() == self.weekday
        if self.recurrence is Recurrence.NTH_WEEKDAY:
            if d.weekday() != self.weekday:
                return False
            return ((d.day - 1) // 7) + 1 == self.ordinal
        if self.recurrence is Recurrence.LAST_WEEKDAY:
            if d.weekday() != self.weekday:
                return False
            last = _cal.monthrange(d.year, d.month)[1]
            return d.day + 7 > last
        if self.recurrence is Recurrence.NTH_BUSINESS_DAY:
            # Weekday-only business days; public holidays are NOT modelled, so
            # a holiday in the first days of a month shifts the true date.
            n = 0
            for day in range(1, d.day + 1):
                if date(d.year, d.month, day).weekday() < 5:
                    n += 1
            return d.weekday() < 5 and n == self.ordinal
        return False


def _ind(code, label, country, unit, strength, infl=0, agency="", rev=False) -> IndicatorSpec:
    return IndicatorSpec(code, label, country, unit, strength, infl, agency, rev)


US = "United States"
EZ = "Euro Area"
UK = "United Kingdom"
JP = "Japan"
CN = "China"

_BLS = "https://www.bls.gov/schedule/news_release/"
_BEA = "https://www.bea.gov/news/schedule"
_CENSUS = "https://www.census.gov/economic-indicators/"
_FED = "https://www.federalreserve.gov/newsevents/calendar.htm"
_ECB = "https://www.ecb.europa.eu/press/calendars/mgcgc/html/index.en.html"
_BOE = "https://www.bankofengland.co.uk/news/calendar"
_BOJ = "https://www.boj.or.jp/en/mopo/mpmsche_minu/index.htm"
_NBS = "https://www.stats.gov.cn/english/"

RELEASES: tuple[Release, ...] = (
    # ---------------- United States: inflation -----------------------------
    Release("US_CPI", "US CPI (headline & core)", US, "BLS", EventClass.SCHEDULED_STATISTIC,
            "America/New_York", "08:30", Recurrence.AGENCY_SCHEDULE, tier_impact=1,
            indicator=_ind("US_CPI_YOY", "US CPI y/y", US, "pct_yoy", 0, 1, "BLS"),
            confidence=0.95, verify=_BLS,
            notes="Locked-file embargo; core is the number the rates market trades."),
    Release("US_CORE_CPI", "US Core CPI m/m", US, "BLS", EventClass.SCHEDULED_STATISTIC,
            "America/New_York", "08:30", Recurrence.AGENCY_SCHEDULE, tier_impact=1,
            indicator=_ind("US_CORE_CPI_MOM", "US Core CPI m/m", US, "pct_mom", 0, 1, "BLS"),
            confidence=0.95, verify=_BLS),
    Release("US_PPI", "US PPI", US, "BLS", EventClass.SCHEDULED_STATISTIC,
            "America/New_York", "08:30", Recurrence.AGENCY_SCHEDULE, tier_impact=2,
            indicator=_ind("US_PPI_MOM", "US PPI m/m", US, "pct_mom", 0, 1, "BLS"),
            confidence=0.9, verify=_BLS,
            notes="Matters mainly for its PCE-component read-through."),
    Release("US_PCE", "US PCE / Core PCE (Personal Income & Outlays)", US, "BEA",
            EventClass.SCHEDULED_STATISTIC, "America/New_York", "08:30",
            Recurrence.AGENCY_SCHEDULE, tier_impact=1,
            indicator=_ind("US_CORE_PCE_YOY", "US Core PCE y/y", US, "pct_yoy", 0, 1, "BEA", True),
            confidence=0.92, verify=_BEA,
            notes="The Fed's target gauge; often pre-computed from CPI+PPI, so the "
                  "surprise is usually smaller than CPI's."),
    # ---------------- United States: labour --------------------------------
    Release("US_NFP", "US Employment Situation (NFP, U3, AHE)", US, "BLS",
            EventClass.SCHEDULED_STATISTIC, "America/New_York", "08:30",
            Recurrence.NTH_WEEKDAY, weekday=4, ordinal=1, tier_impact=1,
            indicator=_ind("US_NFP", "US Nonfarm Payrolls", US, "k_jobs", 1, 0, "BLS", True),
            confidence=0.88, verify=_BLS,
            notes="First Friday is the convention, not a guarantee; BLS shifts it "
                  "around holidays and the annual benchmark. Revisions to the prior "
                  "two months routinely outweigh the headline."),
    Release("US_UNEMP", "US Unemployment Rate", US, "BLS", EventClass.SCHEDULED_STATISTIC,
            "America/New_York", "08:30", Recurrence.NTH_WEEKDAY, weekday=4, ordinal=1,
            tier_impact=1,
            indicator=_ind("US_U3", "US Unemployment Rate", US, "pct", -1, 0, "BLS"),
            confidence=0.88, verify=_BLS,
            notes="Household survey; higher print = weaker economy (strength_sign -1)."),
    Release("US_AHE", "US Average Hourly Earnings", US, "BLS", EventClass.SCHEDULED_STATISTIC,
            "America/New_York", "08:30", Recurrence.NTH_WEEKDAY, weekday=4, ordinal=1,
            tier_impact=2,
            indicator=_ind("US_AHE_MOM", "US Avg Hourly Earnings m/m", US, "pct_mom", 1, 1, "BLS"),
            confidence=0.88, verify=_BLS,
            notes="Both growth- and inflation-signed: impulse is MIXED by construction."),
    Release("US_CLAIMS", "US Initial Jobless Claims", US, "DOL/ETA",
            EventClass.SCHEDULED_STATISTIC, "America/New_York", "08:30",
            Recurrence.WEEKLY, weekday=3, tier_impact=2,
            indicator=_ind("US_IC", "US Initial Claims", US, "k_claims", -1, 0, "DOL"),
            confidence=0.93, verify="https://www.dol.gov/ui/data.pdf",
            notes="Highest-frequency labour signal; matters most at inflection points. "
                  "Holiday weeks distort the seasonal factors."),
    Release("US_CONT_CLAIMS", "US Continuing Claims", US, "DOL/ETA",
            EventClass.SCHEDULED_STATISTIC, "America/New_York", "08:30",
            Recurrence.WEEKLY, weekday=3, tier_impact=3,
            indicator=_ind("US_CC", "US Continuing Claims", US, "k_claims", -1, 0, "DOL"),
            confidence=0.93, verify="https://www.dol.gov/ui/data.pdf",
            notes="Reported one week in arrears of initial claims."),
    Release("US_JOLTS", "US JOLTS Job Openings", US, "BLS", EventClass.SCHEDULED_STATISTIC,
            "America/New_York", "10:00", Recurrence.AGENCY_SCHEDULE, tier_impact=3,
            indicator=_ind("US_JOLTS", "US Job Openings", US, "mn_jobs", 1, 0, "BLS", True),
            confidence=0.85, verify=_BLS, notes="Stale by ~2 months; low response rate."),
    # ---------------- United States: activity ------------------------------
    Release("US_ISM_MFG", "US ISM Manufacturing PMI", US, "ISM",
            EventClass.SCHEDULED_STATISTIC, "America/New_York", "10:00",
            Recurrence.NTH_BUSINESS_DAY, ordinal=1, tier_impact=2,
            indicator=_ind("US_ISM_M", "US ISM Manufacturing", US, "index", 1, 0, "ISM"),
            confidence=0.75, verify="https://www.ismworld.org/",
            notes="First business day is the convention; holidays shift it and this "
                  "module does not model holidays."),
    Release("US_ISM_SVC", "US ISM Services PMI", US, "ISM", EventClass.SCHEDULED_STATISTIC,
            "America/New_York", "10:00", Recurrence.NTH_BUSINESS_DAY, ordinal=3,
            tier_impact=2,
            indicator=_ind("US_ISM_S", "US ISM Services", US, "index", 1, 0, "ISM"),
            confidence=0.72, verify="https://www.ismworld.org/",
            notes="Services is the larger share of the economy; the prices-paid "
                  "sub-index frequently moves rates more than the headline."),
    Release("US_PMI_FLASH", "US S&P Global Flash PMI", US, "S&P Global",
            EventClass.SCHEDULED_STATISTIC, "America/New_York", "09:45",
            Recurrence.AGENCY_SCHEDULE, tier_impact=3,
            indicator=_ind("US_PMI_C", "US Composite PMI", US, "index", 1, 0, "S&P Global"),
            confidence=0.7, verify="https://www.pmi.spglobal.com/"),
    Release("US_RETAIL", "US Retail Sales", US, "Census", EventClass.SCHEDULED_STATISTIC,
            "America/New_York", "08:30", Recurrence.AGENCY_SCHEDULE, tier_impact=2,
            indicator=_ind("US_RS_MOM", "US Retail Sales m/m", US, "pct_mom", 1, 0, "Census", True),
            confidence=0.9, verify=_CENSUS,
            notes="Nominal, not real: a hot print partly reflects prices. The control "
                  "group is the GDP-relevant cut."),
    Release("US_GDP", "US GDP (adv/2nd/3rd)", US, "BEA", EventClass.SCHEDULED_STATISTIC,
            "America/New_York", "08:30", Recurrence.AGENCY_SCHEDULE, tier_impact=2,
            indicator=_ind("US_GDP_QOQ", "US GDP q/q saar", US, "pct_qoq_saar", 1, 0, "BEA", True),
            confidence=0.9, verify=_BEA, notes="Backward-looking; the deflator can matter more."),
    Release("US_DURABLES", "US Durable Goods Orders", US, "Census",
            EventClass.SCHEDULED_STATISTIC, "America/New_York", "08:30",
            Recurrence.AGENCY_SCHEDULE, tier_impact=3,
            indicator=_ind("US_DG_MOM", "US Durable Goods m/m", US, "pct_mom", 1, 0, "Census", True),
            confidence=0.85, verify=_CENSUS, notes="Aircraft orders dominate the headline."),
    Release("US_IP", "US Industrial Production", US, "Federal Reserve",
            EventClass.SCHEDULED_STATISTIC, "America/New_York", "09:15",
            Recurrence.AGENCY_SCHEDULE, tier_impact=3,
            indicator=_ind("US_IP_MOM", "US Industrial Production m/m", US, "pct_mom", 1, 0, "FRB"),
            confidence=0.8, verify=_FED),
    Release("US_CONF", "US Consumer Confidence (Conference Board)", US, "Conference Board",
            EventClass.SCHEDULED_STATISTIC, "America/New_York", "10:00",
            Recurrence.LAST_WEEKDAY, weekday=1, tier_impact=3,
            indicator=_ind("US_CB_CONF", "US Consumer Confidence", US, "index", 1, 0, "CB"),
            confidence=0.7, verify="https://www.conference-board.org/",
            notes="Last Tuesday is the usual pattern; verify each month."),
    Release("US_HOUSING", "US Housing (starts, permits, existing/new sales)", US,
            "Census / NAR", EventClass.SCHEDULED_STATISTIC, "America/New_York", "08:30",
            Recurrence.AGENCY_SCHEDULE, tier_impact=3, confidence=0.7, verify=_CENSUS,
            notes="Existing home sales publish at 10:00 ET; starts/permits at 08:30 ET."),
    Release("US_TRADE", "US Trade Balance", US, "Census/BEA", EventClass.SCHEDULED_STATISTIC,
            "America/New_York", "08:30", Recurrence.AGENCY_SCHEDULE, tier_impact=3,
            indicator=_ind("US_TB", "US Trade Balance", US, "usd_bn", 1, 0, "Census"),
            confidence=0.85, verify=_CENSUS),
    # ---------------- United States: policy & supply -----------------------
    Release("FOMC_DECISION", "FOMC rate decision & statement", US, "Federal Reserve",
            EventClass.SCHEDULED_POLICY, "America/New_York", "14:00",
            Recurrence.AGENCY_SCHEDULE, tier_impact=1, confidence=0.93, verify=_FED,
            notes="Eight scheduled meetings a year. Quarterly meetings also carry the "
                  "SEP/dot plot, which frequently moves the curve more than the "
                  "statement itself."),
    Release("FOMC_PRESSER", "FOMC Chair press conference", US, "Federal Reserve",
            EventClass.PRESS_CONFERENCE, "America/New_York", "14:30",
            Recurrence.AGENCY_SCHEDULE, tier_impact=1, confidence=0.9, verify=_FED,
            notes="30 minutes after the statement. The Q&A, not the prepared remarks, "
                  "is where guidance shifts."),
    Release("FOMC_MINUTES", "FOMC minutes", US, "Federal Reserve", EventClass.POLICY_MINUTES,
            "America/New_York", "14:00", Recurrence.AGENCY_SCHEDULE, tier_impact=2,
            confidence=0.9, verify=_FED,
            notes="Published three weeks after the meeting; stale unless the meeting "
                  "was close and the data since has been ambiguous."),
    Release("FED_BEIGE", "Fed Beige Book", US, "Federal Reserve", EventClass.POLICY_MINUTES,
            "America/New_York", "14:00", Recurrence.AGENCY_SCHEDULE, tier_impact=3,
            confidence=0.85, verify=_FED, notes="Two weeks before each FOMC meeting."),
    Release("US_AUCTION", "US Treasury auctions (2y/5y/7y/10y/20y/30y)", US, "US Treasury",
            EventClass.AUCTION, "America/New_York", "13:00", Recurrence.AGENCY_SCHEDULE,
            tier_impact=2, confidence=0.85,
            verify="https://www.treasurydirect.gov/auctions/upcoming/",
            notes="Coupon auctions bid at 13:00 ET. Watch the tail vs when-issued, "
                  "bid-to-cover and indirect take-down, not the stop alone."),
    Release("FED_SPEECH", "Fed officials' speeches & testimony", US, "Federal Reserve",
            EventClass.OFFICIAL_SPEECH, "America/New_York", None, Recurrence.AGENCY_SCHEDULE,
            tier_impact=2, confidence=0.95, verify=_FED,
            notes="Voting status and the blackout window decide whether it matters."),
    # ---------------- Euro area --------------------------------------------
    Release("ECB_DECISION", "ECB monetary policy decision", EZ, "ECB",
            EventClass.SCHEDULED_POLICY, "Europe/Berlin", "14:15",
            Recurrence.AGENCY_SCHEDULE, tier_impact=1, confidence=0.85, verify=_ECB,
            notes="Decision 14:15 CET, press conference 14:45 CET since the 2022 "
                  "timing change. Verify per meeting."),
    Release("ECB_PRESSER", "ECB press conference", EZ, "ECB", EventClass.PRESS_CONFERENCE,
            "Europe/Berlin", "14:45", Recurrence.AGENCY_SCHEDULE, tier_impact=1,
            confidence=0.85, verify=_ECB),
    Release("ECB_ACCOUNTS", "ECB monetary policy accounts", EZ, "ECB",
            EventClass.POLICY_MINUTES, "Europe/Berlin", "13:30",
            Recurrence.AGENCY_SCHEDULE, tier_impact=3, confidence=0.7, verify=_ECB),
    Release("EZ_CPI", "Euro area HICP (flash & final)", EZ, "Eurostat",
            EventClass.SCHEDULED_STATISTIC, "Europe/Brussels", "11:00",
            Recurrence.AGENCY_SCHEDULE, tier_impact=1,
            indicator=_ind("EZ_HICP_YOY", "Euro area HICP y/y", EZ, "pct_yoy", 0, 1, "Eurostat"),
            confidence=0.85, verify="https://ec.europa.eu/eurostat/news/release-calendar",
            notes="German, French, Spanish and Italian national prints land first and "
                  "largely determine the aggregate: the euro-area flash is often "
                  "already priced by the time it prints."),
    Release("EZ_GDP", "Euro area GDP", EZ, "Eurostat", EventClass.SCHEDULED_STATISTIC,
            "Europe/Brussels", "11:00", Recurrence.AGENCY_SCHEDULE, tier_impact=2,
            indicator=_ind("EZ_GDP_QOQ", "Euro area GDP q/q", EZ, "pct_qoq", 1, 0, "Eurostat", True),
            confidence=0.8, verify="https://ec.europa.eu/eurostat/news/release-calendar"),
    Release("EZ_PMI", "Euro area flash PMIs", EZ, "S&P Global/HCOB",
            EventClass.SCHEDULED_STATISTIC, "Europe/Brussels", "10:00",
            Recurrence.AGENCY_SCHEDULE, tier_impact=2,
            indicator=_ind("EZ_PMI_C", "Euro area Composite PMI", EZ, "index", 1, 0, "HCOB"),
            confidence=0.75, verify="https://www.pmi.spglobal.com/",
            notes="France ~09:15, Germany ~09:30, euro area ~10:00 CET."),
    Release("DE_CPI", "German CPI (flash)", "Germany", "Destatis",
            EventClass.SCHEDULED_STATISTIC, "Europe/Berlin", "14:00",
            Recurrence.AGENCY_SCHEDULE, tier_impact=2,
            indicator=_ind("DE_CPI_YOY", "German CPI y/y", "Germany", "pct_yoy", 0, 1, "Destatis"),
            confidence=0.7, verify="https://www.destatis.de/EN/Press/",
            notes="State-level prints leak the national number through the morning."),
    Release("DE_ZEW", "German ZEW expectations", "Germany", "ZEW",
            EventClass.SCHEDULED_STATISTIC, "Europe/Berlin", "11:00",
            Recurrence.AGENCY_SCHEDULE, tier_impact=3,
            indicator=_ind("DE_ZEW", "ZEW Expectations", "Germany", "index", 1, 0, "ZEW"),
            confidence=0.75, verify="https://www.zew.de/en/"),
    Release("DE_IFO", "German ifo business climate", "Germany", "ifo",
            EventClass.SCHEDULED_STATISTIC, "Europe/Berlin", "10:00",
            Recurrence.AGENCY_SCHEDULE, tier_impact=3,
            indicator=_ind("DE_IFO", "ifo Business Climate", "Germany", "index", 1, 0, "ifo"),
            confidence=0.75, verify="https://www.ifo.de/en"),
    # ---------------- United Kingdom ---------------------------------------
    Release("BOE_DECISION", "Bank of England MPC decision", UK, "Bank of England",
            EventClass.SCHEDULED_POLICY, "Europe/London", "12:00",
            Recurrence.AGENCY_SCHEDULE, tier_impact=1, confidence=0.88, verify=_BOE,
            notes="Announcement at 12:00 London. The vote split is the signal; a "
                  "unanimous hold and a 5-4 hold are different trades."),
    Release("UK_CPI", "UK CPI", UK, "ONS", EventClass.SCHEDULED_STATISTIC,
            "Europe/London", "07:00", Recurrence.AGENCY_SCHEDULE, tier_impact=1,
            indicator=_ind("UK_CPI_YOY", "UK CPI y/y", UK, "pct_yoy", 0, 1, "ONS"),
            confidence=0.9, verify="https://www.ons.gov.uk/releasecalendar",
            notes="ONS publishes at 07:00 London. Services CPI is the BoE's focus."),
    Release("UK_LABOUR", "UK labour market & wage growth", UK, "ONS",
            EventClass.SCHEDULED_STATISTIC, "Europe/London", "07:00",
            Recurrence.AGENCY_SCHEDULE, tier_impact=2,
            indicator=_ind("UK_AWE", "UK Avg Weekly Earnings y/y", UK, "pct_yoy", 1, 1, "ONS", True),
            confidence=0.9, verify="https://www.ons.gov.uk/releasecalendar",
            notes="LFS response rates are impaired; the BoE discounts the unemployment rate."),
    Release("UK_GDP", "UK GDP (monthly & quarterly)", UK, "ONS",
            EventClass.SCHEDULED_STATISTIC, "Europe/London", "07:00",
            Recurrence.AGENCY_SCHEDULE, tier_impact=3,
            indicator=_ind("UK_GDP_MOM", "UK GDP m/m", UK, "pct_mom", 1, 0, "ONS", True),
            confidence=0.9, verify="https://www.ons.gov.uk/releasecalendar"),
    Release("UK_FISCAL", "UK fiscal events (Budget / Statement)", UK, "HM Treasury",
            EventClass.GOVERNMENT_ANNOUNCEMENT, "Europe/London", "12:30",
            Recurrence.AGENCY_SCHEDULE, tier_impact=1, confidence=0.6,
            verify="https://www.gov.uk/government/organisations/hm-treasury",
            notes="Gilt remit and OBR forecast alongside the statement are what the "
                  "long end actually trades."),
    # ---------------- Japan --------------------------------------------------
    Release("BOJ_DECISION", "Bank of Japan policy decision", JP, "Bank of Japan",
            EventClass.SCHEDULED_POLICY, "Asia/Tokyo", None, Recurrence.AGENCY_SCHEDULE,
            tier_impact=1, confidence=0.95, verify=_BOJ,
            notes="No fixed announcement time - the release lands somewhere in the "
                  "late Tokyo morning/early afternoon. That uncertainty is itself a "
                  "volatility source in USDJPY and JGBs."),
    Release("JP_CPI", "Japan National CPI", JP, "Statistics Bureau",
            EventClass.SCHEDULED_STATISTIC, "Asia/Tokyo", "08:30",
            Recurrence.AGENCY_SCHEDULE, tier_impact=2,
            indicator=_ind("JP_CPI_YOY", "Japan Core CPI y/y", JP, "pct_yoy", 0, 1, "SBJ"),
            confidence=0.8, verify="https://www.stat.go.jp/english/"),
    Release("JP_WAGES", "Japan labour cash earnings / shunto", JP, "MHLW",
            EventClass.SCHEDULED_STATISTIC, "Asia/Tokyo", "08:30",
            Recurrence.AGENCY_SCHEDULE, tier_impact=2,
            indicator=_ind("JP_WAGE", "Japan Cash Earnings y/y", JP, "pct_yoy", 1, 1, "MHLW", True),
            confidence=0.7, verify="https://www.mhlw.go.jp/english/",
            notes="Wage momentum is the BoJ's stated condition for sustained inflation."),
    Release("JP_TANKAN", "BoJ Tankan survey", JP, "Bank of Japan",
            EventClass.SCHEDULED_STATISTIC, "Asia/Tokyo", "08:50",
            Recurrence.AGENCY_SCHEDULE, tier_impact=3,
            indicator=_ind("JP_TANKAN", "Tankan Large Mfg DI", JP, "index", 1, 0, "BoJ"),
            confidence=0.75, verify=_BOJ),
    Release("JP_INTERVENTION", "MoF/BoJ FX intervention", JP, "Ministry of Finance",
            EventClass.INTERVENTION, "Asia/Tokyo", None, Recurrence.EVENT_DRIVEN,
            tier_impact=1, confidence=0.95,
            verify="https://www.mof.go.jp/english/policy/international_policy/",
            notes="Unscheduled by nature. Verbal escalation ladder (watching closely -> "
                  "with a sense of urgency -> will not rule out any options) precedes "
                  "action; monthly intervention totals confirm it after the fact."),
    # ---------------- China --------------------------------------------------
    Release("PBOC_LPR", "PBoC Loan Prime Rate fixing", CN, "PBoC",
            EventClass.SCHEDULED_POLICY, "Asia/Shanghai", "09:15",
            Recurrence.AGENCY_SCHEDULE, tier_impact=2, confidence=0.75,
            verify="http://www.pbc.gov.cn/en/", notes="Around the 20th of each month."),
    Release("CN_ACTIVITY", "China activity data (IP, retail sales, FAI)", CN, "NBS",
            EventClass.SCHEDULED_STATISTIC, "Asia/Shanghai", "10:00",
            Recurrence.AGENCY_SCHEDULE, tier_impact=2,
            indicator=_ind("CN_RETAIL", "China Retail Sales y/y", CN, "pct_yoy", 1, 0, "NBS"),
            confidence=0.8, verify=_NBS),
    Release("CN_GDP", "China GDP", CN, "NBS", EventClass.SCHEDULED_STATISTIC,
            "Asia/Shanghai", "10:00", Recurrence.AGENCY_SCHEDULE, tier_impact=2,
            indicator=_ind("CN_GDP_YOY", "China GDP y/y", CN, "pct_yoy", 1, 0, "NBS"),
            confidence=0.8, verify=_NBS),
    Release("CN_CPI", "China CPI / PPI", CN, "NBS", EventClass.SCHEDULED_STATISTIC,
            "Asia/Shanghai", "09:30", Recurrence.AGENCY_SCHEDULE, tier_impact=3,
            indicator=_ind("CN_CPI_YOY", "China CPI y/y", CN, "pct_yoy", 0, 1, "NBS"),
            confidence=0.75, verify=_NBS,
            notes="Deflation risk here is a global goods-disinflation channel."),
    Release("CN_PMI", "China NBS & Caixin PMIs", CN, "NBS / Caixin",
            EventClass.SCHEDULED_STATISTIC, "Asia/Shanghai", "09:30",
            Recurrence.AGENCY_SCHEDULE, tier_impact=2,
            indicator=_ind("CN_PMI_M", "China Mfg PMI", CN, "index", 1, 0, "NBS"),
            confidence=0.75, verify=_NBS,
            notes="NBS 09:30 Beijing (last day of month); Caixin 09:45 the next business day."),
    Release("CN_CREDIT", "China aggregate financing / new loans", CN, "PBoC",
            EventClass.SCHEDULED_STATISTIC, "Asia/Shanghai", None,
            Recurrence.AGENCY_SCHEDULE, tier_impact=2,
            indicator=_ind("CN_TSF", "China Total Social Financing", CN, "cny_bn", 1, 0, "PBoC"),
            confidence=0.6, verify="http://www.pbc.gov.cn/en/",
            notes="Released without a fixed time, usually between the 9th and 15th. "
                  "The cleanest read on Chinese credit impulse and therefore on "
                  "global commodity demand."),
    Release("CN_TRADE", "China trade data", CN, "GACC", EventClass.SCHEDULED_STATISTIC,
            "Asia/Shanghai", "11:00", Recurrence.AGENCY_SCHEDULE, tier_impact=3,
            confidence=0.6, verify="http://english.customs.gov.cn/"),
    # ---------------- Other DM / commodities --------------------------------
    Release("BOC_DECISION", "Bank of Canada decision", "Canada", "Bank of Canada",
            EventClass.SCHEDULED_POLICY, "America/Toronto", "09:45",
            Recurrence.AGENCY_SCHEDULE, tier_impact=2, confidence=0.85,
            verify="https://www.bankofcanada.ca/"),
    Release("RBA_DECISION", "Reserve Bank of Australia decision", "Australia", "RBA",
            EventClass.SCHEDULED_POLICY, "Australia/Sydney", "14:30",
            Recurrence.AGENCY_SCHEDULE, tier_impact=2, confidence=0.8,
            verify="https://www.rba.gov.au/"),
    Release("RBNZ_DECISION", "RBNZ decision", "New Zealand", "RBNZ",
            EventClass.SCHEDULED_POLICY, "Pacific/Auckland", "14:00",
            Recurrence.AGENCY_SCHEDULE, tier_impact=3, confidence=0.8,
            verify="https://www.rbnz.govt.nz/"),
    Release("SNB_DECISION", "Swiss National Bank assessment", "Switzerland", "SNB",
            EventClass.SCHEDULED_POLICY, "Europe/Zurich", "09:30",
            Recurrence.AGENCY_SCHEDULE, tier_impact=2, confidence=0.8,
            verify="https://www.snb.ch/en/",
            notes="Quarterly. Low frequency and a history of surprises makes each one "
                  "a fat-tail CHF event."),
    Release("EIA_CRUDE", "EIA weekly petroleum status", US, "EIA",
            EventClass.SCHEDULED_STATISTIC, "America/New_York", "10:30",
            Recurrence.WEEKLY, weekday=2, tier_impact=3,
            indicator=_ind("US_EIA_CRUDE", "EIA Crude Inventories", US, "mn_bbl", -1, 0, "EIA"),
            confidence=0.85, verify="https://www.eia.gov/petroleum/supply/weekly/",
            notes="Wednesday 10:30 ET, slipping to Thursday after a Monday holiday. "
                  "A build is bearish crude, hence strength_sign -1."),
    Release("OPEC_MEETING", "OPEC+ ministerial / JMMC", "OPEC+", "OPEC",
            EventClass.GOVERNMENT_ANNOUNCEMENT, "Europe/Vienna", None,
            Recurrence.AGENCY_SCHEDULE, tier_impact=1, confidence=0.9,
            verify="https://www.opec.org/opec_web/en/",
            notes="Outcome frequently leaks to wires through delegates before the "
                  "communique. Treat delegate reports as Tier 2 UNCONFIRMED until the "
                  "communique publishes."),
)

BY_CODE = {r.code: r for r in RELEASES}
INDICATORS = {r.indicator.code: r.indicator for r in RELEASES if r.indicator}


def _validate() -> None:
    """Fail loudly at import if the table is internally inconsistent.

    A mistyped or non-canonical IANA zone (``Europe/Frankfurt`` is an alias, not
    a zone) would otherwise surface as a wrong release time under load, which is
    exactly when nobody is checking.
    """
    seen: set[str] = set()
    for r in RELEASES:
        if r.code in seen:
            raise ValueError(f"duplicate release code: {r.code}")
        seen.add(r.code)
        try:
            r.zone
        except Exception as exc:  # noqa: BLE001
            raise ValueError(f"{r.code}: unresolvable timezone '{r.tz}': {exc}") from exc
        if r.clock:
            hh, _, mm = r.clock.partition(":")
            if not (hh.isdigit() and mm.isdigit() and 0 <= int(hh) < 24 and 0 <= int(mm) < 60):
                raise ValueError(f"{r.code}: malformed clock '{r.clock}'")
        if r.recurrence is Recurrence.NTH_WEEKDAY and (r.weekday is None or r.ordinal is None):
            raise ValueError(f"{r.code}: NTH_WEEKDAY needs both weekday and ordinal")
        if r.recurrence is Recurrence.WEEKLY and r.weekday is None:
            raise ValueError(f"{r.code}: WEEKLY needs a weekday")
        if r.recurrence in (Recurrence.NTH_BUSINESS_DAY, Recurrence.LAST_WEEKDAY) \
                and r.ordinal is None and r.weekday is None:
            raise ValueError(f"{r.code}: {r.recurrence.value} needs an ordinal or weekday")


_validate()


def by_country(country: str) -> list[Release]:
    return [r for r in RELEASES if r.country.lower() == country.lower()]


def top_tier() -> list[Release]:
    return [r for r in RELEASES if r.tier_impact == 1]


def coverage_report() -> dict[str, int]:
    out: dict[str, int] = {}
    for r in RELEASES:
        out[r.country] = out.get(r.country, 0) + 1
    return dict(sorted(out.items(), key=lambda kv: -kv[1]))


__all__ = [
    "BY_CODE", "INDICATORS", "RELEASES", "Recurrence", "Release", "by_country",
    "coverage_report", "top_tier",
]
