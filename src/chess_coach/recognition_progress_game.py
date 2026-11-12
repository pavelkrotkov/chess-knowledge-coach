"""Read the existing independent capture windows without replaying games."""

import sqlite3
import time

from .capture_game_trend_report import report as capture_report
from .mastery_time import parse_utc

SECONDS = 2.0


def capture(db, subject, root):
    until = time.monotonic() + SECONDS
    version = db.connection.execute("PRAGMA data_version").fetchone()[0]
    db.connection.set_progress_handler(lambda: int(time.monotonic() >= until), 1000)
    try:
        result = capture_report(db, subject, root)
        if (
            time.monotonic() >= until
            or db.connection.execute("PRAGMA data_version").fetchone()[0] != version
        ):
            return None
        return result
    except (sqlite3.Error, ValueError, TypeError):
        return None
    finally:
        db.connection.set_progress_handler(None, 0)


def later(group, games):
    if not group.get("comparable") or not games or not games.get("comparable"):
        return False
    end = parse_utc(group.get("recognition_end"))
    start = parse_utc(games.get("earlier", {}).get("oldest"))
    return bool(end and start and start > end)
