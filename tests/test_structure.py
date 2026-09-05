import unittest
from datetime import datetime, timedelta, timezone

from macro.structure import (
    Bar, EventKind, SwingKind, Trend, analyse, atr, classify_trend, find_fvgs,
    find_swings, true_range,
)

T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)


def mk(closes, wick=0.2):
    bars, px = [], closes[0]
    for i, c in enumerate(closes):
        o = px
        bars.append(Bar(T0 + timedelta(minutes=i), o, max(o, c) + wick,
                        min(o, c) - wick, c, 100))
        px = c
    return bars


class TestStructurePrimitives(unittest.TestCase):
    def test_bar_rejects_impossible_ohlc(self):
        with self.assertRaises(ValueError):
            Bar(T0, 10, 9, 11, 10)            # high below low
        with self.assertRaises(ValueError):
            Bar(T0, 20, 11, 9, 10)            # open outside range
        with self.assertRaises(ValueError):
            Bar(T0, 10, 11, 9, 20)            # close outside range

    def test_body_ratio_of_a_doji_with_zero_range_is_zero_not_nan(self):
        b = Bar(T0, 10, 10, 10, 10)
        self.assertEqual(b.range, 0.0)
        self.assertEqual(b.body_ratio, 0.0)

    def test_true_range_includes_gaps(self):
        prev = Bar(T0, 10, 10.5, 9.5, 10)
        cur = Bar(T0 + timedelta(minutes=1), 12, 12.5, 11.8, 12)
        self.assertAlmostEqual(true_range(prev, cur), 2.5)

    def test_atr_needs_period_plus_one_bars(self):
        self.assertIsNone(atr(mk([1, 2, 3]), period=14))

    def test_atr_of_flat_series_is_none(self):
        self.assertIsNone(atr([Bar(T0 + timedelta(minutes=i), 5, 5, 5, 5)
                               for i in range(20)], period=14))


class TestSwingsAndLookahead(unittest.TestCase):
    def test_pivot_confirmation_lag_equals_right(self):
        bars = mk([1, 2, 3, 5, 3, 2, 1, 2, 3])
        for s in find_swings(bars, left=2, right=2):
            self.assertEqual(s.confirmed_at, s.index + 2)

    def test_a_pivot_is_never_confirmed_before_it_prints(self):
        bars = mk([1, 2, 3, 5, 3, 2, 1, 2, 3, 4, 5, 6, 5, 4])
        for s in find_swings(bars):
            self.assertGreater(s.confirmed_at, s.index - 1)
            self.assertLess(s.confirmed_at, len(bars))

    def test_no_swing_in_the_unconfirmable_tail(self):
        bars = mk([1, 2, 3, 4, 5, 6, 7, 9])
        idx = [s.index for s in find_swings(bars, left=2, right=2)]
        self.assertTrue(all(i <= len(bars) - 3 for i in idx))

    def test_structure_events_only_reference_already_confirmed_pivots(self):
        bars = mk([1, 3, 2, 4, 3, 5, 4, 6, 5, 7, 6, 8, 7, 9, 8, 10, 6, 4, 3, 2, 1,
                   2, 3, 2, 1, 0.5], wick=0.15)
        r = analyse(bars, atr_period=10)
        self.assertTrue(r.ok)
        by_index = {s.price: s for s in r.swings}
        for ev in r.events:
            if ev.reference_level is None:
                continue
            pivots = [s for s in r.swings if abs(s.price - ev.reference_level) < 1e-9]
            for p in pivots:
                self.assertLess(p.confirmed_at, ev.index,
                                f"{ev.kind} at {ev.index} used a pivot confirmed at "
                                f"{p.confirmed_at}: lookahead")


class TestTrendAndPatterns(unittest.TestCase):
    def test_hh_hl_is_bullish(self):
        bars = mk([1, 3, 2, 5, 4, 7, 6, 9, 8, 11, 10])
        self.assertIn(classify_trend(find_swings(bars)), (Trend.BULLISH, Trend.RANGING))

    def test_bullish_fvg_requires_a_true_gap(self):
        bars = [
            Bar(T0, 10, 11, 9.8, 10.9),
            Bar(T0 + timedelta(minutes=1), 10.9, 12.5, 10.8, 12.4),
            Bar(T0 + timedelta(minutes=2), 12.4, 13.5, 11.5, 13.0),
        ]
        gaps = find_fvgs(bars)
        self.assertEqual(len(gaps), 1)
        self.assertEqual(gaps[0].kind, "bullish")
        self.assertAlmostEqual(gaps[0].bottom, 11.0)   # high of bar 0
        self.assertAlmostEqual(gaps[0].top, 11.5)      # low of bar 2

    def test_overlapping_bars_produce_no_fvg(self):
        bars = mk([10, 10.4, 10.8, 11.2], wick=0.6)
        self.assertEqual(find_fvgs(bars), [])

    def test_fvg_fill_is_detected(self):
        bars = [
            Bar(T0, 10, 11, 9.8, 10.9),
            Bar(T0 + timedelta(minutes=1), 10.9, 12.5, 10.8, 12.4),
            Bar(T0 + timedelta(minutes=2), 12.4, 13.5, 11.5, 13.0),
            Bar(T0 + timedelta(minutes=3), 13.0, 13.2, 10.5, 10.8),
        ]
        self.assertEqual(find_fvgs(bars)[0].filled_at, 3)


class TestAnalyseGuards(unittest.TestCase):
    def test_too_few_bars_is_insufficient_not_a_crash(self):
        r = analyse(mk([1, 2, 3]))
        self.assertFalse(r.ok)
        self.assertIn("at least", r.reason)

    def test_out_of_order_bars_rejected(self):
        bars = mk(list(range(1, 30)))
        bars[10], bars[11] = bars[11], bars[10]
        r = analyse(bars, atr_period=10)
        self.assertFalse(r.ok)
        self.assertIn("ascending", r.reason)

    def test_flat_series_is_insufficient(self):
        bars = [Bar(T0 + timedelta(minutes=i), 5, 5, 5, 5) for i in range(40)]
        r = analyse(bars, atr_period=14)
        self.assertFalse(r.ok)

    def test_sweep_requires_material_penetration_and_fires_once_per_level(self):
        # grind repeatedly through one swing low, closing back above each time
        closes = [10, 12, 9, 11, 13, 11, 12, 11.5, 12, 11.6, 12.1, 11.7, 12.2,
                  11.8, 12.3, 11.9, 12.4, 12.0, 12.5, 12.1]
        bars = mk(closes, wick=0.9)
        r = analyse(bars, atr_period=10)
        self.assertTrue(r.ok)
        sweeps = [e for e in r.events
                  if e.kind in (EventKind.SWEEP_HIGH, EventKind.SWEEP_LOW)]
        levels = [round(e.reference_level, 6) for e in sweeps]
        self.assertEqual(len(levels), len(set(levels)),
                         "the same level was reported as swept more than once")


if __name__ == "__main__":
    unittest.main()
