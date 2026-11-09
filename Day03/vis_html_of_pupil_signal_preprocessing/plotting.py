"""Static matplotlib figures for each preprocessing stage."""

from __future__ import annotations

import warnings
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.collections import LineCollection  # noqa: E402

from .preprocessing import PreprocessingParams, Stage  # noqa: E402

# Reference categorical palette, fixed order (first 3 validated for all pairs).
SUBJECT_COLORS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100",
                  "#e87ba4", "#008300", "#6250d6", "#e34948"]
OTHER_COLOR = "#8a8984"
TRIAL_COLOR = "#8a8984"
MEAN_COLOR = "#2a78d6"
EXCLUDED_COLOR = "#d03b3b"
SURFACE = "#fcfcfb"
TEXT = "#0b0b0b"
MUTED = "#52514e"
GRID = "#e4e3df"

METRIC_LABELS = {
    "baseline_psc": "baseline (mean −500…0 ms, % signal change)",
    "dilation_psc": "dilation (peak − baseline, % signal change)",
}

FIGSIZE = (4.6, 3.2)
DPI = 110


def subject_color(i: int) -> str:
    return SUBJECT_COLORS[i] if i < len(SUBJECT_COLORS) else OTHER_COLOR


def _new_axes():
    fig, ax = plt.subplots(figsize=FIGSIZE, dpi=DPI)
    fig.patch.set_facecolor(SURFACE)
    ax.set_facecolor(SURFACE)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(MUTED)
        ax.spines[side].set_linewidth(0.8)
    ax.tick_params(colors=MUTED, labelsize=8, width=0.8)
    ax.grid(axis="y", color=GRID, linewidth=0.7)
    ax.set_axisbelow(True)
    return fig, ax


def _finish(fig, ax, path: Path, title: str, x_label: str, y_label: str) -> None:
    ax.set_title(title, fontsize=10, color=TEXT, loc="left")
    ax.set_xlabel(x_label, fontsize=9, color=MUTED)
    ax.set_ylabel(y_label, fontsize=9, color=MUTED)
    if ax.get_legend_handles_labels()[0]:
        ax.legend(fontsize=7, frameon=False, labelcolor=TEXT, loc="best")
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, facecolor=SURFACE)
    plt.close(fig)


def _nanmean_rows(values: np.ndarray) -> np.ndarray:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        return np.nanmean(values, axis=1)


def _add_trials(ax, t, values, color, alpha, width, label=None) -> None:
    if values.shape[1] == 0:
        return
    segments = [np.column_stack([t, values[:, j]]) for j in range(values.shape[1])]
    ax.add_collection(LineCollection(segments, colors=color, linewidths=width,
                                     alpha=alpha, label=label))


def _set_limits(ax, t, values) -> None:
    finite = values[np.isfinite(values)]
    if finite.size:
        lo, hi = np.percentile(finite, [0, 100])
        pad = 0.05 * (hi - lo or 1.0)
        ax.set_ylim(lo - pad, hi + pad)
    ax.set_xlim(t.min(), t.max())


def _onset_line(ax) -> None:
    ax.axvline(0, color=MUTED, linewidth=0.8, linestyle="--", zorder=1)


# --------------------------------------------------------------------------- #
# Per-subject stage figure
# --------------------------------------------------------------------------- #
def plot_stage(stage: Stage, subject: str, path: Path, params: PreprocessingParams,
               excluded: pd.Series | None = None) -> None:
    title = f"s{subject} · {stage.title}"
    if stage.kind == "metrics":
        _plot_metric_hist(stage.data[stage.metric], title, path, METRIC_LABELS[stage.metric])
        return

    fig, ax = _new_axes()
    data = stage.data
    t = data.index.to_numpy(dtype=float)
    values = data.to_numpy(dtype=float)

    if stage.kind == "exclusion" and excluded is not None:
        mask = excluded.reindex(data.columns).fillna(False).to_numpy(dtype=bool)
        _add_trials(ax, t, values[:, ~mask], TRIAL_COLOR, 0.15, 0.4,
                    f"included (n={int((~mask).sum())})")
        _add_trials(ax, t, values[:, mask], EXCLUDED_COLOR, 0.8, 0.8,
                    f"excluded (n={int(mask.sum())})")
        mean = _nanmean_rows(values[:, ~mask])
    else:
        _add_trials(ax, t, values, TRIAL_COLOR, 0.12, 0.4,
                    f"single trials (n={values.shape[1]})")
        mean = _nanmean_rows(values)

    if stage.kind == "baseline":
        b0, b1 = params.baseline_window_ms
        ax.axvspan(b0, b1, color=MUTED, alpha=0.12, linewidth=0, label="baseline window")

    ax.plot(t, mean, color=MEAN_COLOR, linewidth=2, label="mean", zorder=3)
    _onset_line(ax)
    _set_limits(ax, t, values)
    _finish(fig, ax, path, title, "time from event onset (ms)", stage.y_label)


def _plot_metric_hist(values: pd.Series, title: str, path: Path, x_label: str) -> None:
    fig, ax = _new_axes()
    values = values.dropna().to_numpy()
    if values.size:
        ax.hist(values, bins=30, color=MEAN_COLOR, edgecolor=SURFACE, linewidth=1)
        median = float(np.median(values))
        ax.axvline(median, color=TEXT, linewidth=1.2, label=f"median = {median:.1f}%")
    _finish(fig, ax, path, title, x_label, "trials")


# --------------------------------------------------------------------------- #
# All-subjects (aggregate) stage figure
# --------------------------------------------------------------------------- #
def plot_stage_all_subjects(stages: list[Stage], subjects: list[str],
                            excluded: list[pd.Series], path: Path,
                            params: PreprocessingParams) -> None:
    """One line (trial mean) per subject for a given stage."""
    first = stages[0]
    title = f"All subjects · {first.title}"
    fig, ax = _new_axes()

    if first.kind == "metrics":
        col = first.metric
        all_vals = np.concatenate([s.data[col].dropna().to_numpy() for s in stages])
        bins = np.histogram_bin_edges(all_vals, bins=30) if all_vals.size else 30
        for i, (stage, subject) in enumerate(zip(stages, subjects)):
            ax.hist(stage.data[col].dropna(), bins=bins, histtype="step",
                    linewidth=2, color=subject_color(i), label=f"s{subject}")
        _finish(fig, ax, path, title, METRIC_LABELS[col], "trials")
        return

    if first.kind == "baseline":
        b0, b1 = params.baseline_window_ms
        ax.axvspan(b0, b1, color=MUTED, alpha=0.12, linewidth=0, label="baseline window")

    means = []
    for i, (stage, subject, excl) in enumerate(zip(stages, subjects, excluded)):
        data = stage.data
        if stage.kind == "exclusion":
            data = data.loc[:, ~excl.reindex(data.columns).fillna(False).to_numpy(dtype=bool)]
        t = data.index.to_numpy(dtype=float)
        mean = _nanmean_rows(data.to_numpy(dtype=float))
        means.append(mean)
        ax.plot(t, mean, color=subject_color(i), linewidth=2, label=f"s{subject}")
    _onset_line(ax)
    _set_limits(ax, t, np.column_stack(means))
    _finish(fig, ax, path, title, "time from event onset (ms)",
            first.y_label + " — trial mean")
