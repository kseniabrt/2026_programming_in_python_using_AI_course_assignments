## vis_html_of_pupil_signal_preprocessing_with_flask

Use flask to create a web page interface for Day03 programm, in Day04


## General note / context: 

vis_html_of_pupil_signal_preprocessing module code and data.


## Path & Structure:

Output folder (plots, html, data tables): should be saved within each respective data subfolder of the data folder, in another new subfolder named 'vis_html_of_pupil_signal_preprocessing_with_flask'.

All needed data and code should be copied from Day03 module to Day04 module, while Day03 untouched.


## Code notes

implementation should contain a main program file which is the one that i can call from cmd to run the programm, so it will be clear. 


## General analysis objective:

Observe for each subject: pupil signal, pupil signal preprocessed - in each step.


## data context:

Segmented tables context - within data folder there are '01_' and '02_' folders with data files. 

### Parsed EyeLink tables:
explained in vis_html_of_pupil_signal_preprocessing module.

### Segmented data:
explained in vis_html_of_pupil_signal_preprocessing module.


## Data preparation:

data preparation contains signal preprocessing and saving each stage. the data in the data folder is already segmented into relevant time-segments, each file is a time-segment. 

## Signal preprocessing:
explained in vis_html_of_pupil_signal_preprocessing module.


## Analysis plots:
in each column in the html, there will be a step of the preprocessing with short explenation.

y = pupil
x = time in milliseconds

## Flask programm

the web page interface should enable to:

- select which subjects to see in preprocessing stages table (from a list), all subjects is selectable as well
- select which preprocessing stages to see for the selected subjects (from a list)
- other html informating should remain
