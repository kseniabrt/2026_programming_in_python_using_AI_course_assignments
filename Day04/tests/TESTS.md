# Tests

Run from the `Day04` folder:

```
python -m unittest discover -s tests -t .
```

The tests need no real data: they build small synthetic signals and a fake dataset in a
temporary folder. 24 tests in two files.

## test_preprocessing.py: preprocessing steps (15 tests, copied from Day03)

| Test | Checks that |
| --- | --- |
| `test_mark_missing_turns_zeros_into_nan` | 0 samples (EyeLink signal loss) become missing, and the input table is not modified. |
| `test_fast_change_mask_flags_jump_and_merges_close_marks` | A sudden jump is flagged, and two flags fewer than 10 samples apart are joined, so everything between them is deleted. |
| `test_fast_change_mask_does_not_merge_distant_marks` | Flags far apart (50 samples) stay separate; the samples between them are kept. |
| `test_fast_change_mask_handles_all_nan` | A trial with no valid samples does not crash and flags nothing. |
| `test_interpolate_linear_fills_gaps_and_edges` | Gaps are filled linearly, edges take the nearest valid value, and an all-missing trial stays missing. |
| `test_lowpass_removes_fast_oscillation_keeps_slow` | The 6 Hz low-pass removes a 40 Hz oscillation and keeps a 1 Hz one. |
| `test_trim_edges` | 250 ms are cut from both ends (−1000…1000 ms becomes −750…750 ms). |
| `test_block_of_trial` | Trial numbers map to 64-trial blocks (1–64 → 1, 65–128 → 2, …). |
| `test_percent_signal_change_uses_block_grand_mean` | % signal change is computed around each block's own grand mean. |
| `test_trial_metrics` | Baseline (mean −500…0 ms), peak and dilation (peak − baseline) are computed correctly. |
| `test_pipeline_excludes_mostly_missing_trial` | The full pipeline returns 12 stages, ends with the baseline and dilation histograms, and excludes a trial with 75 % missing samples from the later stages. |
| `test_pipeline_removes_padded_blinks_and_saccades` | Blinks are removed with ±150 ms and saccades with ±20 ms padding, at the right times relative to each trial's onset, and blocks from `01_trials` are used. |
| `test_event_mask_uses_onset_and_padding` | An event is placed in a segment using the trial's onset time plus padding, and only in that trial. |
| `test_event_mask_catches_event_outside_window_via_padding` | An event that ends just before the segment still removes samples when its padding reaches into the segment. |
| `test_event_mask_without_events_or_onset` | Missing event tables or unknown trial onsets remove nothing. |

## test_app.py: Flask web page (9 tests)

| Test | Checks that |
| --- | --- |
| `test_first_visit_selects_everything` | On the first visit, all subjects and all stages are selected. |
| `test_keeps_display_order_and_drops_unknown` | Selections keep the page order (accuracy order, stage order) and ignore unknown values. |
| `test_applied_with_nothing_selected` | Pressing Apply with nothing ticked selects nothing (not everything). |
| `test_default_page_shows_all_rows_and_stages` | The start page shows every row × stage plot, plus the summary and parameter tables. |
| `test_filter_subjects_and_stages` | Choosing one subject and one stage shows exactly that plot and no others. |
| `test_aggregate_row_is_selectable` | The "All subjects" row can be chosen on its own. |
| `test_empty_selection_shows_message` | With no subject selected, the page shows a "Nothing to show" message instead of an empty table. |
| `test_plots_load_with_relative_data_dir` | Plot images still load when the data folder is given as a relative path (e.g. `--data-dir ..\sample_data1`). |
| `test_plot_route_serves_file_and_rejects_unknown` | Plot images are served; an unknown dataset or a path leaving the plots folder returns 404. |
