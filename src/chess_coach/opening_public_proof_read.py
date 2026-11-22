"""Read only a current, immutable public opening proof preparation."""

import sqlite3

from .fact_fingerprint import canonical, digest
from .opening_public_proof_files import latest
from .opening_public_proof_source import VERSION, binding, check
from .style_schedule_budget import BudgetExceeded, history_budget
from .tactical_study_path import planning


def view(payload):
    return {
        "version": payload["version"],
        "status": "prepared",
        "reference": payload["binding"]["reference"],
        "sample": payload["sample"],
        "branches": payload["branches"],
    }


def lookup(db, root, subject, game_id, position_id, alternative, deadline):
    try:
        directory, _ = planning(root, subject)
        version = db.connection.execute("PRAGMA data_version").fetchone()[0]
        with history_budget(deadline=deadline):
            identity, index = binding(
                db, root, subject, game_id, position_id, alternative, deadline
            )
        value = latest(directory, digest(canonical(identity)))
        check(deadline)
        if (
            value is None
            or value.get("version") != VERSION
            or value.get("binding") != identity
            or db.connection.execute("PRAGMA data_version").fetchone()[0] != version
        ):
            return None
        with history_budget(deadline=deadline):
            current = binding(db, root, subject, game_id, position_id, alternative, deadline)
        if (
            current != (identity, index)
            or db.connection.execute("PRAGMA data_version").fetchone()[0] != version
        ):
            return None
        return view(value)
    except (OSError, ValueError, TypeError, KeyError, sqlite3.Error, TimeoutError, BudgetExceeded):
        return None
