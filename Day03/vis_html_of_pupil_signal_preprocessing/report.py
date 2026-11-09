"""HTML report: rows = subjects (aggregate row first), columns = stages."""

from __future__ import annotations

import html
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

import pandas as pd

from .preprocessing import PreprocessingParams, Stage

CSS = """
:root {
  --bg: #f6f5f2; --surface: #fcfcfb; --border: #dcdbd6;
  --text: #0b0b0b; --text-2: #52514e; --accent: #2a78d6;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --bg: #121211; --surface: #1a1a19; --border: #3a3936;
    --text: #f0efec; --text-2: #c3c2b7; --accent: #3987e5;
  }
}
:root[data-theme="dark"] {
  --bg: #121211; --surface: #1a1a19; --border: #3a3936;
  --text: #f0efec; --text-2: #c3c2b7; --accent: #3987e5;
}
* { box-sizing: border-box; }
body { margin: 0; padding: 24px 16px; background: var(--bg); color: var(--text);
  font: 14px/1.5 system-ui, -apple-system, "Segoe UI", sans-serif; }
h1 { font-size: 22px; margin: 0 0 4px; }
h2 { font-size: 16px; margin: 28px 0 8px; }
.meta { color: var(--text-2); margin: 0 0 16px; }
.cards { display: flex; flex-wrap: wrap; gap: 16px; }
.card { background: var(--surface); border: 1px solid var(--border);
  border-radius: 8px; padding: 12px 16px; max-width: 100%; overflow-x: auto; }
table.info { border-collapse: collapse; font-size: 13px; }
table.info th, table.info td { padding: 3px 10px; text-align: left;
  border-bottom: 1px solid var(--border); white-space: nowrap; }
table.info td.num { text-align: right; font-variant-numeric: tabular-nums; }
table.info th { color: var(--text-2); font-weight: 600; }
.grid-wrap { overflow: auto; max-height: 92vh; border: 1px solid var(--border);
  border-radius: 8px; background: var(--surface); }
table.grid { border-collapse: separate; border-spacing: 0; }
table.grid th, table.grid td { border-bottom: 1px solid var(--border);
  border-right: 1px solid var(--border); padding: 8px; vertical-align: top;
  background: var(--surface); }
table.grid thead th { position: sticky; top: 0; z-index: 2; width: 360px;
  min-width: 360px; text-align: left; font-weight: 400; }
table.grid thead th b { display: block; font-size: 14px; }
table.grid thead th span { color: var(--text-2); font-size: 12px; }
table.grid .rowhead { position: sticky; left: 0; z-index: 1; min-width: 110px;
  font-weight: 600; }
table.grid thead th.rowhead { z-index: 3; }
table.grid .rowhead small { display: block; color: var(--text-2); font-weight: 400; }
table.grid tr.aggregate td, table.grid tr.aggregate th { border-bottom: 3px solid var(--border); }
table.grid img { width: 360px; height: auto; display: block; border-radius: 4px;
  background: #fcfcfb; }
.step { color: var(--accent); font-variant-numeric: tabular-nums; }
"""


def _rel(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _img(path: Path, root: Path, alt: str) -> str:
    src = html.escape(_rel(path, root))
    return f'<a href="{src}" target="_blank"><img src="{src}" alt="{html.escape(alt)}" loading="lazy"></a>'


def _table(df: pd.DataFrame) -> str:
    head = "".join(f"<th>{html.escape(str(c))}</th>" for c in df.columns)
    rows = []
    for _, row in df.iterrows():
        cells = []
        for v in row:
            cls = ' class="num"' if isinstance(v, (int, float)) and not isinstance(v, bool) else ""
            cells.append(f"<td{cls}>{html.escape(str(v))}</td>")
        rows.append("<tr>" + "".join(cells) + "</tr>")
    return f'<table class="info"><thead><tr>{head}</tr></thead><tbody>{"".join(rows)}</tbody></table>'


def build_report(
    out_dir: Path,
    dataset_name: str,
    stage_templates: list[Stage],
    subjects: list[str],
    plot_paths: dict[str, dict[str, Path]],  # row key -> stage slug -> png
    summary: pd.DataFrame,
    params: PreprocessingParams,
) -> Path:
    """Write ``report.html`` into ``out_dir`` and return its path."""
    params_df = pd.DataFrame(
        [(k, str(v)) for k, v in asdict(params).items()], columns=["parameter", "value"]
    )

    header = '<th class="rowhead">Subject</th>' + "".join(
        f'<th><b><span class="step">{s.number}.</span> {html.escape(s.title)}</b>'
        f"<span>{html.escape(_generic_description(s))}</span></th>"
        for s in stage_templates
    )

    body_rows = []
    rows = [("all", "All subjects", "trial means, one line per subject")] + [
        (s, f"s{s}", _subject_note(summary, s)) for s in subjects
    ]
    for key, label, note in rows:
        cells = [f'<th class="rowhead">{html.escape(label)}<small>{html.escape(note)}</small></th>']
        for stage in stage_templates:
            png = plot_paths[key][stage.slug]
            cells.append(f"<td>{_img(png, out_dir, f'{label} – {stage.title}')}</td>")
        cls = ' class="aggregate"' if key == "all" else ""
        body_rows.append(f"<tr{cls}>" + "".join(cells) + "</tr>")

    doc = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Pupil Preprocessing Report</title>
<style>{CSS}</style>
</head>
<body>
<h1>Pupil signal preprocessing — {html.escape(dataset_name)}</h1>
<p class="meta">{len(subjects)} subjects · generated {datetime.now():%Y-%m-%d %H:%M} ·
pipeline after Algermissen &amp; den Ouden (2024). Blinks and saccades from the EyeLink
event tables (01_blinks, 01_saccades), trial onsets and blocks from 01_trials.
Click any plot to open it full size.</p>

<h2>Overview</h2>
<div class="cards">
  <div class="card"><b>Per-subject summary</b>{_table(summary)}</div>
  <div class="card"><b>Parameters</b>{_table(params_df)}</div>
</div>

<h2>Preprocessing stages</h2>
<p class="meta">Rows: subjects ordered by task accuracy, highest first (first row aggregates
all subjects). Columns: preprocessing
stages in order. Grey = single trials, blue = trial mean, dashed line = event onset.</p>
<div class="grid-wrap">
<table class="grid">
<thead><tr>{header}</tr></thead>
<tbody>{"".join(body_rows)}</tbody>
</table>
</div>
</body>
</html>
"""
    path = out_dir / "report.html"
    path.write_text(doc, encoding="utf-8")
    return path


def _generic_description(stage: Stage) -> str:
    """Column-header text: the stage description without subject-specific numbers."""
    generic = {
        "blinks_removed": "EyeLink blinks ± padding (and any 0 samples) deleted.",
        "saccades_removed": "EyeLink saccades ± padding deleted.",
        "fast_changes_removed": "Samples with |z(first derivative)| > threshold deleted; "
                                "marks closer than the merge distance joined.",
        "trial_exclusion": "Trials with too many missing/interpolated samples "
                           "(red) are excluded from the following steps.",
        "baseline_corrected": "Included trials minus their baseline (shaded window).",
    }
    return generic.get(stage.key, stage.description)


def _subject_note(summary: pd.DataFrame, subject: str) -> str:
    row = summary.loc[summary["subject"] == subject].iloc[0]
    return (f"accuracy {row['accuracy_pct']:.1f}% · "
            f"{row['missing_total_pct']:.1f}% missing · "
            f"{row['n_excluded']}/{row['n_trials']} excluded")
