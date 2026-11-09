## Computation using AI
## vis_html_of_pupil_signal_preprocessing

Generating html report for pupil signal preprocessing, containing all preprocessing stages visualizations, per subject.

## General note / context: 


## Path & Structure:
Output folder (plots, html, data tables): should be saved within each respective data subfolder of the data folder, in another new subfolder named 'vis_html_of_pupil_signal_preprocessing'.
One Report html file generated for all subjects, Rows represent subjects, columns represent analysis plot. First rows contain aggregations or general info/plots.

## General analysis objective:
Observe for each subject: pupil signal, pupil signal preprocessed - in each step. html should contain 


## data context:

Segmented tables context - within data folder there are '01_' and '02_' folders with data files. 

### Parsed EyeLink tables:

The parsing pipeline saves one Parquet file per subject as `s_<subject>_.parquet` under `processedData_py2026/pupil/<table name>/`. The table below covers folders beginning with `01_`, including the companion behavioral CSV export.

| Table name | Content | Schema |
| --- | --- | --- |
| `01_behavior` | One row per behavioral trial, selected from the subject's behavior CSV. | `trialnr`, `validity`, `response`, `acc`, `rt`, `outcome` |
| `01_pupil` | Continuous EyeLink gaze and pupil samples, reindexed at 1 ms intervals by default. | Index: `time`; columns: `gaze_x`, `gaze_y`, `pupil` |
| `01_trials` | One row per trial, assembled from EyeLink messages. | Event/timing columns: `starttrial`, `endtrial`, `startmask`, `endmask`, `startcue`, `stopcue`, `startoutcome`, `stopoutcome`; trial-variable columns: `block`, `trialnr`, `stimulus`, `condition`, `valence`, `required_action`, `manipulation`, `govalidity`, `nogovalidity`, `isi`, `iti`, `response`, `acc`, `rt`, `outcome` |
| `01_blinks` | One row per completed EyeLink blink event. | `eye`, `start_time`, `end_time`, `duration_ms` |
| `01_fixations` | One row per completed EyeLink fixation event, with average gaze position and pupil value. | `eye`, `start_time`, `end_time`, `duration_ms`, `average_gaze_x`, `average_gaze_y`, `average_pupil` |
| `01_saccades` | One row per completed EyeLink saccade event, with gaze endpoints, amplitude, and peak velocity. | `eye`, `start_time`, `end_time`, `duration_ms`, `start_gaze_x`, `start_gaze_y`, `end_gaze_x`, `end_gaze_y`, `amplitude_deg`, `peak_velocity_deg_per_s` |

### Segmented data:

The segmentation pipeline saves one Parquet file per subject as `s_<subject>_.parquet` in each `02_` folder. Each file is a wide matrix of pupil measurements: rows are milliseconds relative to an event onset, and columns are trial numbers from `01_trials`.

| Table name | Content | Schema |
| --- | --- | --- |
| `02_pupil_trial_startmask_1000_2966ms` | Pupil segments aligned to `startmask`, spanning 1000 ms before through 2966 ms after mask onset. | Index: `time_from_event_start_ms`; columns: one pupil-value column per `trialnr` (column-axis name: `trialnr`). |
| `02_pupil_trial_startoutcome_1000_2000ms` | Pupil segments aligned to `startoutcome`, spanning 1000 ms before through 2000 ms after outcome onset. | Index: `time_from_event_start_ms`; columns: one pupil-value column per `trialnr` (column-axis name: `trialnr`). |

The set of `trialnr` columns depends on the subject's trial table. The time margins are encoded in each folder name; the current segmentation function creates a 1 ms time index when the source pupil data have 1 ms sampling.


## Data preparation:
data preparation contains signal preprocessing and saving each stage. the data in the data folder is already segmented into relevant time-segments, each file is a time-segment. 

## Signal preprocessing:
the context for signal preprocessing taken from Algermissen and den Ouden (2024), with the relevant explanation: 
"...After epoching, the timing of blinks
and saccades (as automatically detected by the EyeLink software) was extracted. These gaps of missing data were zeropadded by deleting 150 ms (for blinks, 20 ms for saccades) of samples before and after them (as recommended by the EyeLink manufacturer). In addition, we computed the first derivative of the pupil time course and marked abnormally fast pupil changes (absolute values of the z-standardized first derivative higher than 2). If two such marks occurred less than ten samples away from each other, we deleted all samples in-between. Finally, we interpolated missing or deleted samples with linear interpolation and low-pass filtered the data at 6 Hz with a 3-order Butterworth filter. We deleted the first and last 250 ms of each trial to remove edge artifacts
caused by the filter. We converted pupil diameter to units of modulation (percent signal change) around the mean of the pupil time series of each block using the grand-mean pupil diameter per block (i.e., 64 trials forming one block). Trials with more than 50% of missing/interpolated data were excluded (in total 166 trials of 8,960 trials; per participant: M = 4.74, SD = 9.10, range 0–43). Finally, we computed the trial-by-trial pupil baseline as mean pupil diameter in the 500 ms before the onset of the forward mask and the maximal pupil dilation as the maximal value during the 2,966 ms after onset of the forward mask (i.e., until the earliest possible end of the ISI). We then computed the trial-by-trial pupil dilation by subtracting the trial-by-trial pupil baseline from the trialby-trial maximal dilation. ..."

## Analysis plots:

in each column in the html, there will be a step of the preprocessing with short explenation.

y = pupil
x = time in milliseconds
