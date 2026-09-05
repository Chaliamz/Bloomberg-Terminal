"""The no-fabrication contract, enforced as tests rather than asserted in prose."""

import io
import re
import unittest
from contextlib import redirect_stdout, redirect_stderr

from macro import __main__ as cli
from macro.brief import build as build_brief
from macro.data import fred, treasury
from macro.data.base import Unavailable
from macro.events import make_event, render_alert
from macro.preevent import build as build_preevent
from macro.radar import COMMANDS, Radar
from macro.regime import MacroRegime
from macro.render.html import render as render_html
from macro.scoring import EventClass
from macro.sources import make_source
from macro.state import CORE_KEYS, MarketState
from macro.types import Tier, observed, unknown, utcnow

# Words that name a market value. If a section on an empty system mentions one,
# it must be marking it absent, not supplying it.
MARKET_WORDS = ("consensus", "actual", "previous", "forecast", "estimate")
# Phrases that count as marking a value absent rather than supplying one.
REFUSALS = ("unknown", "never generated", "not supplied", "must be ingested",
            "are not invented", "not generated")


class TestEmptySystemInventsNothing(unittest.TestCase):
    def setUp(self):
        self.radar = Radar()

    def test_every_command_runs_on_an_empty_book(self):
        for cmd in COMMANDS:
            out = self.radar.dispatch(cmd)
            self.assertIsInstance(out, str)
            self.assertGreater(len(out), 20, cmd)

    def test_empty_state_reports_unknown_for_every_core_field(self):
        st = MarketState()
        for k in CORE_KEYS:
            self.assertFalse(st.get(k).known, k)
        self.assertEqual(st.coverage, 0.0)

    def test_curve_and_conditions_refuse_on_an_empty_state(self):
        st = MarketState()
        self.assertFalse(st.curve().ok)
        self.assertFalse(st.conditions().ok)

    def test_empty_brief_offers_no_market_values(self):
        b = build_brief(MarketState(), [])
        text = b.render()
        for section in b.sections:
            joined = " ".join(section.lines).lower()
            if any(w in joined for w in MARKET_WORDS):
                self.assertTrue(
                    any(r in joined for r in REFUSALS),
                    f"section '{section.title}' names a market value without "
                    f"marking it absent: {joined[:200]}",
                )
        self.assertEqual(b.bias, "WAIT")

    def test_bias_defaults_to_wait_without_a_regime(self):
        self.assertEqual(build_brief(MarketState(), []).bias, "WAIT")

    def test_bias_stays_wait_on_thin_coverage_even_with_a_regime(self):
        st = MarketState()
        st.regime = MacroRegime.GROWTH_DOMINANT
        st.put("US2Y", observed(4.0, "pct"))
        self.assertEqual(build_brief(st, []).bias, "WAIT")

    def test_alert_command_says_nothing_rather_than_inventing(self):
        out = self.radar.cmd_alert()
        self.assertIn("NO ALERT-GRADE", out)

    def test_setup_command_generates_nothing_from_nothing(self):
        self.assertIn("does not generate setups", self.radar.cmd_setup())

    def test_next_separates_rule_derived_from_agency_scheduled(self):
        out = self.radar.cmd_next()
        self.assertIn("cannot be derived", out)

    def test_cpi_map_refuses_to_supply_a_consensus(self):
        out = self.radar.dispatch("CPI")
        self.assertIn("never generates forecast values", out)


