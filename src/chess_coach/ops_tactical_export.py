"""Create one private non-overwriting tactical export candidate."""

import argparse
import os
import re
import sqlite3
from pathlib import Path
from types import SimpleNamespace

from .schema_compat import readonly
from .tactical_course_budget import Budget
from .tactical_course_deadline import PreviewDeadline
from .tactical_course_files import paths
from .tactical_course_offer import offer as offer_course
from .tactical_course_publish import publish
from .tactical_export import build
from .tactical_export_input import load


def prepare(root, preview, expected_hash, output, *, offer=False):
    database, output = paths(root, output)
    connection = sqlite3.connect(database.as_uri() + "?mode=ro", uri=True, timeout=1)
    connection.row_factory = sqlite3.Row
    # SQLite must create connection-local views before enabling query-only mode.
    readonly(connection, database)
    connection.execute("PRAGMA query_only=ON")
    try:
        db = SimpleNamespace(connection=connection)
        budget = Budget(db)
        with budget.scope(snapshot=False):
            envelope = load(root, preview)
            if (
                not isinstance(envelope, dict)
                or not re.fullmatch(r"[0-9a-f]{64}", expected_hash)
                or envelope.get("preview_sha256") != expected_hash
            ):
                raise ValueError("selected preview hash differs")
        result = build(
            db, os.environ["CHESS_SUBJECT"], os.environ["CHESS_CORPUS"], envelope, budget
        )
        publish(output, result, budget, readonly=True)
        offer_course(
            root, database, os.environ["CHESS_SUBJECT"], output, result, budget, enabled=offer
        )
    finally:
        connection.close()


def main():
    parser = argparse.ArgumentParser(description="Prepare one private tactical export candidate")
    parser.add_argument("--project-root", required=True, type=Path)
    parser.add_argument("--preview", required=True, type=Path)
    parser.add_argument("--preview-sha256", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument(
        "--offer", action="store_true", help="offer the completed export in the private tutor"
    )
    args = parser.parse_args()
    try:
        prepare(args.project_root, args.preview, args.preview_sha256, args.output, offer=args.offer)
    except (Exception, PreviewDeadline):
        raise SystemExit("Tactical export unavailable; an export may have been retained.") from None

    print("Private tactical export candidate prepared.")


if __name__ == "__main__":
    main()
