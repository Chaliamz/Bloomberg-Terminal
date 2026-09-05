import unittest

from macro.surprise import (
    BAND_MAJOR, Impulse, IndicatorSpec, SurpriseClass, evaluate,
    surprise_distribution,
)
from macro.types import UnitMismatch, observed, unknown

CPI = IndicatorSpec("CPI", "CPI y/y", "US", "pct_yoy", strength_sign=0, inflation_sign=1)
NFP = IndicatorSpec("NFP", "Nonfarm Payrolls", "US", "k_jobs", strength_sign=1,
                    inflation_sign=0, revision_prone=True)
U3 = IndicatorSpec("U3", "Unemployment Rate", "US", "pct", strength_sign=-1)
AHE = IndicatorSpec("AHE", "Avg Hourly Earnings", "US", "pct_mom",
                    strength_sign=1, inflation_sign=1)

HIST = [0.1, -0.1, 0.2, 0.0, -0.2, 0.1, 0.3, -0.1, 0.0, 0.1]


class TestSurprise(unittest.TestCase):
    def test_absolute_surprise_arithmetic(self):
        r = evaluate(CPI, observed(3.4, "pct_yoy"), observed(3.1, "pct_yoy"))
        self.assertAlmostEqual(r.absolute_surprise, 0.3, places=10)

    def test_zscore_uses_supplied_sigma_only(self):
        r = evaluate(CPI, observed(3.4, "pct_yoy"), observed(3.1, "pct_yoy"),
                     surprise_history=HIST)
        self.assertIsNotNone(r.standardized_surprise)
        self.assertEqual(r.sigma_sample, len(HIST))

    def test_no_history_means_no_zscore_ever(self):
        r = evaluate(CPI, observed(3.4, "pct_yoy"), observed(3.1, "pct_yoy"))
        self.assertIsNone(r.standardized_surprise)
        self.assertIsNone(r.sigma_used)
        self.assertTrue(any("no built-in sigma table" in n for n in r.notes))

    def test_short_history_rejected(self):
        r = evaluate(CPI, observed(3.4, "pct_yoy"), observed(3.1, "pct_yoy"),
                     surprise_history=[0.1, 0.0, -0.1])
        self.assertIsNone(r.standardized_surprise)
        self.assertTrue(any("too short" in n for n in r.notes))

    def test_zero_dispersion_history_suppresses_zscore(self):
        r = evaluate(CPI, observed(3.4, "pct_yoy"), observed(3.1, "pct_yoy"),
                     surprise_history=[0.0] * 10)
        self.assertIsNone(r.standardized_surprise)

    def test_unit_mismatch_between_actual_and_spec(self):
        r = evaluate(CPI, observed(0.3, "pct_mom"), observed(0.3, "pct_mom"))
        self.assertFalse(r.ok)
        self.assertIn("unit mismatch", r.reason)

    def test_unit_mismatch_between_sides_raises(self):
        with self.assertRaises(UnitMismatch):
            evaluate(CPI, observed(3.4, "pct_yoy"), observed(0.3, "pct_mom"))

    def test_missing_actual_is_insufficient_not_zero(self):
        r = evaluate(CPI, unknown("pct_yoy"), observed(3.1, "pct_yoy"))
        self.assertFalse(r.ok)
        self.assertIn("actual", r.missing)

    def test_higher_unemployment_is_a_weaker_growth_impulse(self):
        r = evaluate(U3, observed(4.5, "pct"), observed(4.1, "pct"),
                     surprise_history=[0.1, -0.1, 0.1, 0.0, -0.1, 0.1, 0.0, -0.1, 0.1, 0.0])
        self.assertEqual(r.impulse, Impulse.GROWTH_WEAKER)
        self.assertEqual(r.classification, SurpriseClass.MAJOR_POSITIVE)

    def test_dual_signed_indicator_is_mixed(self):
        r = evaluate(AHE, observed(0.5, "pct_mom"), observed(0.3, "pct_mom"),
                     surprise_history=HIST)
        self.assertEqual(r.impulse, Impulse.MIXED)

    def test_revision_is_surfaced(self):
        r = evaluate(NFP, observed(200, "k_jobs"), observed(190, "k_jobs"),
                     previous=observed(150, "k_jobs"),
                     revised_previous=observed(90, "k_jobs"))
        self.assertAlmostEqual(r.revision_delta, -60.0)
        self.assertTrue(any("revised" in n for n in r.notes))
        self.assertTrue(any("revision-prone" in n for n in r.notes))

    def test_momentum_uses_revised_previous_when_present(self):
        r = evaluate(NFP, observed(200, "k_jobs"), observed(190, "k_jobs"),
                     previous=observed(150, "k_jobs"),
                     revised_previous=observed(90, "k_jobs"))
        self.assertAlmostEqual(r.momentum_delta, 110.0)

    def test_zero_consensus_does_not_divide_by_zero(self):
        r = evaluate(CPI, observed(0.4, "pct_yoy"), observed(0.0, "pct_yoy"))
        self.assertTrue(r.ok)
        self.assertTrue(any("consensus is ~0" in n for n in r.notes))

    def test_distribution_refuses_without_sigma(self):
        d = surprise_distribution(CPI, observed(3.1, "pct_yoy"), None)
        self.assertTrue(all(v.startswith("UNKNOWN") for v in d.values()))

    def test_distribution_bands_are_symmetric_around_consensus(self):
        d = surprise_distribution(CPI, observed(3.0, "pct_yoy"), 0.2)
        self.assertIn(f"{3.0 - BAND_MAJOR * 0.2:.2f}", d["extreme"])
        self.assertIn(f"{3.0 + BAND_MAJOR * 0.2:.2f}", d["extreme"])


if __name__ == "__main__":
    unittest.main()