class TestUnknownPropagation(unittest.TestCase):
    def test_alert_renders_unknowns_instead_of_placeholders(self):
        ev = make_event(
            "Unsourced claim", event_class=EventClass.GEOPOLITICAL, country="Unknown",
            summary="A claim with no source and no reaction map.",
            sources=[], when=None, market_impact=80, expected_volatility=70,
            directional_confidence=40,
        )
        text = render_alert(ev)
        self.assertIn("TIME:         UNKNOWN", text)
        self.assertIn("NO SOURCE ATTACHED", text)
        self.assertIn("UNKNOWN - no transmission map attached", text)
        self.assertIn("UNKNOWN - no price series supplied", text)

    def test_unsourced_claims_score_near_zero_credibility(self):
        ev = make_event(
            "Unsourced claim", event_class=EventClass.EMERGENCY_ACTION, country="X",
            summary="x", sources=[], when=utcnow(), market_impact=100,
            expected_volatility=100, directional_confidence=100,
        )
        self.assertEqual(ev.confirmation.credibility_score, 0.0)
        self.assertLess(ev.scores.priority, 30.0)

    def test_a_confirmed_primary_event_outranks_a_louder_anonymous_one(self):
        primary = make_event(
            "Central bank cuts rates", event_class=EventClass.SCHEDULED_POLICY,
            country="X", summary="x",
            sources=[make_source("Fed", "https://www.federalreserve.gov/a",
                                 published_at=utcnow(), is_primary_document=True)],
            when=utcnow(), market_impact=85, expected_volatility=70,
            directional_confidence=60)
        anon = make_event(
            "SOURCES: emergency 100bp cut imminent", event_class=EventClass.EMERGENCY_ACTION,
            country="X", summary="x",
            sources=[make_source("@leak", "https://x.com/leak")],
            when=utcnow(), market_impact=100, expected_volatility=100,
            directional_confidence=90, is_unscheduled=True)
        self.assertGreater(primary.effective_priority, anon.effective_priority)

    def test_preevent_marks_every_missing_input(self):
        pack = build_preevent("Some release", scheduled_for=None,
                              regime=MacroRegime.UNKNOWN)
        self.assertTrue(pack.unknowns)
        text = pack.render()
        self.assertIn("UNKNOWN", text)
        self.assertIn("UNRESOLVED INPUTS", text)

    def test_html_renders_unknown_class_not_a_number(self):
        html = render_html(Radar(), build_brief(MarketState(), []))
        self.assertIn("class=\"num unknown\">UNKNOWN", html.replace("'", '"'))
        self.assertIn("are not estimated, back-filled or carried forward", html)

    def test_html_escapes_injected_content(self):
        r = Radar()
        r.add(make_event("<script>alert(1)</script>", event_class=EventClass.GEOPOLITICAL,
                         country="X", summary="x",
                         sources=[make_source("Reuters", "https://reuters.com/a",
                                              published_at=utcnow())],
                         when=utcnow(), market_impact=60, expected_volatility=50,
                         directional_confidence=40))
        html = render_html(r)
        self.assertNotIn("<script>alert(1)</script>", html)
        self.assertIn("&lt;script&gt;", html)


class TestAdaptersDegradeHonestly(unittest.TestCase):
    def test_fred_without_a_key_is_unavailable_not_a_stub(self):
        r = fred.fetch("DGS10", api_key=None) if not fred.available() else Unavailable("x", "y")
        self.assertIsInstance(r, Unavailable)
        self.assertIn("FRED_API_KEY", r.reason + r.hint)

    def test_no_bundled_fallback_values_exist_in_the_adapters(self):
        import inspect
        for mod in (fred, treasury):
            src = inspect.getsource(mod)
            self.assertNotIn("FALLBACK", src.upper())
            # a float literal that looks like a yield or price would be a smell
            self.assertFalse(re.search(r"=\s*[1-9]\d?\.\d{2}\b", src),
                             f"{mod.__name__} contains a hardcoded market-like value")

    def test_series_with_no_points_reports_unknown(self):
        from macro.data.base import Series
        from macro.types import SourceRef
        s = Series("X", "x", "pct", (), SourceRef("t", Tier.PRIMARY))
        self.assertFalse(s.latest.known)
        self.assertFalse(s.nth_last(3).known)


class TestCli(unittest.TestCase):
    def _run(self, argv):
        buf, err = io.StringIO(), io.StringIO()
        with redirect_stdout(buf), redirect_stderr(err):
            code = cli.main(argv)
        return code, buf.getvalue()

    def test_every_cli_command_exits_clean(self):
        for name in cli.CLI_TO_COMMAND:
            code, out = self._run([name])
            self.assertEqual(code, 0, name)
            self.assertTrue(out.strip(), name)

    def test_demo_is_labelled_synthetic_throughout(self):
        code, out = self._run(["demo"])
        self.assertEqual(code, 0)
        self.assertGreaterEqual(out.count("SYNTHETIC"), 5)
        self.assertIn("ALL VALUES BELOW ARE SYNTHETIC", out)
        self.assertIn("not market data", out.lower())
        # the banner is repeated at the end so a truncated read still carries it
        self.assertGreaterEqual(out.count("DEMONSTRATION MODE"), 2)

    def test_missing_state_file_is_an_error_not_a_silent_default(self):
        code, _ = self._run(["radar", "--state", "/nonexistent/state.json"])
        self.assertEqual(code, 2)

    def test_coverage_command(self):
        code, out = self._run(["coverage"])
        self.assertEqual(code, 0)
        self.assertIn("United States", out)


if __name__ == "__main__":
    unittest.main()
