"""Read only a current, immutable public opening proof preparation."""

import sqlite3

from .opening_public_fork_later import bound as full_bound
from .opening_public_proof_current import selected
from .opening_public_proof_source import binding, check
from .opening_public_proof_view import requested, view
from .opening_public_protection_policy import selected as selected_protection
from .style_schedule_budget import BudgetExceeded, history_budget
from .tactical_study_path import planning


def lookup(
    db,
    root,
    subject,
    game_id,
    position_id,
    alternative,
    deadline,
    *,
    fork_window="initial",
    proof_kind="fork",
):
    try:
        directory, _ = planning(root, subject)
        version = db.connection.execute("PRAGMA data_version").fetchone()[0]
        with history_budget(deadline=deadline):
            identity, index = binding(
                db, root, subject, game_id, position_id, alternative, deadline
            )
        if proof_kind == "protection":
            value, legacy, full = selected_protection(directory, identity, fork_window)
        else:
            value, legacy, full = selected(
                directory, identity, root, subject, deadline, fork_window, kind=proof_kind
            )
        check(deadline)
        if value is None:
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
        return requested(view(value, legacy), fork_window, proof_kind)
    except (OSError, ValueError, TypeError, KeyError, sqlite3.Error, TimeoutError, BudgetExceeded):
        return None
