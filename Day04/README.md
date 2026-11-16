## objective

Day04 assignment is to Write a flask web page program that executes Day03 business logic.

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


python main.py               # prepares outputs if missing, then starts the web page
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

