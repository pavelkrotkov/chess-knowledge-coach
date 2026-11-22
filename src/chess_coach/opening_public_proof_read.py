"""Read only a current, immutable public opening proof preparation."""

import sqlite3

from .opening_public_fork_later import bound as full_bound
from .opening_public_proof_current import selected
from .opening_public_proof_source import binding, check
from .opening_public_proof_view import view
from .style_schedule_budget import BudgetExceeded, history_budget
from .tactical_study_path import planning


def lookup(
    db, root, subject, game_id, position_id, alternative, deadline, *, fork_window="initial"
):
    try:
        directory, _ = planning(root, subject)
        version = db.connection.execute("PRAGMA data_version").fetchone()[0]
        with history_budget(deadline=deadline):
            identity, index = binding(
                db, root, subject, game_id, position_id, alternative, deadline
            )
        value, legacy, full = selected(directory, identity, root, subject, deadline, fork_window)
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
        if full and full_bound(root, subject, deadline) != full:
            return None
        result = view(value, legacy)
        result["fork_window"] = fork_window
        return result
    except (OSError, ValueError, TypeError, KeyError, sqlite3.Error, TimeoutError, BudgetExceeded):
        return None
