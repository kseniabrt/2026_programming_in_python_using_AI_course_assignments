"""Tests for the Flask page, on a tiny synthetic manifest (no real data needed).

Run from Day04: python -m unittest discover -s tests -t .
"""

import json
import os
import tempfile
import unittest
from pathlib import Path

from vis_html_of_pupil_signal_preprocessing_with_flask.app import create_app, selected
from vis_html_of_pupil_signal_preprocessing_with_flask.build import OUTPUT_FOLDER_NAME

DATASET = "02_pupil_timecourse_startmask_1000_2966ms"
STAGES = [
    {"slug": "01_raw", "number": 1, "title": "Raw signal", "description": "raw"},
    {"slug": "02_blinks_removed", "number": 2, "title": "Blinks removed", "description": "b"},
]
SUBJECTS = [{"id": "10", "label": "s10", "note": "accuracy 90%"},
            {"id": "08", "label": "s08", "note": "accuracy 58%"}]


def write_fake_dataset(data_dir: Path) -> None:
    out = data_dir / DATASET / OUTPUT_FOLDER_NAME
    (out / "plots").mkdir(parents=True)
    plots = {}
    for row in ["all", "10", "08"]:
        plots[row] = {}
        for st in STAGES:
            name = f"{row}_{st['number']:02d}.png"
            (out / "plots" / name).write_bytes(b"png")
            plots[row][st["slug"]] = name
    manifest = {
        "dataset": DATASET, "onset_event": "startmask", "generated": "now",
        "stages": STAGES, "subjects": SUBJECTS, "plots": plots,
        "summary_columns": ["subject", "accuracy_pct"],
        "summary": [{"subject": "10", "accuracy_pct": 90.2},
                    {"subject": "08", "accuracy_pct": 57.8}],
        "params": [["edge_trim_ms", "250.0"]],
    }
    (out / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")


class TestSelected(unittest.TestCase):
    def test_first_visit_selects_everything(self):
        self.assertEqual(selected([], ["a", "b"], applied=False), ["a", "b"])

    def test_keeps_display_order_and_drops_unknown(self):
        self.assertEqual(selected(["b", "x", "a"], ["a", "b", "c"], applied=True), ["a", "b"])

    def test_applied_with_nothing_selected(self):
        self.assertEqual(selected([], ["a", "b"], applied=True), [])


class TestApp(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        data_dir = Path(self.tmp.name)
        write_fake_dataset(data_dir)
        self.client = create_app(data_dir).test_client()

    def tearDown(self):
        self.tmp.cleanup()

    def test_default_page_shows_all_rows_and_stages(self):
        page = self.client.get("/").get_data(as_text=True)
        for img in ["all_01.png", "10_02.png", "08_01.png"]:
            self.assertIn(f"/plots/{DATASET}/{img}", page)
        self.assertIn("Per-subject summary", page)
        self.assertIn("Parameters", page)

    def test_filter_subjects_and_stages(self):
        page = self.client.get(
            "/?applied=1&subject=08&stage=02_blinks_removed").get_data(as_text=True)
        self.assertIn("08_02.png", page)
        self.assertNotIn("08_01.png", page)
        self.assertNotIn("10_02.png", page)
        self.assertNotIn("all_02.png", page)

    def test_aggregate_row_is_selectable(self):
        page = self.client.get("/?applied=1&subject=all&stage=01_raw").get_data(as_text=True)
        self.assertIn("all_01.png", page)
        self.assertNotIn("10_01.png", page)

    def test_empty_selection_shows_message(self):
        page = self.client.get("/?applied=1&stage=01_raw").get_data(as_text=True)
        self.assertIn("Nothing to show", page)

    def test_plots_load_with_relative_data_dir(self):
        cwd = os.getcwd()
        os.chdir(self.tmp.name)
        try:
            client = create_app(Path(".")).test_client()
            with client.get(f"/plots/{DATASET}/10_01.png") as response:
                self.assertEqual(response.status_code, 200)
        finally:
            os.chdir(cwd)

    def test_plot_route_serves_file_and_rejects_unknown(self):
        with self.client.get(f"/plots/{DATASET}/10_01.png") as response:
            self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.get("/plots/nope/10_01.png").status_code, 404)
        self.assertEqual(self.client.get(f"/plots/{DATASET}/../manifest.json").status_code, 404)


if __name__ == "__main__":
    unittest.main()
