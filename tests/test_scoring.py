import unittest

from macro.scoring import (
    EventClass, UrgencyBand, band, credibility, information_latency, score_event,
)
from macro.types import Tier, Verification


class TestScoring(unittest.TestCase):
    def test_bands(self):
        self.assertEqual(band(95), UrgencyBand.EXTREME)
        self.assertEqual(band(90), UrgencyBand.EXTREME)
        self.assertEqual(band(89.9), UrgencyBand.HIGH)
        self.assertEqual(band(75), UrgencyBand.HIGH)
        self.assertEqual(band(50), UrgencyBand.MEDIUM)
        self.assertEqual(band(25), UrgencyBand.LOW)
        self.assertEqual(band(0), UrgencyBand.INFORMATIONAL)

    def test_credibility_orders_tiers(self):
        p = credibility(Tier.PRIMARY, Verification.CONFIRMED)
        i = credibility(Tier.INSTITUTIONAL, Verification.REPORTED)
        s = credibility(Tier.SOCIAL, Verification.UNCONFIRMED)
        self.assertGreater(p, i)
        self.assertGreater(i, s)

    def test_confirmations_have_diminishing_returns_and_a_cap(self):
        a = credibility(Tier.SOCIAL, Verification.UNCONFIRMED, independent_confirmations=3)
        b = credibility(Tier.SOCIAL, Verification.UNCONFIRMED, independent_confirmations=50)
        self.assertEqual(a, b)

    def test_credibility_gates_priority(self):
        kw = dict(market_impact=95, surprise=80, information_latency_score=50,
                  expected_volatility=85, directional_confidence=60)
        good = score_event(credibility_score=100, **kw)
        bad = score_event(credibility_score=5, **kw)
        self.assertGreater(good.priority, bad.priority * 2.5)

    def test_priority_never_exceeds_100(self):
        s = score_event(market_impact=100, surprise=100, credibility_score=100,
                        information_latency_score=100, expected_volatility=100,
                        directional_confidence=100, minutes_to_event=1)
        self.assertLessEqual(s.priority, 100.0)
        self.assertLessEqual(s.urgency, 100.0)

    def test_proximity_lifts_urgency_not_priority(self):
        kw = dict(market_impact=80, surprise=50, credibility_score=90,
                  information_latency_score=20, expected_volatility=70,
                  directional_confidence=50)
        far = score_event(minutes_to_event=5000, **kw)
        near = score_event(minutes_to_event=5, **kw)
        self.assertAlmostEqual(far.priority, near.priority, places=6)
        self.assertGreater(near.urgency, far.urgency)

    def test_embargo_floors_latency(self):
        score, why = information_latency(EventClass.SCHEDULED_STATISTIC,
                                         embargoed_release=True, live_streamed=True)
        self.assertLessEqual(score, 20)
        self.assertIn("embargo", why)

    def test_unscheduled_events_score_higher_latency_than_scheduled(self):
        sched, _ = information_latency(EventClass.SCHEDULED_STATISTIC)
        emerg, _ = information_latency(EventClass.EMERGENCY_ACTION)
        self.assertGreater(emerg, sched)


if __name__ == "__main__":
    unittest.main()
