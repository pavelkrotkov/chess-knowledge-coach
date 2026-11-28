"""Read only a current, immutable public opening proof preparation."""

import sqlite3

from .opening_public_capture_pv_current import verify as verify_capture_pv
from .opening_public_capture_pv_policy import policy as capture_pv_policy
from .opening_public_capture_pv_policy import selected as selected_capture_pv
from .opening_public_defense_pv_policy import policy as defense_policy
from .opening_public_defense_pv_policy import selected as selected_defense_pv
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
        selectors = {
            "defense_pv": selected_defense_pv,
            "capture_pv": selected_capture_pv,
            "protection": selected_protection,
        }
        selector = selectors.get(proof_kind)
        if selector is not None:
            value, legacy, full = selector(directory, identity, fork_window)
        else:
            value, legacy, full = selected(
                directory, identity, root, subject, deadline, fork_window, kind=proof_kind
            )
        check(deadline)
        if value is None:
            return None
        if proof_kind in {"mate", "short_mate", "back_rank", "skewer", "double_mate"} and (
            full is None or proof_kind not in value["binding"]["policy"]
        ):
            return None
        pv_policies = {"defense_pv": defense_policy, "capture_pv": capture_pv_policy}
        if proof_kind in pv_policies:
            verify_capture_pv(index, pv_policies[proof_kind](identity), value["branches"], deadline)
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
