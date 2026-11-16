"""Pupil-signal preprocessing, following Algermissen & den Ouden (2024).

Every function works on a *segment table*: a DataFrame whose index is
``time_from_event_start_ms`` (one row per sample) and whose columns are trial
numbers (``trialnr``). Functions never modify their input; they return new
tables so that every intermediate stage can be kept, saved and plotted.

Pipeline (see :func:`run_pipeline`):

1. raw signal
2. remove blinks: EyeLink blink events padded by 150 ms on each side (plus
   any remaining 0 samples, which EyeLink writes when the pupil is lost)
3. remove saccades: EyeLink saccade events padded by 20 ms on each side
4. remove abnormally fast pupil changes (|z(first derivative)| > 2, merge marks
   closer than 10 samples)
5. linear interpolation of missing/removed samples
6. 6 Hz low-pass, 3rd-order Butterworth (zero-phase)
7. trim 250 ms at both edges (filter edge artefacts)
8. percent signal change around the grand mean of each block
9. exclude trials with > 50 % missing/interpolated samples
10. baseline (mean of 500 ms before onset), peak (max after onset), dilation

Event tables (blinks/saccades) use absolute EyeLink time. A segment sample at
``time_from_event_start_ms = t`` of a trial with onset ``T`` (e.g. its
``startmask``) has absolute time ``T + t``.
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
    blink_padding_ms: float = 150.0
    saccade_padding_ms: float = 20.0
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
    metric: str | None = None  # for kind="metrics": trial_metrics column to plot

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


def event_mask(
    segments: pd.DataFrame,
    onsets: pd.Series,
    events: pd.DataFrame | None,
    padding_ms: float,
) -> pd.DataFrame:
    """Boolean table (same shape as ``segments``): True inside a padded event.

    ``onsets`` maps trialnr -> absolute onset time of the segment's event.
    ``events`` has absolute ``start_time`` / ``end_time`` columns. A sample is
    marked when ``start_time - padding <= T + t <= end_time + padding``.
    Trials without a known onset, or no event table, are left unmarked.
    """
    mask = np.zeros(segments.shape, dtype=bool)
    if events is None or events.empty:
        return pd.DataFrame(mask, index=segments.index, columns=segments.columns)

    t = segments.index.to_numpy(dtype=float)
    order = np.argsort(events["start_time"].to_numpy())
    starts = events["start_time"].to_numpy(dtype=float)[order] - padding_ms
    ends = events["end_time"].to_numpy(dtype=float)[order] + padding_ms
    # Running max of ends lets us find every event overlapping a window,
    # even when a long event starts long before the window.
    max_end = np.maximum.accumulate(ends)
    onset_values = onsets.reindex(segments.columns).to_numpy(dtype=float)

    for j, onset in enumerate(onset_values):
        if not np.isfinite(onset):
            continue
        abs_t = onset + t
        first = np.searchsorted(max_end, abs_t[0], side="left")
        last = np.searchsorted(starts, abs_t[-1], side="right")
        for start, end in zip(starts[first:last], ends[first:last]):
            lo = np.searchsorted(abs_t, start, side="left")
            hi = np.searchsorted(abs_t, end, side="right")
            mask[lo:hi, j] = True
    return pd.DataFrame(mask, index=segments.index, columns=segments.columns)


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
    segments: pd.DataFrame,
    trials_per_block: int = 64,
    blocks: np.ndarray | None = None,
) -> pd.DataFrame:
    """Convert to % change around the grand-mean pupil size of each block.

    ``blocks`` gives the block of each column; if omitted it is derived from
    the trial number with ``trials_per_block``.
    """
    if blocks is None:
        blocks = block_of_trial(segments.columns, trials_per_block)
    blocks = np.asarray(blocks)
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
    onsets: pd.Series | None = None,
    blinks: pd.DataFrame | None = None,
    saccades: pd.DataFrame | None = None,
    blocks: pd.Series | None = None,
) -> PipelineResult:
    """Run every step and keep each intermediate stage.

    ``onsets`` (trialnr -> absolute onset time), ``blinks`` and ``saccades``
    (EyeLink event tables) enable the blink/saccade stages; without them those
    stages only mark 0-samples. ``blocks`` (trialnr -> block) overrides the
    block number derived from ``params.trials_per_block``.
    """
    p = params
    if onsets is None:
        onsets = pd.Series(dtype=float)
    raw = segments.astype(float)

    in_blink = event_mask(raw, onsets, blinks, p.blink_padding_ms)
    no_blinks = mark_missing(raw).mask(in_blink)
    in_saccade = event_mask(raw, onsets, saccades, p.saccade_padding_ms)
    no_saccades = no_blinks.mask(in_saccade)
    cleaned = remove_fast_changes(
        no_saccades, p.derivative_z_threshold, p.derivative_merge_samples
    )
    interpolated = interpolate_linear(cleaned)
    filtered = lowpass_filter(
        interpolated, p.lowpass_cutoff_hz, p.lowpass_order, p.sampling_rate_hz
    )
    trimmed = trim_edges(filtered, p.edge_trim_ms)
    if blocks is not None:
        block_ids = blocks.reindex(trimmed.columns).to_numpy()
    else:
        block_ids = block_of_trial(trimmed.columns, p.trials_per_block)
    psc = percent_signal_change(trimmed, blocks=block_ids)

    # Shares per trial, within the analysed (trimmed) window.
    def share(mask: pd.DataFrame) -> pd.Series:
        return trim_edges(mask, p.edge_trim_ms).mean()

    missing_frac = share(cleaned.isna())
    excluded = missing_frac > p.max_missing_fraction
    included = psc.loc[:, ~excluded]

    metrics = trial_metrics(psc, p.baseline_window_ms, p.peak_window_start_ms)
    baseline_corrected = included - metrics.loc[included.columns, "baseline_psc"]

    metrics.insert(0, "block", block_ids)
    metrics.insert(1, "blink_fraction", share(no_blinks.isna()))
    metrics.insert(2, "saccade_fraction", share(no_saccades.isna() & no_blinks.notna()))
    metrics.insert(3, "missing_fraction", missing_frac)
    metrics.insert(4, "excluded", excluded)
    metrics.insert(0, "subject", subject)
    metrics.index.name = "trialnr"

    n_trials = raw.shape[1]
    blink_pct = 100 * no_blinks.isna().to_numpy().mean()
    sacc_pct = 100 * no_saccades.isna().to_numpy().mean() - blink_pct
    total_pct = 100 * cleaned.isna().to_numpy().mean()
    fast_pct = total_pct - blink_pct - sacc_pct
    lo, hi = trimmed.index.min(), trimmed.index.max()
    b0, b1 = p.baseline_window_ms
    unit = "pupil size (a.u.)"

    stages = [
        Stage(1, "raw", "Raw signal",
              "Pupil size as recorded, every trial overlaid. Drops to 0 are "
              "samples where the tracker lost the pupil (blinks).",
              raw, unit),
        Stage(2, "blinks_removed", "Blinks removed",
              f"EyeLink blinks padded by {p.blink_padding_ms:g} ms before and "
              f"after, deleted together with any 0 samples ({blink_pct:.1f}% of "
              "samples).",
              no_blinks, unit),
        Stage(3, "saccades_removed", "Saccades removed",
              f"EyeLink saccades padded by {p.saccade_padding_ms:g} ms before and "
              f"after, deleted (+{sacc_pct:.1f}% of samples).",
              no_saccades, unit),
        Stage(4, "fast_changes_removed", "Fast changes removed",
              f"Samples where |z(first derivative)| > {p.derivative_z_threshold:g} "
              f"deleted; marks < {p.derivative_merge_samples} samples apart "
              f"merged (+{fast_pct:.1f}%). Missing in total: {total_pct:.1f}%.",
              cleaned, unit),
        Stage(5, "interpolated", "Linear interpolation",
              "Missing and deleted samples filled by linear interpolation "
              "(edges: nearest valid sample).",
              interpolated, unit),
        Stage(6, "lowpass", "Low-pass filter",
              f"{p.lowpass_cutoff_hz:g} Hz low-pass, order-{p.lowpass_order} "
              "Butterworth, zero-phase (forward-backward).",
              filtered, unit),
        Stage(7, "trimmed", "Edges trimmed",
              f"First and last {p.edge_trim_ms:g} ms removed to drop filter "
              f"edge artefacts; window now {lo:g} to {hi:g} ms.",
              trimmed, unit),
        Stage(8, "percent_signal_change", "Percent signal change",
              "Each sample expressed as % change from the grand-mean pupil size "
              "of its block.",
              psc, "pupil (% signal change)"),
        Stage(9, "trial_exclusion", "Trial exclusion",
              f"Trials with > {p.max_missing_fraction:.0%} missing/interpolated "
              f"samples excluded: {int(excluded.sum())} of {n_trials} trials.",
              psc, "pupil (% signal change)", kind="exclusion"),
        Stage(10, "baseline_corrected", "Baseline corrected",
              f"Included trials minus their baseline (mean of {b0:g} to "
              f"{b1:g} ms). Peak = maximum from {p.peak_window_start_ms:g} ms "
              f"to {hi:g} ms.",
              baseline_corrected, "pupil (% change from baseline)", kind="baseline"),
        Stage(11, "baseline", "Trial-by-trial baseline",
              f"Distribution over included trials of the baseline = mean pupil "
              f"from {b0:g} to {b1:g} ms (% signal change).",
              metrics.loc[~metrics["excluded"]], "trials", kind="metrics",
              metric="baseline_psc"),
        Stage(12, "dilation", "Trial-by-trial dilation",
              "Distribution over included trials of dilation = peak minus "
              "baseline.",
              metrics.loc[~metrics["excluded"]], "trials", kind="metrics",
              metric="dilation_psc"),
    ]

    summary = {
        "subject": subject,
        "n_trials": n_trials,
        "blink_samples_pct": round(blink_pct, 2),
        "saccade_samples_pct": round(sacc_pct, 2),
        "fast_change_samples_pct": round(fast_pct, 2),
        "missing_total_pct": round(total_pct, 2),
        "n_excluded": int(excluded.sum()),
        "mean_baseline_psc": round(float(metrics.loc[~excluded, "baseline_psc"].mean()), 3),
        "mean_dilation_psc": round(float(metrics.loc[~excluded, "dilation_psc"].mean()), 3),
    }
    return PipelineResult(subject, stages, metrics, summary)
