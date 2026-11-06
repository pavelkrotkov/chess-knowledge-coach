"""Create one private opening comparison for an operator."""

import argparse
import os
import sqlite3
from pathlib import Path
from types import SimpleNamespace

from .opening_measure_prepare import _prepare
from .tactical_course_deadline import PreviewDeadline
from .tactical_course_files import paths
from .tactical_study_path import planning


def prepare(root, game_id, position_id, alternative, output, engine):
    planning(root, os.environ["CHESS_SUBJECT"])
    database, output = paths(root, output)
    connection = sqlite3.connect(database.as_uri() + "?mode=ro", uri=True, timeout=1)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only=ON")
    db = SimpleNamespace(connection=connection, path=database)
    try:
        _prepare(db, game_id, position_id, alternative, output, engine)
    finally:
        connection.close()


def main():
    parser = argparse.ArgumentParser(description="Measure one owned opening catalog alternative")
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--game-id", type=int, required=True)
    parser.add_argument("--position-id", type=int, required=True)
    parser.add_argument("--alternative", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--engine", default="/usr/games/stockfish")
    args = parser.parse_args()
    try:
        prepare(
            args.project_root,
            args.game_id,
            args.position_id,
            args.alternative,
            args.output,
            args.engine,
        )
    except (Exception, PreviewDeadline):
        raise SystemExit("Opening comparison unavailable; no result was published.") from None
    print("Private opening comparison prepared.")


if __name__ == "__main__":
    main()
