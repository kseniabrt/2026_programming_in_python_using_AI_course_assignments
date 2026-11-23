"""Main program: pupil preprocessing report as a Flask web page.

Run from cmd, inside the Day04 folder:

    python main.py                 # build outputs if missing, then start the web page
    python main.py --rebuild       # recompute all preprocessing and plots first
    python main.py --port 8000     # use another port
    python main.py --build-only    # only compute the outputs, do not start the server

Then open http://127.0.0.1:5000 in a browser (stop the server with Ctrl+C).

Steps:
1. For every sample_data1/02_* folder, run the Day03 preprocessing pipeline and save
   plots, stage tables, summaries and a static report.html into
   <02_folder>/vis_html_of_pupil_signal_preprocessing_with_flask/
   (skipped when those outputs already exist, unless --rebuild).
2. Start the Flask web page, where you choose the dataset, the subjects and
   the preprocessing stages to show.
"""

from __future__ import annotations

import argparse
import socket
from pathlib import Path

from vis_html_of_pupil_signal_preprocessing_with_flask.app import create_app
from vis_html_of_pupil_signal_preprocessing_with_flask.build import build_all

# Shared data folder at the repository root: <repo>/sample_data1
DEFAULT_DATA_DIR = Path(__file__).resolve().parents[1] / "sample_data1"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Pupil preprocessing report as a Flask web page.")
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR,
                        help="folder with the 01_* and 02_* data folders "
                             "(default: <repo>/sample_data1)")
    parser.add_argument("--rebuild", action="store_true",
                        help="recompute preprocessing and plots even if outputs exist")
    parser.add_argument("--build-only", action="store_true",
                        help="only compute the outputs; do not start the web server")
    parser.add_argument("--host", default="127.0.0.1", help="server address (default 127.0.0.1)")
    parser.add_argument("--port", type=int, default=5000, help="server port (default 5000)")
    return parser.parse_args(argv)


def port_in_use(host: str, port: int) -> bool:
    """True when another program (e.g. an older server) already listens there."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex((host, port)) == 0


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    args.data_dir = args.data_dir.resolve()

    if not args.build_only and port_in_use(args.host, args.port):
        raise SystemExit(
            f"Port {args.port} is already in use, probably by an older server that is "
            f"still running.\nStop it (Ctrl+C in its window) or choose another port, "
            f"e.g. python main.py --port {args.port + 1}")

    print("Step 1/2: preprocessing")
    build_all(args.data_dir, rebuild=args.rebuild)
    if args.build_only:
        return

    print("Step 2/2: web page")
    app = create_app(args.data_dir)
    print(f"Open http://{args.host}:{args.port} in your browser (Ctrl+C to stop).")
    app.run(host=args.host, port=args.port, debug=False)


if __name__ == "__main__":
    main()
