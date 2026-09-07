"""The unattended-scan path.

A scheduled run appends here rather than editing Python, so this store is the
one place where an unsupervised process can put a number on the page. Every
guard that keeps the no-fabrication contract on that path is tested.
"""

import json
import os
import tempfile
import unittest

from macro import observe
from macro.live import PriceAnchor


class TestObservationStore(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.TemporaryDirectory()
        self.p = os.path.join(self.d.name, "obs.json")

    def tearDown(self):
        self.d.cleanup()

    def _add(self, **kw):
        base = dict(date="2026-09-05T12:00:00Z", price=80000.0,
                    source="Carrier", tier=3, path=self.p)
        base.update(kw)
        return observe.add(**base)

    def test_a_valid_observation_is_stored(self):
        ok, why = self._add()
        self.assertTrue(ok, why)
        self.assertEqual(len(observe.load(self.p)), 1)

    def test_source_and_tier_are_mandatory(self):
        self.assertFalse(self._add(source="   ")[0])
        self.assertFalse(self._add(tier=9)[0])
        self.assertFalse(self._add(tier=0)[0])
        self.assertEqual(observe.load(self.p), [])

    def test_a_future_stamp_is_refused(self):
        ok, why = self._add(date="2099-01-01T00:00:00Z")
        self.assertFalse(ok)
        self.assertIn("future", why)

    def test_non_finite_and_non_positive_prices_are_refused(self):
        for bad in (0, -1, float("nan"), float("inf"), float("-inf"), "abc", None):
            self.assertFalse(self._add(price=bad)[0], f"accepted {bad!r}")
        self.assertEqual(observe.load(self.p), [])

    def test_a_malformed_stamp_is_refused(self):
        for bad in ("2026-09-05", "yesterday", "2026-09-05T12:00:00"):
            self.assertFalse(self._add(date=bad)[0], bad)

    def test_rescanning_the_same_print_is_a_no_op(self):
        self.assertTrue(self._add()[0])
        for _ in range(5):
            ok, why = self._add()
            self.assertFalse(ok)
            self.assertEqual(why, "already stored")
        self.assertEqual(len(observe.load(self.p)), 1)

    def test_the_same_instant_from_a_second_carrier_is_kept(self):
        self.assertTrue(self._add()[0])
        self.assertTrue(self._add(source="Other carrier", price=80010.0)[0])
        self.assertEqual(len(observe.load(self.p)), 2)

    def test_the_store_stays_sorted(self):
        for stamp in ("2026-09-05T12:00:00Z", "2026-09-01T09:00:00Z",
                      "2026-09-03T18:30:00Z"):
            self._add(date=stamp, source="C" + stamp[-6:])
        dates = [r["date"] for r in observe.load(self.p)]
        self.assertEqual(dates, sorted(dates))

    def test_a_corrupt_store_is_empty_not_fatal(self):
        for junk in ("{not json", "{}", "[1,2,3]", ""):
            with open(self.p, "w") as fh:
                fh.write(junk)
            self.assertEqual(observe.load(self.p), [])

    def test_a_row_missing_provenance_is_dropped_on_read(self):
        with open(self.p, "w") as fh:
            json.dump([{"date": "2026-09-05T12:00:00Z", "price": 1.0},
                       {"date": "2026-09-05T13:00:00Z", "price": 2.0,
                        "source": "Good", "tier": 2}], fh)
        rows = observe.load(self.p)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["source"], "Good")

    def test_the_write_is_atomic(self):
        self._add()
        self.assertFalse(os.path.exists(self.p + ".tmp"))

    def test_merge_keeps_the_baseline_and_adds_the_scan(self):
        base = [PriceAnchor(date="2026-09-01T12:00:00Z", price=78154.66,
                            source="Fortune", tier=3)]
        self._add(date="2026-09-05T12:00:00Z", source="Later scan")
        out = observe.merge(base, self.p)
        self.assertEqual(len(out), 2)
        self.assertEqual([a.date for a in out], sorted(a.date for a in out))

    def test_merge_never_duplicates_the_baseline(self):
        base = [PriceAnchor(date="2026-09-05T12:00:00Z", price=80000.0,
                            source="Carrier", tier=3)]
        self._add()                       # same (date, source) as the baseline
        self.assertEqual(len(observe.merge(base, self.p)), 1)

    def test_an_empty_store_changes_nothing(self):
        base = [PriceAnchor(date="2026-09-01T12:00:00Z", price=1.0,
                            source="S", tier=3)]
        self.assertEqual(len(observe.merge(base, self.p)), 1)


if __name__ == "__main__":
    unittest.main()


class TestTheStoreSurvivesAFreshClone(unittest.TestCase):
    """A scheduled run works from a clone. If the store is gitignored, every run
    starts empty and the unattended refresh accumulates nothing, for ever, with
    no error anywhere. It was ignored; this is the guard."""

    def _ignored(self, path):
        import subprocess
        r = subprocess.run(["git", "check-ignore", "-q", path],
                           capture_output=True,
                           cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        if r.returncode not in (0, 1):
            self.skipTest("git unavailable or not a repository")
        return r.returncode == 0

    def test_the_observation_store_is_not_ignored(self):
        self.assertFalse(self._ignored("state/observations.json"),
                         "the observation store is gitignored: a scheduled run "
                         "would clone an empty store and lose every accumulated "
                         "observation")

    def test_the_derived_snapshot_cache_is_still_ignored(self):
        self.assertTrue(self._ignored("state/snapshot.json"),
                        "snapshot.json is a derived cache and must not be tracked")
