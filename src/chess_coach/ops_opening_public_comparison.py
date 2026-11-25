"""Prepare one checked public opening comparison for the private chooser."""

import argparse
import os
from pathlib import Path

from .opening_profile_cli_db import private_database
from .opening_public_comparison_prepare import prepare
from .tactical_course_deadline import PreviewDeadline


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", required=True, type=Path)
    parser.add_argument("--selection", required=True)
    parser.add_argument("--engine", default="/usr/games/stockfish")
    args = parser.parse_args()
    try:
        with private_database(args.project_root, os.environ["CHESS_SUBJECT"]) as db:
            result = prepare(
                db, args.project_root, os.environ["CHESS_SUBJECT"], args.selection, args.engine
            )
    except (Exception, PreviewDeadline):
        raise SystemExit("Public opening comparison unavailable.") from None
    print("Public opening comparison:", result["status"])


if __name__ == "__main__":
    main()
