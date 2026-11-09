"""Unit tests for the preprocessing steps (run from Day03: python -m unittest)."""

import unittest

import numpy as np
import pandas as pd

from vis_html_of_pupil_signal_preprocessing.preprocessing import (
    PreprocessingParams,
    block_of_trial,
    event_mask,
    fast_change_mask,
    interpolate_linear,
    lowpass_filter,
    mark_missing,
    percent_signal_change,
    run_pipeline,
    trial_metrics,
    trim_edges,
)


def make_segments(n_time=2001, trials=(1, 2, 3), start_ms=-1000, seed=0):
    rng = np.random.default_rng(seed)
    t = np.arange(start_ms, start_ms + n_time)
    data = 1000 + np.cumsum(rng.normal(0, 0.5, (n_time, len(trials))), axis=0)
    df = pd.DataFrame(data, index=pd.Index(t, name="time_from_event_start_ms"),
                      columns=pd.Index(list(trials), name="trialnr"))
    return df


class TestSteps(unittest.TestCase):
    def test_mark_missing_turns_zeros_into_nan(self):
        df = pd.DataFrame({1: [5.0, 0.0, 3.0]})
        out = mark_missing(df)
        self.assertTrue(np.isnan(out.iloc[1, 0]))
        self.assertEqual(out.iloc[0, 0], 5.0)
        self.assertEqual(df.iloc[1, 0], 0.0)  # input untouched

    def test_fast_change_mask_flags_jump_and_merges_close_marks(self):
        x = np.ones(200)
        x[100:105] = 50.0  # jump up at 100, jump down at 105 (5 samples apart)
        mask = fast_change_mask(x, z_threshold=2, merge_samples=10)
        self.assertTrue(mask[100:106].all())
        self.assertEqual(mask.sum(), 6)

    def test_fast_change_mask_does_not_merge_distant_marks(self):
        x = np.ones(200)
        x[100:150] = 50.0  # marks 50 samples apart
        mask = fast_change_mask(x, z_threshold=2, merge_samples=10)
        self.assertTrue(mask[100] and mask[150])
        self.assertFalse(mask[101:150].any())

    def test_fast_change_mask_handles_all_nan(self):
        self.assertFalse(fast_change_mask(np.full(50, np.nan)).any())

    def test_interpolate_linear_fills_gaps_and_edges(self):
        df = pd.DataFrame({1: [np.nan, 1.0, np.nan, 3.0, np.nan], 2: [np.nan] * 5})
        out = interpolate_linear(df)
        np.testing.assert_allclose(out[1], [1.0, 1.0, 2.0, 3.0, 3.0])
        self.assertTrue(out[2].isna().all())

    def test_lowpass_removes_fast_oscillation_keeps_slow(self):
        t = np.arange(4000) / 1000
        slow, fast = np.sin(2 * np.pi * 1 * t), np.sin(2 * np.pi * 40 * t)
        out = lowpass_filter(pd.DataFrame({1: slow + fast}))[1].to_numpy()
        np.testing.assert_allclose(out[500:-500], slow[500:-500], atol=0.02)

    def test_trim_edges(self):
        df = make_segments(n_time=2001)  # -1000 .. 1000
        out = trim_edges(df, 250)
        self.assertEqual(out.index.min(), -750)
        self.assertEqual(out.index.max(), 750)

    def test_block_of_trial(self):
        np.testing.assert_array_equal(block_of_trial([1, 64, 65, 128, 129], 64), [1, 1, 2, 2, 3])

    def test_percent_signal_change_uses_block_grand_mean(self):
        df = pd.DataFrame({1: [90.0, 110.0], 2: [100.0, 100.0], 65: [200.0, 200.0]})
        out = percent_signal_change(df, 64)
        np.testing.assert_allclose(out[1], [-10.0, 10.0])
        np.testing.assert_allclose(out[65], [0.0, 0.0])

    def test_trial_metrics(self):
        t = np.arange(-500, 501)
        psc = pd.DataFrame({1: np.where(t < 0, 2.0, 5.0)}, index=t)
        m = trial_metrics(psc, (-500, 0), 0)
        self.assertAlmostEqual(m.loc[1, "baseline_psc"], 2.0)
        self.assertAlmostEqual(m.loc[1, "dilation_psc"], 3.0)


class TestPipeline(unittest.TestCase):
    def test_pipeline_excludes_mostly_missing_trial(self):
        df = make_segments(trials=(1, 2, 3))
        df.iloc[:1500, 2] = 0.0  # trial 3: 75% zeros
        result = run_pipeline(df, "99", PreprocessingParams())
        self.assertEqual(len(result.stages), 12)
        self.assertEqual([s.metric for s in result.stages[-2:]],
                         ["baseline_psc", "dilation_psc"])
        self.assertTrue(result.trial_metrics.loc[3, "excluded"])
        self.assertFalse(result.trial_metrics.loc[1, "excluded"])
        self.assertEqual(result.summary["n_excluded"], 1)
        final = next(s for s in result.stages if s.key == "baseline_corrected").data
        self.assertNotIn(3, final.columns)
        self.assertFalse(final.isna().any().any())

    def test_pipeline_removes_padded_blinks_and_saccades(self):
        df = make_segments(trials=(1, 2))  # time -1000 .. 1000
        onsets = pd.Series({1: 10_000, 2: 20_000})
        blinks = pd.DataFrame({"start_time": [10_000], "end_time": [10_100]})
        saccades = pd.DataFrame({"start_time": [20_500], "end_time": [20_510]})
        result = run_pipeline(df, "99", PreprocessingParams(), onsets=onsets,
                              blinks=blinks, saccades=saccades,
                              blocks=pd.Series({1: 7, 2: 7}))
        no_blinks = result.stages[1].data
        no_saccades = result.stages[2].data
        self.assertEqual(no_blinks[1].isna().sum(), 401)  # -150 .. 250 ms
        self.assertEqual(no_blinks[2].isna().sum(), 0)
        self.assertEqual(no_saccades[2].isna().sum(), 51)  # 480 .. 530 ms
        self.assertTrue((result.trial_metrics["block"] == 7).all())


class TestEventMask(unittest.TestCase):
    def test_event_mask_uses_onset_and_padding(self):
        df = make_segments(n_time=21, trials=(1, 2), start_ms=-10)  # -10 .. 10
        onsets = pd.Series({1: 1000, 2: 5000})
        events = pd.DataFrame({"start_time": [1002], "end_time": [1003]})
        mask = event_mask(df, onsets, events, padding_ms=2)
        self.assertEqual(mask[1][mask[1]].index.tolist(), [0, 1, 2, 3, 4, 5])
        self.assertFalse(mask[2].any())

    def test_event_mask_catches_event_outside_window_via_padding(self):
        df = make_segments(n_time=21, trials=(1,), start_ms=-10)
        onsets = pd.Series({1: 1000})
        long_before = pd.DataFrame({"start_time": [900, 950], "end_time": [985, 960]})
        mask = event_mask(df, onsets, long_before, padding_ms=10)
        self.assertEqual(mask[1][mask[1]].index.tolist(), [-10, -9, -8, -7, -6, -5])

    def test_event_mask_without_events_or_onset(self):
        df = make_segments(n_time=21, trials=(1,), start_ms=-10)
        events = pd.DataFrame({"start_time": [1000], "end_time": [1005]})
        self.assertFalse(event_mask(df, pd.Series({1: 1000}), None, 0).any().any())
        self.assertFalse(event_mask(df, pd.Series(dtype=float), events, 0).any().any())


if __name__ == "__main__":
    unittest.main()
