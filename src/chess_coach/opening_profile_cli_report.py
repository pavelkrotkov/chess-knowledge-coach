"""Run an owner-bound profile against a contained read-only database."""

import time

from .opening_decision import inspect
from .opening_profile_cli_db import private_database
from .opening_profile_source import profile


def report(
    root,
    subject,
    game_id,
    position_id,
    alternative,
    reference,
    *,
    fork_window="initial",
    proof_kind="fork",
):
    with private_database(root, subject) as db:
        connection = db.connection
        deadline = time.monotonic() + 12
        connection.set_progress_handler(lambda: int(time.monotonic() >= deadline), 1000)
        version = connection.execute("PRAGMA data_version").fetchone()[0]
        decision = inspect(db, game_id, position_id, subject, alternative=alternative)
        choice = next(
            (item for item in decision["catalog"]["items"] if item["uci"] == alternative), None
        )
        if choice is None:
            raise ValueError("opening alternative unavailable")
        played = profile(db, root, subject, decision, decision["played_uci"], reference, deadline)
        other = profile(db, root, subject, decision, choice["uci"], reference, deadline)
        prepared = None
        if reference == "recent":
            from .opening_public_proof_read import lookup

            prepared = lookup(
                db,
                root,
                subject,
                game_id,
                position_id,
                alternative,
                deadline,
                fork_window=fork_window,
                proof_kind=proof_kind,
            )
        if connection.execute("PRAGMA data_version").fetchone()[0] != version:
            raise ValueError("opening decision changed")
        result = {
            "reference": reference,
            "decision_ply": decision["ply"],
            "color": decision["color"],
            "played": played,
            "alternative": other,
        }
        if reference == "recent":
            result["public_preparation"] = prepared
        return result


def preparation(root, subject, game_id, position_id, alternative):
    from .opening_preparation import report as inventory

    with private_database(root, subject) as db:
        _, _, _, result = inventory(
            db, root, subject, game_id, position_id, alternative, deadline=time.monotonic() + 12
        )
        return result


def prepare_public(
    root,
    subject,
    game_id,
    position_id,
    alternative,
    *,
    forks=False,
    fork_window="initial",
    prevent=False,
    protection=False,
    capture_pv=False,
    defense_pv=False,
    mate=False,
    short_mate=False,
    back_rank=False,
    skewer=False,
    double_mate=False,
    discovery_material=False,
    discovery_opportunity=False,
):
    from .opening_public_proof import prepare

    with private_database(root, subject) as db:
        return prepare(
            db,
            root,
            subject,
            game_id,
            position_id,
            alternative,
            forks=forks,
            fork_window=fork_window,
            prevent=prevent,
            protection=protection,
            capture_pv=capture_pv,
            defense_pv=defense_pv,
            mate=mate,
            short_mate=short_mate,
            back_rank=back_rank,
            skewer=skewer,
            double_mate=double_mate,
            discovery_material=discovery_material,
            discovery_opportunity=discovery_opportunity,
        )
