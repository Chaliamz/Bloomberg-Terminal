import unittest
from datetime import date

from macro.calendar_spec import (
    BY_CODE, INDICATORS, RELEASES, Recurrence, by_country, coverage_report, top_tier,
)


class TestCalendarSpec(unittest.TestCase):
    def test_codes_are_unique(self):
        codes = [r.code for r in RELEASES]
        self.assertEqual(len(codes), len(set(codes)))

    def test_required_regions_are_covered(self):
        cov = coverage_report()
        for region in ("United States", "Euro Area", "United Kingdom", "Japan", "China"):
            self.assertIn(region, cov)
        self.assertTrue(by_country("Canada") and by_country("Australia")
                        and by_country("Switzerland") and by_country("New Zealand"))

    def test_us_core_series_present(self):
        for code in ("US_CPI", "US_CORE_CPI", "US_PCE", "US_NFP", "US_UNEMP",
                     "US_AHE", "US_CLAIMS", "US_CONT_CLAIMS", "US_ISM_MFG",
                     "US_ISM_SVC", "US_RETAIL", "US_GDP", "US_DURABLES",
                     "US_JOLTS", "US_HOUSING", "US_IP", "US_TRADE", "US_AUCTION",
                     "FOMC_DECISION", "FOMC_MINUTES", "FED_BEIGE", "FED_SPEECH"):
            self.assertIn(code, BY_CODE, code)

    def test_every_indicator_has_a_valid_sign(self):
        for spec in INDICATORS.values():
            self.assertIn(spec.strength_sign, (-1, 0, 1))
            self.assertIn(spec.inflation_sign, (-1, 0, 1))

    def test_unemployment_and_claims_are_inverted(self):
        self.assertEqual(INDICATORS["US_U3"].strength_sign, -1)
        self.assertEqual(INDICATORS["US_IC"].strength_sign, -1)

    def test_no_release_carries_a_value(self):
        for r in RELEASES:
            for field in ("consensus", "previous", "actual", "forecast"):
                self.assertFalse(hasattr(r, field),
                                 f"{r.code} exposes a {field}: the calendar must "
                                 "carry semantics, never values")

    def test_agency_scheduled_releases_refuse_to_guess_dates(self):
        for r in RELEASES:
            if r.recurrence in (Recurrence.AGENCY_SCHEDULE, Recurrence.EVENT_DRIVEN):
                out = r.next_occurrences(date(2026, 5, 1))
                self.assertIsInstance(out, str)
                self.assertIn("UNKNOWN", out)

    def test_nfp_lands_on_a_first_friday(self):
        for dt in BY_CODE["US_NFP"].next_occurrences(date(2026, 1, 1), 6):
            self.assertEqual(dt.weekday(), 4)
            self.assertLessEqual(dt.day, 7)
            self.assertEqual(dt.strftime("%H:%M"), "08:30")

    def test_claims_land_on_thursdays(self):
        for dt in BY_CODE["US_CLAIMS"].next_occurrences(date(2026, 1, 1), 8):
            self.assertEqual(dt.weekday(), 3)

    def test_conference_board_lands_on_a_last_tuesday(self):
        import calendar
        for dt in BY_CODE["US_CONF"].next_occurrences(date(2026, 1, 1), 5):
            self.assertEqual(dt.weekday(), 1)
            last = calendar.monthrange(dt.year, dt.month)[1]
            self.assertGreater(dt.day + 7, last)

    def test_ism_manufacturing_is_a_first_business_day(self):
        for dt in BY_CODE["US_ISM_MFG"].next_occurrences(date(2026, 1, 1), 5):
            self.assertLess(dt.weekday(), 5)
            self.assertLessEqual(dt.day, 3)

    def test_every_release_carries_a_confidence_and_verify_target(self):
        for r in RELEASES:
            self.assertGreater(r.confidence, 0.0)
            self.assertLessEqual(r.confidence, 1.0)
            if r.recurrence is not Recurrence.EVENT_DRIVEN:
                self.assertTrue(r.verify, f"{r.code} has no verification URL")

    def test_top_tier_is_not_empty(self):
        self.assertGreaterEqual(len(top_tier()), 8)

    def test_timezones_resolve(self):
        for r in RELEASES:
            self.assertIsNotNone(r.zone)
            if r.clock:
                self.assertIsNotNone(r.local_time())


if __name__ == "__main__":
    unittest.main()
