"""Actual-vs-expected: the arithmetic, the refusals, and the rendered panel.

The engine's value is entirely in what it declines to do, so most of this file
drives the refusals rather than the happy path.
"""

from __future__ import annotations

import unittest

from macro import seed, terminal
from macro.live import RELEASE_CLOCK
from macro.reaction import MacroRegime, build_matrix
from macro.surprise import Impulse
from macro.release import (
    ABOVE, BEARISH, BELOW, BULLISH, IN_LINE, MIXED, NEUTRAL,
    Expectation, Forecast, assess, fmt_value, roll_up,
)
from macro.types import Insufficient

INFL = "INFLATION-DOMINANT"


def exp(**kw) -> Expectation:
    base = dict(metric="Core MoM", actual=0.3, consensus=0.2, unit="pct",
                source="BLS via CNBC", tier=1, as_of="2026-09-11T12:30:00Z",
                consensus_source="Dow Jones consensus", hawkish_sign=1)
    base.update(kw)
    return Expectation(**base)


class TestConstruction(unittest.TestCase):
    def test_actual_needs_a_source(self):
        with self.assertRaises(ValueError):
            exp(source="  ")

    def test_consensus_needs_its_own_carrier(self):
        """A consensus with no carrier is somebody's memory of a consensus."""
        with self.assertRaises(ValueError):
            exp(consensus_source="")

    def test_tier_is_bounded(self):
        for bad in (0, 5, -1):
            with self.assertRaises(ValueError):
                exp(tier=bad)

    def test_stamp_must_be_iso_z(self):
        for bad in ("2026-09-11", "2026-09-11T12:30:00", "not a date"):
            with self.assertRaises(ValueError):
                exp(as_of=bad)

    def test_two_channels_is_rejected(self):
        """One row, one channel. A blended verdict cannot be audited."""
        with self.assertRaises(ValueError):
            exp(hawkish_sign=1, growth_sign=1)

    def test_signs_are_bounded(self):
        with self.assertRaises(ValueError):
            exp(hawkish_sign=2)

    def test_negative_tolerance_is_rejected(self):
        with self.assertRaises(ValueError):
            exp(tolerance=-0.1)

    def test_non_finite_is_rejected(self):
        for bad in (float("nan"), float("inf")):
            with self.assertRaises(ValueError):
                exp(actual=bad)


class TestForecastConstruction(unittest.TestCase):
    """A Forecast is only half an Expectation, and the half it keeps still has
    to carry provenance."""

    def fc(self, **kw):
        base = dict(metric="Headline YoY", consensus=3.7, unit="pct",
                    consensus_source="Consensus forecast, via Nowflation",
                    as_of="2026-09-14T18:00:00Z", previous=3.4)
        base.update(kw)
        return Forecast(**base)

    def test_it_builds(self):
        self.assertIn("3.7% expected", self.fc().render())
        self.assertIn("not yet printed", self.fc().render())

    def test_consensus_needs_a_carrier(self):
        for bad in ("", "   "):
            with self.assertRaises(ValueError):
                self.fc(consensus_source=bad)

    def test_unit_is_mandatory(self):
        with self.assertRaises(ValueError):
            self.fc(unit=" ")

    def test_metric_is_mandatory(self):
        with self.assertRaises(ValueError):
            self.fc(metric="")

    def test_stamp_must_be_iso_z(self):
        with self.assertRaises(ValueError):
            self.fc(as_of="2026-09-14")

    def test_non_finite_consensus_is_rejected(self):
        for bad in (float("nan"), float("inf")):
            with self.assertRaises(ValueError):
                self.fc(consensus=bad)

    def test_it_carries_no_actual_at_all(self):
        """The reason this is a separate type: there is no field a caller could
        forget to check."""
        self.assertFalse(hasattr(self.fc(), "actual"))

    def test_every_shipped_forecast_constructs(self):
        seen = 0
        for r in RELEASE_CLOCK:
            for spec in r.get("forecasts") or ():
                Forecast(**{k: v for k, v in spec.items() if k != "note"})
                seen += 1
        self.assertGreaterEqual(seen, 2)

    def test_no_forecast_is_attached_to_a_release_that_already_printed(self):
        for r in RELEASE_CLOCK:
            if r.get("forecasts"):
                self.assertGreater(r["when"], seed.CAPTURE,
                                   f"{r['code']} has printed but still shows a forecast")


