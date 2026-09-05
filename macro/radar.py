"""The radar itself: event book, ranking, and the command surface (spec 29).

Every command answers the operating question from spec section 30 - what is
changing expectations, what is already priced, who is exposed - rather than
"what news is happening".
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from . import brief as brief_mod
from . import preevent
from .calendar_spec import BY_CODE, INDICATORS, RELEASES, Release
from .centralbank import speech_radar
from .events import MacroEvent, render_alert
from .liquidity import detect_anomaly
from .reaction import analyse_orders, build_matrix
from .regime import MacroRegime, RiskRegime
from .scoring import EventClass, LATENCY_NOTE, UrgencyBand
from .setups import NoTrade, Setup
from .state import MarketState
from .structure import StructureRead
from .surprise import Impulse
from .types import iso, utcnow

COMMANDS = (
    "RADAR", "NEXT", "SPEECHES", "FED", "ECB", "CPI", "NFP", "RISK", "LIQUIDITY",
    "MARKET", "SETUP", "ALERT", "PRE-EVENT", "WHAT MATTERS",
)

RULE = "=" * 78
THIN = "-" * 78


@dataclass
class Radar:
    state: MarketState = field(default_factory=MarketState)
    events: list[MacroEvent] = field(default_factory=list)
    setups: list[Setup | NoTrade] = field(default_factory=list)
    structures: dict[str, StructureRead] = field(default_factory=dict)
    overnight: list[str] = field(default_factory=list)
    geopolitical: list[str] = field(default_factory=list)

    # ---------------------------------------------------------------- book
    def add(self, event: MacroEvent) -> MacroEvent:
        self.events.append(event)
        return event

    def ranked(self, minimum: float = 0.0) -> list[MacroEvent]:
        keep = [
            e for e in self.events
            if e.effective_priority >= minimum and (e.noise is None or e.noise.keep)
        ]
        return sorted(keep, key=lambda e: -e.effective_priority)

    def suppressed(self) -> list[MacroEvent]:
        return [e for e in self.events if e.noise is not None and not e.noise.keep]

    # ------------------------------------------------------------ commands
    def dispatch(self, command: str, *, arg: str | None = None) -> str:
        c = command.strip().upper().replace("_", " ")
        table = {
            "RADAR": self.cmd_radar,
            "NEXT": self.cmd_next,
            "SPEECHES": self.cmd_speeches,
            "FED": lambda: self.cmd_bank("Federal Reserve", "United States"),
            "ECB": lambda: self.cmd_bank("ECB", "Euro Area"),
            "CPI": lambda: self.cmd_event_map("US_CPI"),
            "NFP": lambda: self.cmd_event_map("US_NFP"),
            "RISK": self.cmd_risk,
            "LIQUIDITY": self.cmd_liquidity,
            "MARKET": self.cmd_market,
            "SETUP": self.cmd_setup,
            "ALERT": self.cmd_alert,
            "PRE-EVENT": lambda: self.cmd_preevent(arg),
            "PREEVENT": lambda: self.cmd_preevent(arg),
            "WHAT MATTERS": self.cmd_what_matters,
            "WHAT MATTERS?": self.cmd_what_matters,
        }
        fn = table.get(c)
        if fn is None:
            return (
                f"UNKNOWN COMMAND '{command}'. Available: " + ", ".join(COMMANDS)
            )
        return fn()

    # --------------------------------------------------------------- RADAR
    def cmd_radar(self) -> str:
        ranked = self.ranked()
        lines = [RULE, "MACRO RADAR - HIGHEST-PRIORITY CURRENT DEVELOPMENTS", RULE]
        if not ranked:
            lines.append("  No events in the book. The radar reports an empty book "
                         "rather than manufacturing headlines.")
        for e in ranked[:12]:
            lines.append("  " + e.one_line())
            lines.append(f"        {e.confirmation.label} | credibility "
                         f"{e.confirmation.credibility_score:.0f} | "
                         f"latency {e.scores.information_latency:.0f}")
            if e.confirmation.misinformation_flags:
                lines.append(f"        ! {e.confirmation.misinformation_flags[0]}")
        sup = self.suppressed()
        if sup:
            lines.append(THIN)
            lines.append(f"  {len(sup)} item(s) suppressed by the noise filter:")
            for e in sup[:5]:
                lines.append(f"    - {e.title}  [{e.noise.reasons[0] if e.noise else ''}]")
        lines.append(RULE)
        lines.append(f"  {LATENCY_NOTE}")
        return "\n".join(lines)

    # ---------------------------------------------------------------- NEXT
    def cmd_next(self, horizon_days: int = 7) -> str:
        today = utcnow().date()
        rows: list[tuple[datetime, str]] = []
        unscheduled: list[str] = []
        for r in RELEASES:
            nxt = r.next_occurrences(today, 2)
            if isinstance(nxt, str):
                unscheduled.append(f"{r.label} ({r.agency})")
                continue
            for dt in nxt:
                if (dt.date() - today).days <= horizon_days:
                    rows.append((dt, f"{r.label} - {r.agency} "
                                     f"[impact tier {r.tier_impact}, conf {r.confidence:.2f}]"))
        rows.sort(key=lambda x: x[0])
        lines = [RULE, f"NEXT MARKET-MOVING EVENTS - RULE-DERIVABLE, {horizon_days}d HORIZON", RULE]
        for dt, label in rows:
            lines.append(f"  {dt:%Y-%m-%d %H:%M %Z}  {label}")
        if not rows:
            lines.append("  No rule-derivable releases inside the horizon.")
        lines.append(THIN)
        lines.append(f"  {len(unscheduled)} release(s) follow a published agency schedule "
                     "and cannot be derived. Their dates must be ingested, not guessed:")
        for u in unscheduled[:14]:
            lines.append(f"    - {u}")
        if len(unscheduled) > 14:
            lines.append(f"    ... and {len(unscheduled) - 14} more")
        lines.append(RULE)
        return "\n".join(lines)

    # ------------------------------------------------------------- SPEECHES
    def cmd_speeches(self) -> str:
        lines = [RULE, "PUBLIC SPEECH RADAR", RULE]
        speech_events = [
            e for e in self.ranked()
            if e.event_class in (EventClass.OFFICIAL_SPEECH, EventClass.PRESS_CONFERENCE)
        ]
        if speech_events:
            for e in speech_events:
                lines.append("  " + e.one_line())
                lines.append(f"        priced beforehand: {e.market_pricing_before}")
        else:
            lines.append("  No speeches loaded into the event book.")
        lines.append(THIN)
        lines.append("  Template trigger map (attach a real speaker to make it concrete):")
        sr = speech_radar("<speaker>", "<institution>", "<role>")
        for t in sr.hawkish_triggers[:3]:
            lines.append(f"    HAWKISH TRIGGER  {t}")
        for t in sr.dovish_triggers[:3]:
            lines.append(f"    DOVISH TRIGGER   {t}")
        lines.append(f"    NEUTRAL          {sr.neutral_scenario}")
        for c in sr.caveats:
            lines.append(f"    ! {c}")
        lines.append(RULE)
        return "\n".join(lines)

    # ------------------------------------------------------------ FED / ECB
    def cmd_bank(self, agency: str, country: str) -> str:
        lines = [RULE, f"{agency.upper()} - EXPECTATIONS DOSSIER", RULE]
        pricing = self.state.market_pricing.get(agency)
        lines.append("  WHAT IS PRICED")
        default_pricing = (
            "UNKNOWN - no OIS/futures-implied path supplied. This system does not "
            "assume a market-implied path."
        )
        lines.append(f"    {pricing or default_pricing}")
        lines.append("  SCHEDULED SURFACE")
        for r in RELEASES:
            if r.agency.lower().startswith(agency.lower()[:3]) or r.country == country:
                if r.event_class in (
                    EventClass.SCHEDULED_POLICY, EventClass.PRESS_CONFERENCE,
                    EventClass.POLICY_MINUTES, EventClass.OFFICIAL_SPEECH,
                ):
                    lines.append(
                        f"    {r.label:<44} {r.clock or 'no fixed time':>13} {r.tz}"
                    )
                    if r.notes:
                        lines.append(f"        {r.notes}")
        lines.append("  RELATED EVENTS IN THE BOOK")
        rel = [e for e in self.ranked() if e.country == country]
        for e in rel[:6]:
            lines.append("    " + e.one_line())
        if not rel:
            lines.append("    none")
        lines.append("  CURVE READ (the market's own answer on the policy path)")
        lines.append(f"    {self.state.curve().render()}")
        lines.append(RULE)
        return "\n".join(lines)

    # ------------------------------------------------------- CPI / NFP maps
    def cmd_event_map(self, code: str) -> str:
        r: Release | None = BY_CODE.get(code)
        if r is None:
            return f"UNKNOWN release code '{code}'"
        ind = r.indicator
        lines = [RULE, f"EVENT MAP - {r.label}", RULE]
        lines.append(f"  Agency        {r.agency}")
        lines.append(f"  Clock         {r.clock or 'no fixed time'} {r.tz} "
                     f"(confidence {r.confidence:.2f})")
        lines.append(f"  Recurrence    {r.recurrence.value}")
        nxt = r.next_occurrences(utcnow().date(), 3)
        lines.append("  Next          " + (
            ", ".join(f"{d:%Y-%m-%d %H:%M}" for d in nxt) if isinstance(nxt, list) else nxt
        ))
        lines.append(f"  Verify at     {r.verify}")
        if r.notes:
            lines.append(f"  Note          {r.notes}")
        lines.append(THIN)
        lines.append("  CONSENSUS / PREVIOUS / MARKET-IMPLIED")
        lines.append("    UNKNOWN - this system never generates forecast values. Supply "
                     "them and the surprise engine will standardise the result.")
        lines.append(THIN)

        if ind is None:
            lines.append("  No indicator semantics attached to this release.")
            lines.append(RULE)
            return "\n".join(lines)

        regime = self.state.regime
        if ind.inflation_sign != 0:
            up, dn = Impulse.INFLATION_HOTTER, Impulse.INFLATION_COOLER
        else:
            up, dn = Impulse.GROWTH_STRONGER, Impulse.GROWTH_WEAKER
        for imp in (up, dn):
            m = build_matrix(imp, regime, magnitude=1.6,
                             scenario_label=f"{r.label}: {imp.value}")
            lines.append(m.render())
            lines.append("")
        oa = analyse_orders(build_matrix(up, regime, magnitude=1.6))
        lines.append(oa.render())
        lines.append(THIN)
        lines.append(f"  Higher print = {'more inflationary' if ind.inflation_sign > 0 else 'n/a for inflation'}"
                     f", {'stronger economy' if ind.strength_sign > 0 else 'weaker economy' if ind.strength_sign < 0 else 'growth-neutral'}.")
        if ind.revision_prone:
            lines.append("  Revision-prone series: the revision to the prior print "
                         "regularly outweighs the headline surprise.")
        lines.append(RULE)
        return "\n".join(lines)

    # ---------------------------------------------------------------- RISK
    def cmd_risk(self) -> str:
        cond = self.state.conditions()
        lines = [RULE, "GLOBAL RISK REGIME", RULE]
        lines.append(f"  Macro regime  {self.state.regime.value}")
        lines.append(f"                {self.state.regime.explanation}")
        lines.append(f"  Basis         {self.state.regime_basis}")
        lines.append(f"  Conditions    {cond.render()}")
        if getattr(cond, "ok", False):
            for c in cond.caveats:      # type: ignore[union-attr]
                lines.append(f"    ! {c}")
            if cond.missing:            # type: ignore[union-attr]
                lines.append(f"    unobserved: {', '.join(cond.missing[:10])}")  # type: ignore[union-attr]
        lines.append(f"  Curve         {self.state.curve().render()}")
        hi = [e for e in self.ranked() if e.band in (UrgencyBand.EXTREME, UrgencyBand.HIGH)]
        lines.append(f"  Unresolved high/extreme catalysts: {len(hi)}")
        for e in hi[:5]:
            lines.append("    " + e.one_line())
        lines.append(RULE)
        return "\n".join(lines)

    # ----------------------------------------------------------- LIQUIDITY
    def cmd_liquidity(self) -> str:
        cond = self.state.conditions()
        lines = [RULE, "GLOBAL LIQUIDITY & FUNDING CONDITIONS", RULE, f"  {cond.render()}"]
        if getattr(cond, "ok", False):
            lines.append("  CONTRIBUTIONS")
            for name, contrib, why in cond.contributions:   # type: ignore[union-attr]
                lines.append(f"    {name:<24} {contrib:+.2f}  {why}")
            lines.append("  ALARMS")
            for a in (cond.alarms or ("none tripped",)):    # type: ignore[union-attr]
                lines.append(f"    {a}")
            lines.append("  NOT OBSERVED (assumed neither benign nor stressed)")
            lines.append("    " + ", ".join(cond.missing))  # type: ignore[union-attr]
        lines.append(RULE)
        return "\n".join(lines)

    # -------------------------------------------------------------- MARKET
    def cmd_market(self) -> str:
        b = brief_mod.build(self.state, self.events,
                            overnight=self.overnight, geopolitical=self.geopolitical)
        return b.render()

    # --------------------------------------------------------------- SETUP
    def cmd_setup(self) -> str:
        lines = [RULE, "SETUP SCAN", RULE]
        good = [s for s in self.setups if getattr(s, "ok", False)]
        bad = [s for s in self.setups if not getattr(s, "ok", False)]
        if not self.setups:
            lines.append("  No candidate setups submitted. The engine does not "
                         "generate setups from nothing.")
        for s in good:
            lines.append(s.render())     # type: ignore[union-attr]
            lines.append(THIN)
        for s in bad:
            lines.append(s.render())     # type: ignore[union-attr]
        if self.setups and not good:
            lines.append(THIN)
            lines.append("  NO TRADE - WAIT FOR CONFIRMATION")
            lines.append("  Every candidate failed at least one gate. No trade beats "
                         "a bad trade.")
        lines.append(RULE)
        return "\n".join(lines)

    # --------------------------------------------------------------- ALERT
    def cmd_alert(self, threshold: float = 60.0) -> str:
        hot = [e for e in self.ranked() if e.effective_priority >= threshold]
        if not hot:
            return (
                f"{RULE}\nNO ALERT-GRADE DEVELOPMENTS\n{RULE}\n"
                f"  Nothing in the book clears priority {threshold:.0f}. Silence here "
                "is information: it means nothing is currently changing expectations."
            )
        return "\n\n".join(render_alert(e) for e in hot)

    # ----------------------------------------------------------- PRE-EVENT
    def cmd_preevent(self, code: str | None) -> str:
        code = (code or "US_CPI").upper()
        r = BY_CODE.get(code)
        if r is None:
            return (f"UNKNOWN release code '{code}'. Known codes: "
                    + ", ".join(sorted(BY_CODE)[:20]) + " ...")
        ind = r.indicator
        up, dn = (
            (Impulse.INFLATION_COOLER, Impulse.INFLATION_HOTTER)
            if ind and ind.inflation_sign != 0
            else (Impulse.GROWTH_STRONGER, Impulse.GROWTH_WEAKER)
        )
        nxt = r.next_occurrences(utcnow().date(), 1)
        when = nxt[0] if isinstance(nxt, list) and nxt else None
        pack = preevent.build(
            r.label, scheduled_for=when, regime=self.state.regime, indicator=ind,
            reaction_up=build_matrix(up, self.state.regime),
            reaction_down=build_matrix(dn, self.state.regime),
            structure=self.structures.get(code),
            market_pricing=self.state.market_pricing.get(r.agency),
        )
        return pack.render()

    # ------------------------------------------------------- WHAT MATTERS?
    def cmd_what_matters(self, k: int = 5) -> str:
        ranked = self.ranked()
        lines = [RULE, "WHAT MATTERS - NOISE STRIPPED", RULE]
        if not ranked:
            lines.append("  Nothing in the book changes expectations right now.")
            lines.append("  That is a finding, not a gap: an empty answer beats a "
                         "manufactured one.")
            lines.append(RULE)
            return "\n".join(lines)
        changers = [e for e in ranked if e.noise is None or e.noise.changes_expectations]
        pool = changers or ranked
        for i, e in enumerate(pool[:k], 1):
            lines.append(f"  {i}. {e.title}")
            lines.append(f"     priority {e.effective_priority:.1f} [{e.band.value}] | "
                         f"{e.confirmation.label}")
            lines.append(f"     before: {e.market_pricing_before}")
            if e.reaction:
                top = max(e.reaction.cells, key=lambda c: c.confidence)
                lines.append(f"     highest-conviction leg: {top.asset} "
                             f"{top.direction.arrow} ({top.confidence:.2f}) - {top.mechanism}")
            lines.append(f"     invalidation: {e.invalidation}")
        dropped = len(ranked) - len(pool)
        if dropped > 0:
            lines.append(f"  ({dropped} item(s) ranked but excluded: they do not change "
                         "the prior distribution.)")
        lines.append(RULE)
        return "\n".join(lines)


__all__ = ["COMMANDS", "Radar"]
