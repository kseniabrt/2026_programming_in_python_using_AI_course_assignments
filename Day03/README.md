## objective

Day03 assignment is to Write a program that has a function that can do a scientific computation, using some data. 

I want to understand more a signal preprocessing in Algermissen (2024) dataset, so I've decided to write a program using Claude Code that performs the preprocessing stated in the article and plots all the stages for me to explore. 

I gave as a context the actual relevant paragraph from the article and designed my desired output in an html page format. 


## prompt 1

hello claude, how are you?

i would like us to plan, and implement a new module within Day03 in this project. 
please read the context prompt.md in this module, plan and implement. please ask for clarifications if any. 

lets for the beggining skip the preprocessing of blinks and saccades, since i did not give you the relevant data for it.

thank you.

## Claude 1

"... What the data shows: 6–12% of samples are missing per subject, about half zeros and half removed in stage 3. No trials were excluded.

Assumptions I made — please correct any that are wrong:

1. Zeros mean missing data. EyeLink writes 0 when it loses the pupil, so I treat zeros as gaps.
2. Blocks are trials 1–64, 65–128, and so on. That gives 4 blocks for the 256 trials.
3. The derivative is z-scored within each trial, and the 50% missing share is counted inside the trimmed window.
4. The peak window is shorter than in the paper. After trimming, the startmask segment ends at 2716 ms, not 2966 ms. To match the paper exactly, the segments would need to extend 250 ms further.
5. Baseline and peak use the same windows for the outcome-locked data: baseline is −500 to 0 ms and the peak is the maximum after onset.

Things to know:
- Dips around blinks: the filtered plots show sharp dips next to blinks. The derivative step misses the slow pupil drop just before and after a blink, and that is exactly what the 150 ms blink padding is meant to fix. If you'd like, I can pad every run of zeros by 150 ms as a stand-in until you have the event data.
- Short file names: the output folder path is already 220 characters, and Windows rejects paths over 260. So files have short names like plots/s08_03.png, and stage_index.csv lists which stage each number is.
- Nothing committed: I haven't committed anything. The outputs are written inside data/, so tell me whether you want them committed or added to .gitignore.  "


## Prompt 2

please add git ignore for data folder content, as well as cache files. tell me if there any more files should be ignored from git.

## Prompt 3

Hello Claude, how are you?
I've added data for 01_behavior, 01_blinks, 01_fixations, 01_saccades and 01_trials. I would like we now use this data to complete the preprocessing with the essential data of blinks and saccades, as described in Day03 prompt.md context file. 
please observe, plan, ask for clarifications and implement. 
thank you!

## Prompt 4

Please add also:
1. between stage 10 and 11 - another stage with the histograms of the trial-by-trial baseline (in the same way as trial-by-trial dilation)
2. order subjects (rows) by total accuracy in the task

