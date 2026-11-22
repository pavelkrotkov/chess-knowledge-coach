"""Run an owner-bound profile against a contained read-only database."""

import time
from types import SimpleNamespace

from .opening_decision import inspect
from .opening_profile_cli_db import open_database
from .opening_profile_source import profile
from .tactical_study_path import planning


def report(root, subject, game_id, position_id, alternative, reference):
    planning(root, subject)
    connection, path = open_database(root)
    try:
        db = SimpleNamespace(connection=connection, path=path)
        deadline = time.monotonic() + 12
        connection.set_progress_handler(lambda: int(time.monotonic() >= deadline), 1000)
        version = connection.execute("PRAGMA data_version").fetchone()[0]
        decision = inspect(db, game_id, position_id, subject)
        choice = next(
            (item for item in decision["catalog"]["items"] if item["uci"] == alternative), None
        )
        if choice is None:
            raise ValueError("opening alternative unavailable")
        played = profile(db, root, subject, decision, decision["played_uci"], reference, deadline)
        other = profile(db, root, subject, decision, choice["uci"], reference, deadline)
        if connection.execute("PRAGMA data_version").fetchone()[0] != version:
            raise ValueError("opening decision changed")
        return {
            "reference": reference,
            "decision_ply": decision["ply"],
            "color": decision["color"],
            "played": played,
            "alternative": other,
        }
    finally:
        connection.close()


def preparation(root, subject, game_id, position_id, alternative):
    from .opening_preparation import report as inventory

    planning(root, subject)
    connection, path = open_database(root)
    try:
        db = SimpleNamespace(connection=connection, path=path)
        _, _, _, result = inventory(
            db, root, subject, game_id, position_id, alternative, deadline=time.monotonic() + 12
        )
        return result
    finally:
        connection.close()