class TestRefusals(unittest.TestCase):
    def test_no_channel_refuses_a_verdict(self):
        v = assess(exp(hawkish_sign=0), INFL)
        self.assertIsInstance(v, Insufficient)
        self.assertIn("hawkish_sign/growth_sign", v.missing)

    def test_unknown_regime_refuses_a_verdict(self):
        for regime in ("", "UNKNOWN", "MIXED / UNRESOLVED"):
            v = assess(exp(), regime)
            self.assertIsInstance(v, Insufficient, regime)
            self.assertIn("regime", v.missing)

    def test_a_refusal_is_not_silently_neutral(self):
        """The failure mode this guards: refusing by returning NEUTRAL, which
        reads on the page as 'we checked and it did not matter'."""
        v = assess(exp(), "UNKNOWN")
        self.assertFalse(getattr(v, "ok", False))
        self.assertNotIn(NEUTRAL, v.render())


class TestArithmetic(unittest.TestCase):
    def test_exact_match_is_in_line(self):
        v = assess(exp(actual=3.4, consensus=3.4), INFL)
        self.assertEqual((v.direction, v.risk), (IN_LINE, NEUTRAL))

    def test_hot_inflation_is_bearish_risk(self):
        v = assess(exp(actual=0.3, consensus=0.2), INFL)
        self.assertEqual((v.direction, v.risk), (ABOVE, BEARISH))

    def test_cool_inflation_is_bullish_risk(self):
        v = assess(exp(actual=0.2, consensus=0.3), INFL)
        self.assertEqual((v.direction, v.risk), (BELOW, BULLISH))

    def test_float_noise_does_not_flip_a_tolerance(self):
        """5.4 - 5.3 is 0.10000000000000053 in binary floating point. Without
        the epsilon a tolerance of exactly 0.1 calls this a surprise while
        calling 0.2 - 0.3 in line - the same gap, opposite answers."""
        hot = assess(exp(actual=5.4, consensus=5.3, tolerance=0.1), INFL)
        cool = assess(exp(actual=0.2, consensus=0.3, tolerance=0.1), INFL)
        self.assertEqual(hot.direction, IN_LINE)
        self.assertEqual(cool.direction, IN_LINE)

    def test_tolerance_absorbs_survey_noise(self):
        v = assess(exp(metric="Initial claims", actual=206.0, consensus=205.0,
                       unit="k", hawkish_sign=0, growth_sign=-1, tolerance=5.0), INFL)
        self.assertEqual(v.direction, IN_LINE)

    def test_a_claims_blowout_still_registers(self):
        """Claims far above consensus is a weaker-growth impulse, and under an
        inflation-dominant reaction function macro.reaction reads bad news as
        bought. This module does not hold its own opinion about that."""
        v = assess(exp(metric="Initial claims", actual=260.0, consensus=205.0,
                       unit="k", hawkish_sign=0, growth_sign=-1, tolerance=5.0), INFL)
        self.assertEqual(v.direction, ABOVE)
        self.assertEqual(v.risk, BULLISH)
        self.assertIn("stall speed", v.why)


class TestRegimeConditionality(unittest.TestCase):
    """The same print, two reaction functions, two answers. This is the whole
    argument for refusing when the regime is unknown."""

    def test_strong_growth_flips_sign_with_the_regime(self):
        strong = dict(metric="Retail sales", actual=0.9, consensus=0.4, unit="pct",
                      hawkish_sign=0, growth_sign=1)
        self.assertEqual(assess(exp(**strong), INFL).risk, BEARISH)
        self.assertEqual(assess(exp(**strong), "GROWTH-DOMINANT").risk, BULLISH)

    def test_weak_growth_flips_sign_with_the_regime_too(self):
        weak = dict(metric="Retail sales", actual=-0.4, consensus=0.4, unit="pct",
                    hawkish_sign=0, growth_sign=1)
        self.assertEqual(assess(exp(**weak), INFL).risk, BULLISH)
        self.assertEqual(assess(exp(**weak), "GROWTH-DOMINANT").risk, BEARISH)

    def test_policy_channel_does_not_depend_on_the_regime(self):
        for regime in (INFL, "GROWTH-DOMINANT"):
            self.assertEqual(assess(exp(actual=0.3, consensus=0.2), regime).risk,
                             BEARISH)


