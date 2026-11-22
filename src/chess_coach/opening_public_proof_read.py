"""Read only a current, immutable public opening proof preparation."""

import sqlite3

from .opening_public_proof_source import binding, check
from .opening_public_proof_versions import current as current_preparation
from .style_schedule_budget import BudgetExceeded, history_budget
from .tactical_study_path import planning


def view(payload, legacy=None):
    result = {
        "version": payload["version"],
        "status": "prepared",
        "reference": payload["binding"]["reference"],
        "sample": payload["sample"],
        "branches": payload["branches"],
    }
    if "fork" in payload["binding"]["policy"]:
        result["fork_policy"] = payload["binding"]["policy"]["fork"]
    if legacy is not None:
        result["legacy_capture"] = legacy["branches"]
    return result


def lookup(db, root, subject, game_id, position_id, alternative, deadline):
    try:
        directory, _ = planning(root, subject)
        version = db.connection.execute("PRAGMA data_version").fetchone()[0]
        with history_budget(deadline=deadline):
            identity, index = binding(
                db, root, subject, game_id, position_id, alternative, deadline
            )
        value, legacy = current_preparation(directory, identity)
        check(deadline)
        if value is None or db.connection.execute("PRAGMA data_version").fetchone()[0] != version:
            return None
        with history_budget(deadline=deadline):
            current = binding(db, root, subject, game_id, position_id, alternative, deadline)
        if (
            current != (identity, index)
            or db.connection.execute("PRAGMA data_version").fetchone()[0] != version
        ):
            return None
        return view(value, legacy)
    except (OSError, ValueError, TypeError, KeyError, sqlite3.Error, TimeoutError, BudgetExceeded):
        return None
