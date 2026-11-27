"""Read only a current, immutable public opening proof preparation."""

import sqlite3

from .opening_public_capture_pv_current import verify as verify_capture_pv
from .opening_public_capture_pv_policy import policy as capture_pv_policy
from .opening_public_capture_pv_policy import selected as selected_capture_pv
from .opening_public_proof_current import confirm, selected
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
        if proof_kind == "defense_pv":
            from .opening_public_defense_pv_policy import selected as selected_defense_pv

            value, legacy, full = selected_defense_pv(directory, identity, fork_window)
        elif proof_kind == "capture_pv":
            value, legacy, full = selected_capture_pv(directory, identity, fork_window)
        elif proof_kind == "protection":
            value, legacy, full = selected_protection(directory, identity, fork_window)
        else:
            value, legacy, full = selected(
                directory, identity, root, subject, deadline, fork_window, kind=proof_kind
            )
        check(deadline)
        if value is None:
            return None
        if proof_kind == "defense_pv":
            from .opening_public_defense_pv_policy import policy as defense_policy

            verify_capture_pv(index, defense_policy(identity), value["branches"], deadline)
        elif proof_kind == "capture_pv":
            verify_capture_pv(index, capture_pv_policy(identity), value["branches"], deadline)
        confirm(
            db,
            root,
            subject,
            game_id,
            position_id,
            alternative,
            deadline,
            identity,
            index,
            full,
            version,
        )
        return requested(view(value, legacy), fork_window, proof_kind)
    except (OSError, ValueError, TypeError, KeyError, sqlite3.Error, TimeoutError, BudgetExceeded):
        return None
