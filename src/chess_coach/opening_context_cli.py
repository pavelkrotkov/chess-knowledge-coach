"""Read the selected private database without initializing it."""

import sqlite3
from pathlib import Path

from .opening_context_inventory import inventory
from .opening_profile_cli_db import private_database
from .tactical_course_budget import PreviewUnavailable


def report(root, learner, database):
    if root is None:
        raise ValueError("project root required")
    try:
        with private_database(root, learner, database=database) as db:
            if Path(database).resolve(strict=True) != db.path.resolve(strict=True):
                raise ValueError("selected database differs")
            return inventory(db, root, learner)
    except (OSError, ValueError, TimeoutError, sqlite3.Error, PreviewUnavailable):
        return {"status": "unavailable", "reason": "source_or_deadline", "contexts": None}
