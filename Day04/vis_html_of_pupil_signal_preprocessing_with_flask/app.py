"""Flask web page for the pupil preprocessing report.

The page shows the same report as Day03's ``report.html`` (summary, parameters,
stage table), plus a filter form to choose the dataset, the subjects (rows)
and the preprocessing stages (columns) shown in the stage table.

Selections travel in the URL query string, so any view can be bookmarked:
``/?dataset=<folder>&subject=all&subject=10&stage=01_raw&applied=1``
"""

from __future__ import annotations

import json
from pathlib import Path

from flask import Flask, abort, render_template, request, send_from_directory

from .build import find_segment_folders, manifest_path, output_dir
from .report import CSS

ALL_SUBJECTS = "all"  # id of the aggregate "All subjects" row


def load_datasets(data_dir: Path) -> dict[str, dict]:
    """Manifest of every built ``02_`` folder, keyed by folder name."""
    datasets = {}
    for folder in find_segment_folders(data_dir):
        path = manifest_path(folder)
        if path.exists():
            manifest = json.loads(path.read_text(encoding="utf-8"))
            manifest["plots_dir"] = output_dir(folder) / "plots"
            datasets[folder.name] = manifest
    return datasets


def selected(values: list[str], allowed: list[str], applied: bool) -> list[str]:
    """Keep the user's choices in display order; everything on first visit."""
    if not applied:
        return list(allowed)
    chosen = set(values)
    return [v for v in allowed if v in chosen]


def create_app(data_dir: Path) -> Flask:
    datasets = load_datasets(data_dir)
    if not datasets:
        raise RuntimeError(f"No built datasets in {data_dir}; run the build first.")

    app = Flask(__name__)

    @app.get("/")
    def index():
        dataset_name = request.args.get("dataset")
        if dataset_name not in datasets:
            dataset_name = next(iter(datasets))
        ds = datasets[dataset_name]
        applied = request.args.get("applied") == "1"

        subject_options = [{"id": ALL_SUBJECTS, "label": "All subjects",
                            "note": "trial means, one line per subject"}] + ds["subjects"]
        subject_ids = selected(request.args.getlist("subject"),
                               [s["id"] for s in subject_options], applied)
        stage_slugs = selected(request.args.getlist("stage"),
                               [s["slug"] for s in ds["stages"]], applied)

        return render_template(
            "index.html",
            css=CSS,
            datasets=list(datasets),
            ds=ds,
            dataset_name=dataset_name,
            subject_options=subject_options,
            subject_ids=subject_ids,
            rows=[s for s in subject_options if s["id"] in subject_ids],
            stages=[s for s in ds["stages"] if s["slug"] in stage_slugs],
            stage_slugs=stage_slugs,
        )

    @app.get("/plots/<dataset>/<path:filename>")
    def plot(dataset: str, filename: str):
        if dataset not in datasets:
            abort(404)
        # send_from_directory refuses paths that leave plots_dir.
        return send_from_directory(datasets[dataset]["plots_dir"], filename)

    return app
