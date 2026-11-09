"""Pupil-signal preprocessing, following Algermissen & den Ouden (2024).

Every function works on a *segment table*: a DataFrame whose index is
``time_from_event_start_ms`` (one row per sample) and whose columns are trial
numbers (``trialnr``). Functions never modify their input; they return new
tables so that every intermediate stage can be kept, saved and plotted.

Pipeline (see :func:`run_pipeline`):

1. raw signal
2. mark missing samples (EyeLink writes 0 when the pupil is lost)
   -- blink/saccade padding (150 ms / 20 ms) is NOT applied yet: it needs the
   EyeLink event table, which is not part of the current data.
3. remove abnormally fast pupil changes (|z(first derivative)| > 2, merge marks
   closer than 10 samples)
4. linear interpolation of missing/removed samples
5. 6 Hz low-pass, 3rd-order Butterworth (zero-phase)
6. trim 250 ms at both edges (filter edge artefacts)
7. percent signal change around the grand mean of each 64-trial block
8. exclude trials with > 50 % missing/interpolated samples
9. baseline (mean of 500 ms before onset), peak (max after onset), dilation
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from scipy.signal import butter, filtfilt


@dataclass(frozen=True)
class PreprocessingParams:
    """All tunable numbers of the pipeline in one place."""

    sampling_rate_hz: float = 1000.0
    derivative_z_threshold: float = 2.0
    derivative_merge_samples: int = 10
    lowpass_cutoff_hz: float = 6.0
    lowpass_order: int = 3
    edge_trim_ms: float = 250.0
    trials_per_block: int = 64
    max_missing_fraction: float = 0.5
    baseline_window_ms: tuple[float, float] = (-500.0, 0.0)
    peak_window_start_ms: float = 0.0


@dataclass
class Stage:
    """One preprocessing stage: its data plus what is needed to show it."""

    number: int
    key: str
    title: str
    description: str
    data: pd.DataFrame
    y_label: str
    kind: str = "timecourse"  # "timecourse" | "exclusion" | "baseline" | "metrics"

    @property
    def slug(self) -> str:
        return f"{self.number:02d}_{self.key}"


@dataclass
class PipelineResult:
    subject: str
    stages: list[Stage]
    trial_metrics: pd.DataFrame  # one row per trial
    summary: dict = field(default_factory=dict)


# --------------------------------------------------------------------------- #
# Individual steps
# --------------------------------------------------------------------------- #
def mark_missing(segments: pd.DataFrame) -> pd.DataFrame:
    """Replace non-positive samples (EyeLink signal loss) with NaN."""
    return segments.where(segments > 0)


def fast_change_mask(
    signal: np.ndarray, z_threshold: float = 2.0, merge_samples: int = 10
) -> np.ndarray:
    """Boolean mask of samples to delete because the pupil changed too fast.

    The first derivative is z-standardised within the trial. A sample is
    marked when the change *into* it has |z| > ``z_threshold``. When two marks
    are fewer than ``merge_samples`` samples apart, everything between them is
    marked as well.
    """
    signal = np.asarray(signal, dtype=float)
    mask = np.zeros(signal.shape[0], dtype=bool)
    derivative = np.diff(signal)
    finite = np.isfinite(derivative)
    if finite.sum() < 2:
        return mask
    sd = derivative[finite].std()
    if sd == 0:
        return mask
    z = np.full_like(derivative, np.nan)
    z[finite] = (derivative[finite] - derivative[finite].mean()) / sd
    with np.errstate(invalid="ignore"):
        marks = np.flatnonzero(np.abs(z) > z_threshold) + 1
    mask[marks] = True
    if marks.size > 1:
        close = np.diff(marks) < merge_samples
        for start, stop in zip(marks[:-1][close], marks[1:][close]):
            mask[start : stop + 1] = True
    return mask


def remove_fast_changes(
    segments: pd.DataFrame, z_threshold: float = 2.0, merge_samples: int = 10
) -> pd.DataFrame:
    """Set samples flagged by :func:`fast_change_mask` to NaN, per trial."""
    values = segments.to_numpy(dtype=float, copy=True)
    for j in range(values.shape[1]):
        values[fast_change_mask(values[:, j], z_threshold, merge_samples), j] = np.nan
    return pd.DataFrame(values, index=segments.index, columns=segments.columns)


def interpolate_linear(segments: pd.DataFrame) -> pd.DataFrame:
    """Linearly interpolate NaNs over time; edges take the nearest valid value.

    Trials without any valid sample stay all-NaN.
    """
    values = segments.to_numpy(dtype=float, copy=True)
    x = np.arange(values.shape[0])
    for j in range(values.shape[1]):
        col = values[:, j]
        valid = np.isfinite(col)
        if valid.all() or not valid.any():
            continue
        col[~valid] = np.interp(x[~valid], x[valid], col[valid])
    return pd.DataFrame(values, index=segments.index, columns=segments.columns)


def lowpass_filter(
    segments: pd.DataFrame,
    cutoff_hz: float = 6.0,
    order: int = 3,
    sampling_rate_hz: float = 1000.0,
) -> pd.DataFrame:
    """Zero-phase Butterworth low-pass (``filtfilt``) along time, per trial."""
    b, a = butter(order, cutoff_hz, btype="low", fs=sampling_rate_hz)
    values = segments.to_numpy(dtype=float, copy=True)
    complete = np.isfinite(values).all(axis=0)
    if complete.any():
        values[:, complete] = filtfilt(b, a, values[:, complete], axis=0)
    return pd.DataFrame(values, index=segments.index, columns=segments.columns)


def trim_edges(segments: pd.DataFrame, trim_ms: float = 250.0) -> pd.DataFrame:
    """Drop the first and last ``trim_ms`` milliseconds of every trial."""
    t = segments.index.to_numpy()
    keep = (t >= t.min() + trim_ms) & (t <= t.max() - trim_ms)
    return segments.loc[keep]


def block_of_trial(trials: pd.Index, trials_per_block: int = 64) -> np.ndarray:
    """Block number (1-based) of each trial number (trials are 1-based)."""
    return (np.asarray(trials, dtype=int) - 1) // trials_per_block + 1


def percent_signal_change(
    segments: pd.DataFrame, trials_per_block: int = 64
) -> pd.DataFrame:
    """Convert to % change around the grand-mean pupil size of each block."""
    blocks = block_of_trial(segments.columns, trials_per_block)
    out = segments.copy()
    for block in np.unique(blocks):
        cols = segments.columns[blocks == block]
        grand_mean = np.nanmean(segments[cols].to_numpy())
        out[cols] = (segments[cols] - grand_mean) / grand_mean * 100.0
    return out


def trial_metrics(
    psc: pd.DataFrame,
    baseline_window_ms: tuple[float, float] = (-500.0, 0.0),
    peak_window_start_ms: float = 0.0,
) -> pd.DataFrame:
    """Per-trial baseline (mean in window), peak (max after onset), dilation."""
    t = psc.index.to_numpy()
    in_baseline = (t >= baseline_window_ms[0]) & (t < baseline_window_ms[1])
    in_peak = t >= peak_window_start_ms
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)  # all-NaN trials
        baseline = np.nanmean(psc.to_numpy()[in_baseline], axis=0)
        peak = np.nanmax(psc.to_numpy()[in_peak], axis=0)
    return pd.DataFrame(
        {"baseline_psc": baseline, "peak_psc": peak, "dilation_psc": peak - baseline},
        index=psc.columns,
    )


# --------------------------------------------------------------------------- #
# Full pipeline
# --------------------------------------------------------------------------- #
def run_pipeline(
    segments: pd.DataFrame,
    subject: str,
    params: PreprocessingParams = PreprocessingParams(),
) -> PipelineResult:
    """Run every step and keep each intermediate stage."""
    p = params
    raw = segments.astype(float)
    missing = mark_missing(raw)
    cleaned = remove_fast_changes(
        missing, p.derivative_z_threshold, p.derivative_merge_samples
    )
    interpolated = interpolate_linear(cleaned)
    filtered = lowpass_filter(
        interpolated, p.lowpass_cutoff_hz, p.lowpass_order, p.sampling_rate_hz
    )
    trimmed = trim_edges(filtered, p.edge_trim_ms)
    psc = percent_signal_change(trimmed, p.trials_per_block)

    # Missing/interpolated share per trial, within the analysed (trimmed) window.
    missing_frac = trim_edges(cleaned.isna(), p.edge_trim_ms).mean()
    excluded = missing_frac > p.max_missing_fraction
    included = psc.loc[:, ~excluded]

    metrics = trial_metrics(psc, p.baseline_window_ms, p.peak_window_start_ms)
    baseline_corrected = included - metrics.loc[included.columns, "baseline_psc"]

    metrics.insert(0, "block", block_of_trial(psc.columns, p.trials_per_block))
    metrics.insert(1, "zero_fraction_raw", trim_edges(missing.isna(), p.edge_trim_ms).mean())
    metrics.insert(2, "missing_fraction", missing_frac)
    metrics.insert(3, "excluded", excluded)
    metrics.insert(0, "subject", subject)
    metrics.index.name = "trialnr"

    n_trials = raw.shape[1]
    zero_pct = 100 * missing.isna().to_numpy().mean()
    total_pct = 100 * cleaned.isna().to_numpy().mean()
    lo, hi = trimmed.index.min(), trimmed.index.max()
    b0, b1 = p.baseline_window_ms

    stages = [
        Stage(1, "raw", "Raw signal",
              "Pupil size as recorded, every trial overlaid. Drops to 0 are "
              "samples where the tracker lost the pupil (blinks, signal loss).",
              raw, "pupil size (a.u.)"),
        Stage(2, "missing_marked", "Missing samples marked",
              f"Samples equal to 0 set to missing ({zero_pct:.1f}% of samples). "
              "Blink/saccade padding (150/20 ms) is skipped: no EyeLink event "
              "data yet.",
              missing, "pupil size (a.u.)"),
        Stage(3, "fast_changes_removed", "Fast changes removed",
              f"Samples where |z(first derivative)| > {p.derivative_z_threshold:g} "
              f"deleted; marks < {p.derivative_merge_samples} samples apart "
              f"merged. Missing in total: {total_pct:.1f}%.",
              cleaned, "pupil size (a.u.)"),
        Stage(4, "interpolated", "Linear interpolation",
              "Missing and deleted samples filled by linear interpolation "
              "(edges: nearest valid sample).",
              interpolated, "pupil size (a.u.)"),
        Stage(5, "lowpass", "Low-pass filter",
              f"{p.lowpass_cutoff_hz:g} Hz low-pass, order-{p.lowpass_order} "
              "Butterworth, zero-phase (forward-backward).",
              filtered, "pupil size (a.u.)"),
        Stage(6, "trimmed", "Edges trimmed",
              f"First and last {p.edge_trim_ms:g} ms removed to drop filter "
              f"edge artefacts; window now {lo:g} to {hi:g} ms.",
              trimmed, "pupil size (a.u.)"),
        Stage(7, "percent_signal_change", "Percent signal change",
              "Each sample expressed as % change from the grand-mean pupil size "
              f"of its block ({p.trials_per_block} trials per block).",
              psc, "pupil (% signal change)"),
        Stage(8, "trial_exclusion", "Trial exclusion",
              f"Trials with > {p.max_missing_fraction:.0%} missing/interpolated "
              f"samples excluded: {int(excluded.sum())} of {n_trials} trials.",
              psc, "pupil (% signal change)", kind="exclusion"),
        Stage(9, "baseline_corrected", "Baseline corrected",
              f"Included trials minus their baseline (mean of {b0:g} to "
              f"{b1:g} ms). Peak = maximum from {p.peak_window_start_ms:g} ms "
              f"to {hi:g} ms.",
              baseline_corrected, "pupil (% change from baseline)", kind="baseline"),
        Stage(10, "dilation", "Trial-by-trial dilation",
              "Distribution over included trials of dilation = peak minus "
              "baseline.",
              metrics.loc[~metrics["excluded"]], "trials", kind="metrics"),
    ]

    summary = {
        "subject": subject,
        "n_trials": n_trials,
        "zero_samples_pct": round(zero_pct, 2),
        "fast_change_samples_pct": round(total_pct - zero_pct, 2),
        "missing_total_pct": round(total_pct, 2),
        "n_excluded": int(excluded.sum()),
        "mean_baseline_psc": round(float(metrics.loc[~excluded, "baseline_psc"].mean()), 3),
        "mean_dilation_psc": round(float(metrics.loc[~excluded, "dilation_psc"].mean()), 3),
    }
    return PipelineResult(subject, stages, metrics, summary)
