"""Prepare a source-bound public fork for an unfamiliar context selection."""

import argparse
import json
import os
from pathlib import Path

from .opening_context_fork_prepare import prepare
from .opening_profile_cli_db import private_database
from .tactical_course_deadline import PreviewDeadline


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", required=True, type=Path)
    parser.add_argument("--selection", required=True)
    args = parser.parse_args()
    try:
        with private_database(args.project_root, os.environ["CHESS_SUBJECT"]) as db:
            result = prepare(db, args.project_root, os.environ["CHESS_SUBJECT"], args.selection)
    except (Exception, PreviewDeadline):
        raise SystemExit("Public opening fork preparation unavailable.") from None
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
