"""Write one private, non-overwriting tactical-course preview."""

import argparse
import os
import sqlite3
from pathlib import Path
from types import SimpleNamespace

from .tactical_course import build
from .tactical_course_budget import Budget
from .tactical_course_deadline import PreviewDeadline
from .tactical_course_files import paths
from .tactical_course_publish import publish


def prepare(root, output):
    database, output = paths(root, output)
    connection = sqlite3.connect(database.as_uri() + "?mode=ro", uri=True, timeout=1)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only=ON")
    try:
        db = SimpleNamespace(connection=connection)
        budget = Budget(db)
        result = build(db, os.environ["CHESS_SUBJECT"], os.environ["CHESS_CORPUS"], budget=budget)
        publish(output, result, budget)
    finally:
        connection.close()


def main():
    parser = argparse.ArgumentParser(
        description="Prepare one private local tactical-course preview"
    )
    parser.add_argument("--project-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        prepare(args.project_root, args.output)
    except (Exception, PreviewDeadline):
        raise SystemExit("Tactical preview unavailable; no course was published.") from None
    print("Private tactical preview prepared.")


if __name__ == "__main__":
    main()
