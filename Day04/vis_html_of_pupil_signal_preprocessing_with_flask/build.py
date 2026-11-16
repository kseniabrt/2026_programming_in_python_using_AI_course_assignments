"""Run the Day03 preprocessing for every data folder and save the outputs.

Adapted from Day03's ``vis_html_of_pupil_signal_preprocessing/__main__.py``:
same pipeline, plots and static ``report.html``, written to the
``vis_html_of_pupil_signal_preprocessing_with_flask`` output folder. In
addition, a ``manifest.json`` describes the finished report (stages, subject
order, plot files, summary) so the web page can show it without re-running
the pipeline.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

import pandas as pd

from .plotting import plot_stage, plot_stage_all_subjects
from .preprocessing import PreprocessingParams, PipelineResult, run_pipeline
from .report import _generic_description, _subject_note, build_report

OUTPUT_FOLDER_NAME = "vis_html_of_pupil_signal_preprocessing_with_flask"
MANIFEST_NAME = "manifest.json"
SUBJECT_FILE = re.compile(r"^s_(?P<subject>.+?)_\.parquet$")
SEGMENT_FOLDER = re.compile(r"^02_.*_(?P<event>[a-z]+)_\d+_\d+ms$")


def find_segment_folders(data_dir: Path) -> list[Path]:
    """All ``02_*`` folders (one per segmentation) in the data folder."""
    return sorted(p for p in data_dir.glob("02_*") if p.is_dir())


def output_dir(folder: Path) -> Path:
    return folder / OUTPUT_FOLDER_NAME


def manifest_path(folder: Path) -> Path:
    return output_dir(folder) / MANIFEST_NAME


def find_subject_files(folder: Path) -> dict[str, Path]:
    """Map subject id -> parquet file for every ``s_<subject>_.parquet``."""
    files = {}
    for path in sorted(folder.glob("s_*_.parquet")):
        match = SUBJECT_FILE.match(path.name)
        if match:
            files[match["subject"]] = path
    return files


def onset_column(folder: Path) -> str:
    """Event the segments are aligned to, from the folder name.

    ``02_pupil_timecourse_startmask_1000_2966ms`` -> ``startmask``.
    """
    match = SEGMENT_FOLDER.match(folder.name)
    if not match:
        raise ValueError(f"Cannot read the onset event from folder name {folder.name!r}")
    return match["event"]


def read_optional(path: Path) -> pd.DataFrame | None:
    if path.exists():
        return pd.read_parquet(path)
    print(f"    [warn] missing {path.parent.name}/{path.name}")
    return None


def load_subject_context(data_dir: Path, subject: str, event: str) -> dict:
    """Onsets, blocks, blinks and saccades of one subject from the 01_ tables."""
    name = f"s_{subject}_.parquet"
    trials = read_optional(data_dir / "01_trials" / name)
    context = {
        "blinks": read_optional(data_dir / "01_blinks" / name),
        "saccades": read_optional(data_dir / "01_saccades" / name),
        "onsets": None,
        "blocks": None,
    }
    if trials is not None:
        trials = trials.set_index("trialnr")
        context["onsets"] = trials[event]
        context["blocks"] = trials["block"]
    return context


def subject_accuracy(data_dir: Path, subject: str) -> float:
    """Share of correct trials (mean of ``acc``) in 01_behavior; NaN if unknown."""
    behavior = read_optional(data_dir / "01_behavior" / f"s_{subject}_.parquet")
    if behavior is None or "acc" not in behavior:
        return float("nan")
    return float(behavior["acc"].mean())


def process_folder(folder: Path, params: PreprocessingParams) -> Path | None:
    """Preprocess every subject in one ``02_`` folder; return the manifest path."""
    subject_files = find_subject_files(folder)
    if not subject_files:
        print(f"[skip] {folder.name}: no s_<subject>_.parquet files")
        return None

    out_dir = output_dir(folder)
    plots_dir, stages_dir = out_dir / "plots", out_dir / "stages"
    event = onset_column(folder)
    print(f"[{folder.name}] {len(subject_files)} subjects, onset '{event}' -> {out_dir}")

    results: list[PipelineResult] = []
    plot_paths: dict[str, dict[str, Path]] = {"all": {}}
    for subject, path in subject_files.items():
        print(f"  s{subject}: preprocessing")
        context = load_subject_context(folder.parent, subject, event)
        result = run_pipeline(pd.read_parquet(path), subject, params, **context)
        accuracy = subject_accuracy(folder.parent, subject)
        result.summary = {"subject": subject, "accuracy_pct": round(100 * accuracy, 1),
                          **{k: v for k, v in result.summary.items() if k != "subject"}}
        results.append(result)

        excluded = result.trial_metrics["excluded"]
        plot_paths[subject] = {}
        for stage in result.stages:
            # Short file names on purpose: Windows MAX_PATH (260) is tight here.
            png = plots_dir / f"s{subject}_{stage.number:02d}.png"
            plot_stage(stage, subject, png, params, excluded)
            plot_paths[subject][stage.slug] = png
            if stage.kind != "metrics":  # metrics are saved in trial_metrics.csv
                stage_file = stages_dir / f"s{subject}_{stage.number:02d}.parquet"
                stage_file.parent.mkdir(parents=True, exist_ok=True)
                table = stage.data.copy()
                table.columns = table.columns.astype(str)
                table.to_parquet(stage_file)

    # Rows ordered by task accuracy, best first (unknown accuracy last).
    results.sort(key=lambda r: -r.summary["accuracy_pct"]
                 if pd.notna(r.summary["accuracy_pct"]) else float("inf"))
    subjects = [r.subject for r in results]
    excluded_all = [r.trial_metrics["excluded"] for r in results]
    for i, template in enumerate(results[0].stages):
        png = plots_dir / f"all_{template.number:02d}.png"
        plot_stage_all_subjects([r.stages[i] for r in results], subjects,
                                excluded_all, png, params)
        plot_paths["all"][template.slug] = png

    pd.DataFrame(
        [(s.number, s.key, s.title, s.description) for s in results[0].stages],
        columns=["number", "key", "title", "description_first_subject"],
    ).to_csv(out_dir / "stage_index.csv", index=False)

    summary = pd.DataFrame([r.summary for r in results])
    summary.to_csv(out_dir / "subject_summary.csv", index=False)
    pd.concat([r.trial_metrics for r in results]).to_csv(out_dir / "trial_metrics.csv")

    report = build_report(out_dir, folder.name, results[0].stages, subjects,
                          plot_paths, summary, params)
    print(f"  static report: {report}")

    manifest = {
        "dataset": folder.name,
        "onset_event": event,
        "generated": f"{datetime.now():%Y-%m-%d %H:%M}",
        "stages": [
            {"slug": s.slug, "number": s.number, "title": s.title,
             "description": _generic_description(s)}
            for s in results[0].stages
        ],
        "subjects": [
            {"id": s, "label": f"s{s}", "note": _subject_note(summary, s)} for s in subjects
        ],
        "plots": {
            row: {slug: png.relative_to(plots_dir).as_posix() for slug, png in pngs.items()}
            for row, pngs in plot_paths.items()
        },
        # to_json turns numpy numbers into plain JSON numbers.
        "summary_columns": list(summary.columns),
        "summary": json.loads(summary.to_json(orient="records")),
        "params": [[k, str(v)] for k, v in asdict(params).items()],
    }
    path = manifest_path(folder)
    path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return path


def build_all(data_dir: Path, params: PreprocessingParams = PreprocessingParams(),
              rebuild: bool = False) -> list[Path]:
    """Build every data folder (or reuse an existing manifest unless ``rebuild``)."""
    folders = find_segment_folders(data_dir)
    if not folders:
        raise SystemExit(f"No 02_* folders found in {data_dir}")
    manifests = []
    for folder in folders:
        existing = manifest_path(folder)
        if existing.exists() and not rebuild:
            print(f"[{folder.name}] using existing outputs (pass --rebuild to recompute)")
            manifests.append(existing)
            continue
        path = process_folder(folder, params)
        if path is not None:
            manifests.append(path)
    return manifests
