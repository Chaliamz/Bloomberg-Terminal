import unittest

from macro.curve import CurveMove, NOISE_BP, classify
from macro.liquidity import ANOMALY_Z, assess, detect_anomaly
from macro.regime import RiskRegime
from macro.types import observed as o
from macro.types import unknown


def curve(d2, d10, **kw):
    return classify(y2_now=o(4.0 + d2 / 100, "pct"), y2_prior=o(4.0, "pct"),
                    y10_now=o(4.2 + d10 / 100, "pct"), y10_prior=o(4.2, "pct"), **kw)


class TestCurve(unittest.TestCase):
    def test_bear_flattening(self):
        self.assertEqual(curve(+12, +4).move, CurveMove.BEAR_FLATTENING)

    def test_bull_steepening(self):
        self.assertEqual(curve(-18, -6).move, CurveMove.BULL_STEEPENING)

    def test_bull_flattening(self):
        self.assertEqual(curve(-4, -15).move, CurveMove.BULL_FLATTENING)

    def test_bear_steepening(self):
        self.assertEqual(curve(+3, +14).move, CurveMove.BEAR_STEEPENING)

    def test_sub_noise_move_is_not_classified(self):
        r = curve(+1, +1)
        self.assertEqual(r.move, CurveMove.UNCHANGED)
        self.assertTrue(any(f"{NOISE_BP:.0f}bp" in c for c in r.caveats))

    def test_bp_conversion(self):
        self.assertAlmostEqual(curve(+12, +4).d2y_bp, 12.0, places=6)

    def test_slope_change_arithmetic(self):
        self.assertAlmostEqual(curve(+12, +4).d_slope_2s10s_bp, -8.0, places=6)

    def test_missing_leg_is_insufficient(self):
        r = classify(y2_now=unknown("pct"), y2_prior=o(4.0, "pct"),
                     y10_now=o(4.3, "pct"), y10_prior=o(4.2, "pct"))
        self.assertFalse(r.ok)
        self.assertIn("2y", r.missing)

    def test_attribution_suppressed_without_real_yields(self):
        r = curve(+12, +4)
        self.assertIn("UNKNOWN", r.real_yield_note)
        self.assertTrue(any("attribution suppressed" in c for c in r.caveats))

    def test_real_yield_driven_move_is_identified(self):
        r = curve(-18, -6, real10_now=o(1.90, "pct"), real10_prior=o(2.00, "pct"),
                  breakeven10_now=o(2.32, "pct"), breakeven10_prior=o(2.30, "pct"))
        self.assertTrue(any("Real rates are driving" in p for p in r.pricing))

    def test_breakeven_driven_move_is_identified(self):
        r = curve(-4, -15, real10_now=o(1.99, "pct"), real10_prior=o(2.00, "pct"),
                  breakeven10_now=o(2.20, "pct"), breakeven10_prior=o(2.30, "pct"))
        self.assertTrue(any("Breakevens are driving" in p for p in r.pricing))

    def test_opposite_legs_are_flagged(self):
        r = curve(-10, +12)
        self.assertTrue(any("opposite directions" in c for c in r.caveats))

    def test_unit_mismatch_raises(self):
        with self.assertRaises(ValueError):
            classify(y2_now=o(4.1, "pct"), y2_prior=o(410, "bp"),
                     y10_now=o(4.3, "pct"), y10_prior=o(4.2, "pct"))


class TestConditions(unittest.TestCase):
    def test_no_inputs_is_insufficient(self):
        r = assess()
        self.assertFalse(r.ok)

    def test_alarms_trip_liquidity_stress(self):
        r = assess(levels={"vix": o(35, "index"), "hy_oas_bp": o(600, "bp")},
                   changes_z={"vix": 2.5, "spx_pct": -2.0})
        self.assertEqual(r.regime, RiskRegime.LIQUIDITY_STRESS)
        self.assertEqual(len(r.alarms), 2)

    def test_ambiguous_sign_inputs_are_excluded_from_the_score(self):
        a = assess(changes_z={"spx_pct": 1.0})
        b = assess(changes_z={"spx_pct": 1.0, "gold_pct": 3.0, "rrp_bn": -3.0})
        self.assertAlmostEqual(a.score, b.score)

    def test_coverage_is_reported_honestly(self):
        r = assess(changes_z={"spx_pct": 2.0})
        self.assertLess(r.coverage, 0.15)
        self.assertTrue(any("Thin panel" in c for c in r.caveats))

    def test_z_contributions_are_clamped(self):
        r = assess(changes_z={"spx_pct": 99.0})
        self.assertLessEqual(r.score, 100.0)

    def test_sign_map_is_respected(self):
        risk_on = assess(changes_z={"vix": -2.0, "spx_pct": 2.0})
        risk_off = assess(changes_z={"vix": 2.0, "spx_pct": -2.0})
        self.assertEqual(risk_on.regime, RiskRegime.RISK_ON)
        self.assertEqual(risk_off.regime, RiskRegime.RISK_OFF)


class TestAnomaly(unittest.TestCase):
    def test_small_move_does_not_fire(self):
        self.assertIsNone(detect_anomaly("SPX", ANOMALY_Z - 0.1))

    def test_large_unexplained_move_fires_without_naming_a_cause(self):
        f = detect_anomaly("USDJPY", -3.5)
        self.assertIn("cause NOT identified", f.verdict)
        self.assertGreater(len(f.candidate_explanations), 3)

    def test_candidate_weights_sum_to_one(self):
        f = detect_anomaly("USDJPY", -3.5, correlated_assets_moved=True, volume_z=2.5)
        self.assertAlmostEqual(sum(p for _, p in f.candidate_explanations), 1.0, places=6)

    def test_headline_present_changes_the_verdict(self):
        f = detect_anomaly("SPX", 3.0, headline_found=True)
        self.assertIn("IDENTIFIED HEADLINE", f.verdict)

    def test_instruction_demands_a_primary_source(self):
        self.assertIn("primary", detect_anomaly("BTC", 4.0).instruction)


if __name__ == "__main__":
    unittest.main()