class TestOneReactionFunction(unittest.TestCase):
    """There must be exactly one mapping from impulse to direction in this
    codebase. An independent copy here disagreed with macro.reaction on whether
    weak growth under an inflation-dominant regime is bought; this pins the
    verdict to that engine so the two cannot drift apart again."""

    CASES = (
        (dict(actual=0.3, consensus=0.2, hawkish_sign=1), Impulse.INFLATION_HOTTER),
        (dict(actual=0.1, consensus=0.2, hawkish_sign=1), Impulse.INFLATION_COOLER),
        (dict(actual=0.9, consensus=0.4, hawkish_sign=0, growth_sign=1),
         Impulse.GROWTH_STRONGER),
        (dict(actual=0.1, consensus=0.4, hawkish_sign=0, growth_sign=1),
         Impulse.GROWTH_WEAKER),
    )

    def test_every_verdict_matches_the_reaction_map(self):
        for regime, key in ((INFL, MacroRegime.INFLATION_DOMINANT),
                            ("GROWTH-DOMINANT", MacroRegime.GROWTH_DOMINANT)):
            for kw, impulse in self.CASES:
                v = assess(exp(**kw), regime)
                cell = build_matrix(impulse, key).by_asset("S&P 500")
                want = {"UP UP": BULLISH, "UP": BULLISH, "up": BULLISH,
                        "DOWN DOWN": BEARISH, "DOWN": BEARISH, "dn": BEARISH,
                        "~": NEUTRAL, "?": MIXED}[cell.direction.value]
                self.assertEqual(v.risk, want, f"{regime} {impulse.value}")
                self.assertEqual(v.impulse, impulse.value)

    def test_the_mechanism_prose_follows_the_sign(self):
        """The reaction cells described the hot case while their direction
        flipped, so a BULLISH verdict rendered beside bearish prose."""
        hot = assess(exp(actual=0.3, consensus=0.2, hawkish_sign=1), INFL)
        cool = assess(exp(actual=0.1, consensus=0.2, hawkish_sign=1), INFL)
        self.assertIn("compresses multiples", hot.why)
        self.assertIn("expands multiples", cool.why)
        self.assertNotIn("compresses multiples", cool.why)
        self.assertNotIn("sell off together", cool.why)


class TestRollUp(unittest.TestCase):
    def test_no_prints_is_neutral_and_says_why(self):
        label, why = roll_up([])
        self.assertEqual(label, NEUTRAL)
        self.assertIn("has been sourced yet", why)

    def test_all_in_line_is_neutral(self):
        v = assess(exp(actual=3.4, consensus=3.4), INFL)
        self.assertEqual(roll_up([v, v])[0], NEUTRAL)

    def test_agreement_carries_through(self):
        v = assess(exp(actual=0.3, consensus=0.2), INFL)
        self.assertEqual(roll_up([v, v])[0], BEARISH)

    def test_disagreement_is_mixed_and_names_the_split(self):
        hot = assess(exp(metric="Headline YoY", actual=5.4, consensus=5.3), INFL)
        cool = assess(exp(metric="Core MoM", actual=0.2, consensus=0.3), INFL)
        label, why = roll_up([hot, cool])
        self.assertEqual(label, MIXED)
        self.assertIn("Headline YoY", why)
        self.assertIn("Core MoM", why)
        self.assertIn("bearish", why)
        self.assertIn("bullish", why)


class TestFormatting(unittest.TestCase):
    def test_one_decimal_percent_stays_one_decimal(self):
        self.assertEqual(fmt_value(3.4, "pct"), "3.4%")

    def test_two_decimal_percent_is_preserved(self):
        self.assertEqual(fmt_value(2.25, "pct"), "2.25%")

    def test_thousands_units(self):
        self.assertEqual(fmt_value(206.0, "k"), "206k")

    def test_rounding_is_half_up_like_the_rest_of_the_codebase(self):
        """Python's format spec rounds half to even: 0.125 prints 0.12 and
        2.675 prints 2.67, while macro.terminal._fmt gives 0.13 and 2.68. Two
        rounding rules in one page is how a number changes when it moves cell."""
        self.assertEqual(fmt_value(0.125, "pct"), "0.13%")
        self.assertEqual(fmt_value(2.675, "pct"), "2.68%")
        self.assertEqual(fmt_value(12.5, "bp"), "+13bp")

    def test_negative_percents_keep_their_sign_and_precision(self):
        self.assertEqual(fmt_value(-0.4, "pct"), "-0.4%")
        self.assertEqual(fmt_value(-0.125, "pct"), "-0.13%")


