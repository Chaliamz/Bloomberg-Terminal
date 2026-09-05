import unittest

from macro.setups import MIN_RR, NoTrade, Setup, Side, build_setup, whipsaw_plan

BASE = dict(
    asset="TEST", timeframe="15m", catalyst="a real catalyst", structure=None,
    liquidity_target="equal highs above", require_structure_confirmation=False,
)


def long_setup(**kw):
    args = dict(BASE, side=Side.LONG, entry_low=99, entry_high=101,
                invalidation=90, tp1=110, tp2=120, tp3=131)
    args.update(kw)
    return build_setup(**args)


class TestGeometry(unittest.TestCase):
    def test_valid_long_passes(self):
        s = long_setup()
        self.assertIsInstance(s, Setup)
        self.assertGreaterEqual(s.rr_net, MIN_RR)

    def test_stop_equal_to_entry_is_refused_not_divided_by_zero(self):
        s = long_setup(entry_low=100, entry_high=100, invalidation=100)
        self.assertIsInstance(s, NoTrade)
        self.assertTrue(any("zero or negative" in r for r in s.reasons))

    def test_stop_above_entry_on_a_long_is_refused(self):
        s = long_setup(invalidation=105)
        self.assertIsInstance(s, NoTrade)

    def test_short_geometry_is_mirrored(self):
        s = build_setup(**BASE, side=Side.SHORT, entry_low=99, entry_high=101,
                        invalidation=110, tp1=90, tp2=80, tp3=69)
        self.assertIsInstance(s, Setup)
        self.assertAlmostEqual(s.rr_gross, (100 - 69) / (110 - 100))

    def test_unordered_targets_refused(self):
        s = long_setup(tp1=110, tp2=105, tp3=131)
        self.assertIsInstance(s, NoTrade)

    def test_inverted_entry_bounds_are_swapped_and_noted(self):
        s = long_setup(entry_low=101, entry_high=99)
        self.assertIsInstance(s, Setup)
        self.assertTrue(any("swapped" in n for n in s.notes))


class TestRiskReward(unittest.TestCase):
    def test_rr_gross_arithmetic(self):
        s = long_setup()
        self.assertAlmostEqual(s.rr_gross, (131 - 100) / (100 - 90))

    def test_costs_hit_both_legs(self):
        # widen the target so the trade still clears the floor after costs
        s = long_setup(tp3=160, cost_per_unit=1.0)
        self.assertAlmostEqual(s.rr_net, (60 - 1.0) / (10 + 1.0))
        self.assertLess(s.rr_net, s.rr_gross)

    def test_below_floor_is_refused_with_the_number(self):
        s = long_setup(tp3=125, tp2=120, tp1=110, invalidation=85)
        self.assertIsInstance(s, NoTrade)
        self.assertTrue(any("below the 3R floor" in r for r in s.reasons))

    def test_costs_alone_can_break_the_floor(self):
        # 3.10R gross clears the floor; 1.0/unit of cost drops it to 2.73R
        ok = long_setup(invalidation=90, tp3=131)
        broken = long_setup(invalidation=90, tp3=131, cost_per_unit=1.0)
        self.assertIsInstance(ok, Setup)
        self.assertIsInstance(broken, NoTrade)
        self.assertTrue(any("Costs alone account for" in r for r in broken.reasons))


class TestGates(unittest.TestCase):
    def test_missing_catalyst_refused(self):
        self.assertIsInstance(long_setup(catalyst=None), NoTrade)
        self.assertIsInstance(long_setup(catalyst="   "), NoTrade)

    def test_missing_liquidity_target_refused(self):
        self.assertIsInstance(long_setup(liquidity_target=""), NoTrade)

    def test_catalyst_against_direction_refused(self):
        s = long_setup(catalyst_aligned=False)
        self.assertIsInstance(s, NoTrade)
        self.assertTrue(any("against" in r for r in s.reasons))

    def test_structure_requirement_refuses_without_a_read(self):
        s = long_setup(require_structure_confirmation=True)
        self.assertIsInstance(s, NoTrade)


class TestSizing(unittest.TestCase):
    def test_units_are_risk_over_risk_per_unit(self):
        s = long_setup(account_equity=100_000, risk_fraction=0.01)
        self.assertAlmostEqual(s.sizing.units, 1000 / 10)
        self.assertAlmostEqual(s.sizing.account_risk_amount, 1000)

    def test_costs_enter_the_size_denominator(self):
        s = long_setup(tp3=160, account_equity=100_000, risk_fraction=0.01,
                       cost_per_unit=1.0)
        self.assertAlmostEqual(s.sizing.units, 1000 / 11)

    def test_contract_multiplier_scales_units_and_notional(self):
        s = long_setup(account_equity=100_000, risk_fraction=0.01,
                       contract_multiplier=50)
        self.assertAlmostEqual(s.sizing.units, 1000 / (10 * 50))
        self.assertAlmostEqual(s.sizing.notional_at_entry, s.sizing.units * 100 * 50)

    def test_insane_risk_fraction_refused(self):
        self.assertIsInstance(
            long_setup(account_equity=100_000, risk_fraction=0.5), NoTrade)
        self.assertIsInstance(
            long_setup(account_equity=100_000, risk_fraction=0.0), NoTrade)

    def test_non_positive_equity_refused(self):
        self.assertIsInstance(long_setup(account_equity=0), NoTrade)

    def test_non_positive_multiplier_refused(self):
        self.assertIsInstance(
            long_setup(account_equity=100_000, contract_multiplier=0), NoTrade)

    def test_gap_risk_is_stated_not_hidden(self):
        s = long_setup(account_equity=100_000)
        self.assertTrue(any("gap risk" in a for a in s.sizing.assumptions))


class TestWhipsaw(unittest.TestCase):
    def test_plan_is_explicit_about_unknown_levels(self):
        p = whipsaw_plan("US CPI", None)
        self.assertIn("UNKNOWN", p.initial_reaction_zone)
        self.assertIn("UNKNOWN", p.sweep_zone)
        self.assertIn("Do not enter on the first spike", p.rule)

    def test_four_phase_sequence(self):
        self.assertEqual(len(whipsaw_plan("US CPI", None).sequence), 4)


if __name__ == "__main__":
    unittest.main()
