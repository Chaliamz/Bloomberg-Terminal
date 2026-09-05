import unittest
from datetime import datetime, timedelta, timezone

from macro.noise import filter_item, jaccard
from macro.sources import classify_domain, confirm, make_source
from macro.types import Tier, Verification

NOW = datetime(2026, 3, 2, 12, 0, tzinfo=timezone.utc)


class TestTiering(unittest.TestCase):
    def test_known_domains(self):
        self.assertEqual(classify_domain("https://www.federalreserve.gov/x"), Tier.PRIMARY)
        self.assertEqual(classify_domain("reuters.com"), Tier.INSTITUTIONAL)
        self.assertEqual(classify_domain("https://x.com/a"), Tier.SOCIAL)
        self.assertEqual(classify_domain("random-blog.io"), Tier.UNKNOWN)

    def test_subdomains_inherit(self):
        self.assertEqual(classify_domain("https://apps.bea.gov/iTable"), Tier.PRIMARY)
        self.assertEqual(classify_domain("https://markets.ft.com/x"), Tier.INSTITUTIONAL)

    def test_generic_gov_suffix(self):
        self.assertEqual(classify_domain("https://data.somestate.gov/x"), Tier.PRIMARY)

    def test_lookalike_domain_is_not_promoted(self):
        self.assertEqual(classify_domain("https://reuters.com.evil.io/x"), Tier.UNKNOWN)


class TestConfirmation(unittest.TestCase):
    def test_no_sources_is_unconfirmed(self):
        r = confirm("claim", [])
        self.assertEqual(r.verification, Verification.UNCONFIRMED)
        self.assertEqual(r.credibility_score, 0.0)

    def test_primary_document_confirms(self):
        r = confirm("FOMC held rates", [
            make_source("Fed", "https://www.federalreserve.gov/x",
                        published_at=NOW, is_primary_document=True)])
        self.assertEqual(r.verification, Verification.CONFIRMED)

    def test_many_social_copies_are_one_source(self):
        r = confirm("rumour", [
            make_source(f"@a{i}", f"https://x.com/a{i}", published_at=NOW)
            for i in range(6)])
        self.assertEqual(r.independent_sources, 1)
        self.assertEqual(r.verification, Verification.UNCONFIRMED)
        self.assertTrue(any("single host" in f for f in r.misinformation_flags))

    def test_missing_timestamps_flagged(self):
        r = confirm("x", [make_source("Reuters", "https://reuters.com/a")])
        self.assertTrue(any("no publication timestamp" in f for f in r.misinformation_flags))

    def test_conflict_with_primary_is_disputed(self):
        r = confirm("x", [make_source("Blog", "https://blog.io/a", published_at=NOW)],
                    conflicts_with_primary=True)
        self.assertEqual(r.verification, Verification.DISPUTED)

    def test_recycled_news_flagged(self):
        r = confirm("x", [make_source("Reuters", "https://reuters.com/a",
                                      published_at=NOW - timedelta(days=9))],
                    claim_first_seen=NOW)
        self.assertTrue(any("recycled" in f for f in r.misinformation_flags))

    def test_contradicting_market_reaction_flagged(self):
        r = confirm("x", [make_source("Reuters", "https://reuters.com/a", published_at=NOW)],
                    market_reaction_contradicts=True)
        self.assertTrue(any("contradicts" in f for f in r.misinformation_flags))


class TestNoise(unittest.TestCase):
    def test_exact_duplicate_suppressed(self):
        v = filter_item("ECB cuts rates by 25bp", seen_headlines=["ECB cuts rates by 25bp"])
        self.assertFalse(v.keep)
        self.assertEqual(v.penalty, 0.0)

    def test_near_duplicate_suppressed(self):
        v = filter_item("ECB cuts its policy rate by 25 basis points today",
                        seen_headlines=["ECB cuts its policy rate by 25 basis points"])
        self.assertFalse(v.keep)

    def test_distinct_headline_kept(self):
        v = filter_item("BoJ raised policy rate to 0.75%", tier=Tier.PRIMARY,
                        changes_expectations=True)
        self.assertTrue(v.keep)

    def test_clickbait_penalised(self):
        v = filter_item("You won't believe what happens to gold next", tier=Tier.SOCIAL)
        self.assertLess(v.penalty, 0.5)

    def test_no_expectation_change_is_downgraded_hard(self):
        a = filter_item("Fed official repeats data-dependence", tier=Tier.INSTITUTIONAL,
                        changes_expectations=False)
        b = filter_item("Fed official repeats data-dependence", tier=Tier.INSTITUTIONAL,
                        changes_expectations=True)
        self.assertLess(a.penalty, b.penalty)

    def test_stale_item_penalised(self):
        v = filter_item("ECB announced a new facility", tier=Tier.PRIMARY,
                        published_at=NOW - timedelta(days=5), now=NOW)
        self.assertTrue(any("old news" in r for r in v.reasons))

    def test_jaccard_bounds(self):
        self.assertEqual(jaccard("a b c", "a b c"), 1.0)
        self.assertEqual(jaccard("a b", "c d"), 0.0)
        self.assertEqual(jaccard("", "abc"), 0.0)

    def test_naive_aware_datetime_mismatch_does_not_crash(self):
        v = filter_item("x", published_at=NOW, now=datetime(2026, 3, 2, 12, 0))
        self.assertTrue(any("mismatch" in r for r in v.reasons))


if __name__ == "__main__":
    unittest.main()