class TestSeededReleases(unittest.TestCase):
    """Every print shipped in RELEASE_CLOCK must survive its own validator."""

    def test_every_shipped_print_constructs_and_assesses(self):
        seen = 0
        for r in RELEASE_CLOCK:
            for spec in r.get("prints") or ():
                kw = {k: v for k, v in spec.items() if k != "note"}
                v = assess(Expectation(**kw), seed.REGIME)
                self.assertTrue(getattr(v, "ok", False), f"{r['code']}: {v}")
                seen += 1
        self.assertGreaterEqual(seen, 9)

    def test_every_print_stamp_matches_its_release_instant(self):
        """A figure stamped away from the release it belongs to is either the
        wrong month's data or an invented time."""
        for r in RELEASE_CLOCK:
            for spec in r.get("prints") or ():
                self.assertEqual(spec["as_of"], r["when"],
                                 f"{r['code']}/{spec['metric']}")

    def test_no_print_is_attached_to_a_future_release(self):
        cap = seed.CAPTURE
        for r in RELEASE_CLOCK:
            if r.get("prints"):
                self.assertLessEqual(r["when"], cap,
                                     f"{r['code']} has figures but has not happened")

    def test_cpi_reads_exactly_as_the_desk_stated_it(self):
        cpi = [r for r in RELEASE_CLOCK if r["code"] == "US_CPI"][0]
        by = {p["metric"]: p for p in cpi["prints"]}
        self.assertEqual((by["Headline YoY"]["actual"],
                          by["Headline YoY"]["consensus"]), (3.4, 3.4))
        self.assertEqual(assess(Expectation(**{k: v for k, v in
                                               by["Headline YoY"].items()
                                               if k != "note"}), INFL).risk, NEUTRAL)
        self.assertEqual(assess(Expectation(**{k: v for k, v in
                                               by["Core MoM"].items()
                                               if k != "note"}), INFL).risk, BEARISH)

    def test_ppi_rolls_up_mixed_because_its_legs_disagree(self):
        ppi = [r for r in RELEASE_CLOCK if r["code"] == "US_PPI"][0]
        vs = [assess(Expectation(**{k: v for k, v in p.items() if k != "note"}), INFL)
              for p in ppi["prints"]]
        self.assertEqual(roll_up(vs)[0], MIXED)


