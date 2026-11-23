## objective

Day04 assignment is to Write a flask web page program that executes Day03 business logic.


## How to run

Requirements: Python 3.10+ and the packages in `requirements.txt`:

```
pip install -r requirements.txt
```

Open cmd **in the `Day04` folder** and run the main program, `main.py`:

```
python main.py                       # build outputs if missing, then start the web page
python main.py --rebuild             # recompute all preprocessing and plots first
python main.py --build-only          # only compute the outputs, do not start the server
python main.py --port 8000           # use another port (default 5000)
python main.py --data-dir C:\other\data   # another data folder (default ..\sample_data1)
python -m unittest discover -s tests -t .  # run the tests (see tests\TESTS.md)
```

Then open http://127.0.0.1:5000 in a browser; stop the server with Ctrl+C.

What happens:
1. **Preprocessing** (first run about 25 s; later runs reuse the saved outputs): for every
   `02_*` folder, the Day03 pipeline runs and saves its outputs to
   `sample_data1\<02_folder>\vis_html_of_pupil_signal_preprocessing_with_flask\`
   (plots, stage tables, summaries, a static `report.html` and `manifest.json` for the web page).
2. **Web page**: choose the dataset, the subjects (rows, including the "All subjects" row) and
   the preprocessing stages (columns), then press Apply. The summary and parameter tables
   stay on the page.

Code:
- `main.py`: the main program, the file you run
- `vis_html_of_pupil_signal_preprocessing_with_flask/`
  - `preprocessing.py`, `plotting.py`, `report.py`: copied from Day03 (business logic)
  - `build.py`: runs the pipeline for every data folder and saves the outputs
  - `app.py`, `templates/index.html`: the Flask web page
- `tests/`: unit tests, described in `tests/TESTS.md`


## Data: sample_data1

Day04 uses the same shared data folder as Day03, `sample_data1` at the repository root.
The input files are in git; the outputs the programs generate are not (see `.gitignore`).

```
<repo>\
├── Day03\
├── Day04\
└── sample_data1\
    ├── 01_trials\          s_08_.parquet, s_10_.parquet, s_30_.parquet
    ├── 01_blinks\          (same s_<subject>_.parquet files in every folder)
    ├── 01_saccades\
    ├── 01_behavior\
    ├── 01_fixations\
    ├── 02_pupil_timecourse_startmask_1000_2966ms\
    └── 02_pupil_timecourse_startoutcome_1000_2000ms\
```

Each folder holds one Parquet file per subject, named `s_<subject>_.parquet`.

| Folder | Needed? | Content |
| --- | --- | --- |
| `02_pupil_timecourse_<event>_<before>_<after>ms` | **yes** | Pupil segments: rows = ms from the event onset (`time_from_event_start_ms`), columns = trials (`trialnr`). Each `02_` folder is one dataset in the web page. `<event>` must be a column of `01_trials` (e.g. `startmask`, `startoutcome`). |
| `01_trials` | **yes** | One row per trial: `trialnr`, `block` (block for % signal change) and the event times (`startmask`, `startoutcome`, …) in EyeLink time. Needed to place blinks and saccades in each segment. |
| `01_blinks` | **yes** | EyeLink blink events: `start_time`, `end_time` (EyeLink time). Removed with 150 ms padding. |
| `01_saccades` | **yes** | EyeLink saccade events: `start_time`, `end_time`, … Removed with 20 ms padding. |
| `01_behavior` | recommended | One row per trial with `acc` (correct = 1). Used to order subjects by accuracy. |
| `01_fixations` | no | EyeLink fixation events; not used by the program. |

If a `01_` file is missing, the program prints a warning and skips what depends on it. The
`_Screenshot ….png` files in some folders are documentation only.

Day04 writes its outputs to `vis_html_of_pupil_signal_preprocessing_with_flask\` inside each
`02_` folder; Day03 writes to `vis_html_of_pupil_signal_preprocessing\`, so the two never clash.
After changing the data, run `python main.py --rebuild`, because otherwise the saved outputs are reused.

**Windows path length:** the longest output path is currently 258 characters, just under the
260 limit. If the repository is moved to a deeper folder, saving fails with
`FileNotFoundError`. Either keep the repository path short or enable long paths in Windows
(`LongPathsEnabled` registry setting).

## prompt 1

hello claude, how are you?

I would like us to plan, and implement a new module within Day04 in this project. 
please read the context Day04/prompts/vis_html_of_pupil_signal_preprocessing_with_flask.md in this module, plan and implement. please ask for clarifications if any. 

I want to empasize that the implementation will contain a main program file which is the one that i would call from cmd to run the programm, so it will be clear. 

Make sure to understand Day03 business logic, and do not change Day03 content. 

thank you.


## Claude 1

I'm well, thanks! The Day04 Flask page is built and works. I ran the real server and checked it with test requests, but haven't looked at the page in a browser. Day03 is unchanged.

How to run it (from cmd, in the Day04 folder):


python main.py               # prepares outputs if missing, then starts the web page ((.\main.py))
python main.py --rebuild     # recompute everything first
python main.py --build-only  # only compute outputs, no server
Then open http://127.0.0.1:5000 in a browser, and press Ctrl+C to stop. The first run takes about 25 seconds to preprocess. Later runs reuse the saved outputs and start right away.

What's in Day04:

main.py: the main program file you run. The docstring at the top explains how to use it.
vis_html_of_pupil_signal_preprocessing_with_flask/:
preprocessing.py, plotting.py and report.py: copied unchanged from Day03, so the business logic is the same.
build.py: Day03's runner, now writing to the new output folder. It also saves a manifest.json with everything the web page needs, so restarts don't re-run the pipeline.
app.py and templates/index.html: the web page.
data/: a copy of Day03's 01_* and 02_* input files only. Outputs go to <02_folder>/vis_html_of_pupil_signal_preprocessing_with_flask/, which also gets the static report.html.
tests/: Day03's 15 tests plus 8 new ones for the web page. All 23 pass.
requirements.txt. I installed Flask 3.1.3, which wasn't on your machine before.
What the page does:

Dataset selector: a dropdown to switch between the startmask and startoutcome data.
Subjects: a checkbox list of the "All subjects" row and each subject (still ordered by accuracy), with Select all and Clear buttons.
Stages: a checkbox list of all 12 preprocessing stages, with the same buttons.
Everything else is still there: the description, per-subject summary, parameters, column explanations, and click-to-enlarge plots.
Bookmarkable views: your choices go into the URL, so a filtered view can be saved.
Three choices I made that you may want changed:

"All subjects is selectable": I read this as the "All subjects" row being one of the choices, plus a Select-all button. If you meant the aggregate plots should recalculate for only the selected subjects, I can add that; it means making the plots on request.
Dataset switching: the prompt didn't mention it, but with two data folders the page needs a way to choose between them.
The summary table always lists every subject, whichever ones you filter. Only the stage table follows the selection.
Your Day04 README is your log of prompts and replies, so I left it as it is. Nothing is committed yet.

