import unittest

from macro.centralbank import Tone, diff_statements, read_tone, speech_radar
from macro.reaction import ASSETS, Direction, analyse_orders, build_matrix
from macro.regime import MacroRegime
from macro.surprise import Impulse

HAWK = ("The Committee judges that inflation remains elevated. In determining the "
        "extent of additional policy firming that may be appropriate, the Committee "
        "remains highly vigilant. Upside risks to inflation persist and policy must "
        "stay sufficiently restrictive. Policy is data-dependent.")
DOVE = ("Inflation has eased and disinflation is broadly based. The Committee has "
        "gained greater confidence that inflation is moving sustainably toward 2 "
        "percent. Downside risks to employment have increased. The Committee will "
        "proceed meeting by meeting and judges risks are broadly balanced.")


class TestReactionMatrix(unittest.TestCase):
    def test_every_asset_gets_a_cell(self):
        m = build_matrix(Impulse.INFLATION_HOTTER, MacroRegime.INFLATION_DOMINANT)
        self.assertEqual({c.asset for c in m.cells}, set(ASSETS))

    def test_unknown_regime_refuses_to_pick_a_direction(self):
        m = build_matrix(Impulse.GROWTH_STRONGER, MacroRegime.UNKNOWN)
        self.assertTrue(all(c.direction is Direction.AMBIGUOUS for c in m.cells))
        self.assertTrue(all(c.confidence == 0.0 for c in m.cells))

    def test_equity_sign_flips_with_the_regime(self):
        a = build_matrix(Impulse.GROWTH_WEAKER, MacroRegime.INFLATION_DOMINANT)
        b = build_matrix(Impulse.GROWTH_WEAKER, MacroRegime.GROWTH_DOMINANT)
        self.assertNotEqual(a.by_asset("S&P 500").direction,
                            b.by_asset("S&P 500").direction)

    def test_hot_inflation_bear_flattens(self):
        m = build_matrix(Impulse.INFLATION_HOTTER, MacroRegime.INFLATION_DOMINANT)
        self.assertIn(m.by_asset("US 2Y").direction,
                      (Direction.UP, Direction.STRONG_UP))
        self.assertIn(m.by_asset("2s10s").direction,
                      (Direction.DOWN, Direction.STRONG_DOWN))

    def test_oil_is_ambiguous_on_an_inflation_shock(self):
        m = build_matrix(Impulse.INFLATION_HOTTER, MacroRegime.INFLATION_DOMINANT)
        self.assertIs(m.by_asset("WTI Crude").direction, Direction.AMBIGUOUS)

    def test_liquidity_regime_bids_the_dollar_regardless_of_impulse(self):
        for imp in (Impulse.INFLATION_COOLER, Impulse.GROWTH_STRONGER):
            m = build_matrix(imp, MacroRegime.LIQUIDITY_DOMINANT)
            self.assertIn(m.by_asset("USD (DXY)").direction,
                          (Direction.UP, Direction.STRONG_UP))

    def test_every_cell_carries_a_mechanism(self):
        m = build_matrix(Impulse.INFLATION_HOTTER, MacroRegime.INFLATION_DOMINANT)
        self.assertTrue(all(len(c.mechanism) > 20 for c in m.cells))

    def test_magnitude_scales_conviction_not_sign(self):
        small = build_matrix(Impulse.INFLATION_HOTTER, MacroRegime.INFLATION_DOMINANT, magnitude=0.5)
        big = build_matrix(Impulse.INFLATION_HOTTER, MacroRegime.INFLATION_DOMINANT, magnitude=3.0)
        self.assertIs(small.by_asset("US 2Y").direction, Direction.UP)
        self.assertIs(big.by_asset("US 2Y").direction, Direction.STRONG_UP)

    def test_neutral_impulse_prices_nothing(self):
        m = build_matrix(Impulse.NEUTRAL, MacroRegime.INFLATION_DOMINANT)
        self.assertTrue(all(c.direction is Direction.FLAT for c in m.cells))

    def test_order_analysis_covers_the_spec_questions(self):
        oa = analyse_orders(build_matrix(Impulse.INFLATION_HOTTER,
                                         MacroRegime.INFLATION_DOMINANT))
        topics = " ".join(q for q, _ in oa.questions_answered).lower()
        for t in ("policy path", "real yields", "dollar", "financial conditions",
                  "equity valuation", "gold", "crypto"):
            self.assertIn(t, topics)


class TestCentralBankLanguage(unittest.TestCase):
    def test_hawkish_and_dovish_are_separated(self):
        self.assertIn(read_tone(HAWK).tone, (Tone.HAWKISH, Tone.EXTREMELY_HAWKISH))
        self.assertIn(read_tone(DOVE).tone, (Tone.DOVISH, Tone.EXTREMELY_DOVISH))

    def test_empty_text_is_neutral_with_a_no_read_caveat(self):
        r = read_tone("The weather in Frankfurt was pleasant today and nothing else.")
        self.assertIs(r.tone, Tone.NEUTRAL)
        self.assertTrue(any("no read" in c for c in r.caveats))

    def test_tone_is_labelled_interpretation_not_fact(self):
        self.assertEqual(read_tone(HAWK).category.value, "INTERPRETATION")

    def test_confidence_is_capped(self):
        self.assertLessEqual(read_tone(HAWK * 20).confidence, 0.85)

    def test_short_text_confidence_is_discounted(self):
        short = read_tone("Further policy firming may be appropriate.")
        self.assertTrue(any("Short text" in c for c in short.caveats))

    def test_diff_detects_deleted_guidance(self):
        d = diff_statements(HAWK, DOVE)
        self.assertIn("additional policy firming", d.removed_phrases)
        self.assertLess(d.shift, 0)
        self.assertIn("DELETED", d.headline)

    def test_diff_detects_added_language(self):
        d = diff_statements(HAWK, DOVE)
        self.assertIn("gained greater confidence", d.added_phrases)

    def test_identical_texts_show_no_shift(self):
        d = diff_statements(HAWK, HAWK)
        self.assertAlmostEqual(d.shift, 0.0)
        self.assertIn("UNCHANGED", d.headline)

    def test_guidance_markers_tracked_both_ways(self):
        d = diff_statements(HAWK, DOVE)
        self.assertTrue(d.guidance_added or d.guidance_removed)

    def test_speech_radar_refuses_to_invent_pricing(self):
        sr = speech_radar("Speaker", "Central Bank", "Governor")
        self.assertIn("UNKNOWN", sr.market_prices_now)
        self.assertTrue(sr.hawkish_triggers and sr.dovish_triggers)


if __name__ == "__main__":
    unittest.main()