class TestRenderedPanel(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.snap = seed.build()
        cls.doc = terminal.render(cls.snap)

    def test_actual_and_expected_both_reach_the_page(self):
        self.assertIn(">3.4%<", self.doc)
        self.assertIn("expected", self.doc)

    def test_a_verdict_is_rendered_for_a_released_print(self):
        self.assertIn("VERDICT BEARISH", self.doc)
        self.assertIn("VERDICT MIXED", self.doc)

    def test_both_carriers_are_named_on_the_page(self):
        self.assertIn("Dow Jones consensus", self.doc)
        self.assertIn("BLS via CNBC", self.doc)

    def test_a_future_release_never_renders_a_verdict(self):
        """A pending release may show what the market is CARRYING, but never a
        direction and never a risk read - there is no actual to compare to."""
        pending = [r for r in self.snap.releases if r["when"] > self.snap.captured]
        self.assertGreaterEqual(len(pending), 10, "the calendar has run dry")
        for r in pending:
            html = terminal.render_prints(r, self.snap)
            self.assertNotIn("VERDICT", html, r["code"])
            self.assertNotIn("BEARISH", html, r["code"])
            self.assertNotIn("BULLISH", html, r["code"])
            if r.get("forecasts"):
                self.assertIn("AWAITING", html, r["code"])
                self.assertIn("NOT PRINTED", html, r["code"])
            else:
                self.assertEqual(html, "", r["code"])

    def test_a_pending_release_shows_its_consensus_and_its_carrier(self):
        cpi = [r for r in self.snap.releases if r["code"] == "US_CPI_SEP"][0]
        html = terminal.render_prints(cpi, self.snap)
        self.assertIn("3.7%", html)
        self.assertIn("Nowflation", html)
        self.assertIn("awaiting", html)

    def test_the_calendar_reaches_beyond_the_next_month(self):
        """The panel ran dry two days out before this existed. A shallow
        calendar is the failure this guards, and it is silent otherwise."""
        pending = sorted(r["when"] for r in self.snap.releases
                         if r["when"] > self.snap.captured)
        self.assertGreaterEqual(len(pending), 15)
        self.assertGreater(pending[-1][:7], self.snap.captured[:7],
                           "the furthest pending event is still this month")

    def test_every_release_row_is_uniquely_coded_and_dated(self):
        codes = [r["code"] for r in self.snap.releases]
        self.assertEqual(len(codes), len(set(codes)), "duplicate release codes")
        for r in self.snap.releases:
            self.assertRegex(r["when"], r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
            self.assertTrue(r.get("url", "").startswith("https://"), r["code"])
            self.assertTrue(r.get("agency", "").strip(), r["code"])

    def test_a_day_granularity_row_declares_itself(self):
        """A row whose carrier published no time must not render a clock. The
        marker has to reach the DOM: the JS reads data-day, and without it the
        row silently grows a second counter against an assumed midnight."""
        day = [r for r in self.snap.releases if r.get("day")]
        self.assertTrue(day, "no day-granularity row to check")
        self.assertIn('data-day="1"', self.doc)
        self.assertIn("time not published", self.doc)
        for r in day:
            self.assertTrue(r["when"].endswith("T00:00:00Z"), r["code"])

    def test_pending_releases_render_above_released_ones(self):
        """Source order buried Wednesday's FOMC under last week's CPI once the
        calendar grew past four rows."""
        import re as _re
        rows = _re.findall(r'<div class="rl">.*?data-when="([^"]+)"', self.doc)
        self.assertGreaterEqual(len(rows), 20)
        cap = self.snap.captured
        past = [i for i, w in enumerate(rows) if w <= cap]
        future = [i for i, w in enumerate(rows) if w > cap]
        self.assertTrue(future and past)
        self.assertLess(max(future), min(past),
                        "a released row rendered above a pending one")
        # pending ascending: the soonest event is the top row
        self.assertEqual([rows[i] for i in future],
                         sorted(rows[i] for i in future))
        # released descending: the most recent print sits directly under them
        self.assertEqual([rows[i] for i in past],
                         sorted((rows[i] for i in past), reverse=True))

    def test_a_past_release_with_no_figures_says_so(self):
        """Silence on a passed release reads as 'nothing happened'."""
        ghost = {"code": "X", "label": "X", "when": "2026-01-01T00:00:00Z"}
        html = terminal.render_prints(ghost, self.snap)
        self.assertIn("have not been sourced", html)

    def test_released_split_uses_the_snapshot_not_the_wall_clock(self):
        """Regenerating the same snapshot tomorrow must produce the same page."""
        snap = seed.build()
        snap.captured = "2026-09-10T00:00:00Z"
        cpi = [r for r in snap.releases if r["code"] == "US_CPI"][0]
        self.assertEqual(terminal.render_prints(cpi, snap), "")

    def test_a_refused_print_does_not_shift_the_notes_onto_wrong_metrics(self):
        """Verdict and spec used to be zipped from two lists of unequal length,
        so one refusal slid every provenance line onto the next metric."""
        rel = {"code": "X", "label": "X", "when": "2026-09-10T12:30:00Z",
               "prints": (
                   {"metric": "FIRST", "actual": 1.0, "consensus": 1.0, "unit": "pct",
                    "source": "A", "tier": 1, "as_of": "2026-09-10T12:30:00Z",
                    "consensus_source": "B", "hawkish_sign": 0,
                    "note": "note for FIRST"},        # no channel -> refused
                   {"metric": "SECOND", "actual": 0.3, "consensus": 0.2, "unit": "pct",
                    "source": "A", "tier": 1, "as_of": "2026-09-10T12:30:00Z",
                    "consensus_source": "B", "hawkish_sign": 1,
                    "note": "note for SECOND"},
               )}
        html = terminal.render_prints(rel, self.snap)
        first = html.index("note for SECOND")
        self.assertIn("SECOND", html[:first])
        self.assertNotIn("FIRST</b> &middot; actual", html)
        # the refused row names its own metric beside the refusal
        self.assertRegex(html, r"<b>FIRST</b> &middot; INSUFFICIENT DATA")

    def test_all_refused_is_not_reported_as_nothing_sourced(self):
        rel = {"code": "X", "label": "X", "when": "2026-09-10T12:30:00Z",
               "prints": ({"metric": "ONLY", "actual": 1.0, "consensus": 1.0,
                           "unit": "pct", "source": "A", "tier": 1,
                           "as_of": "2026-09-10T12:30:00Z",
                           "consensus_source": "B"},)}
        html = terminal.render_prints(rel, self.snap)
        self.assertIn("NO VERDICT", html)
        self.assertNotIn("have not been sourced", html)
        self.assertIn("INSUFFICIENT DATA", html)

    def test_article_agrees_with_the_regime_label(self):
        self.assertEqual(terminal._article("INFLATION-DOMINANT"), "an")
        self.assertEqual(terminal._article("GROWTH-DOMINANT"), "a")
        self.assertEqual(terminal._article(""), "a")

    def test_the_panel_note_describes_what_the_block_actually_is(self):
        import re
        flat = re.sub(r"\s+", " ", self.doc)
        self.assertIn("the actual against the number the market was carrying", flat)
        self.assertIn("returns a refusal instead of a verdict", flat)


if __name__ == "__main__":
    unittest.main()
