"""Prepare or read an immutable bounded public opening capture comparison."""

import time

from .fact_fingerprint import canonical, digest
from .opening_public_proof_current import confirm
from .opening_public_proof_files import publish
from .opening_public_proof_read import view
from .opening_public_proof_source import PROOF_SECONDS, SECONDS, binding
from .opening_public_proof_window import evaluate, select
from .opening_recent_capacity import check as capacity
from .style_schedule_budget import history_budget
from .tactical_study_path import planning


def prepare(
    db, root, subject, game_id, position_id, alternative, *, forks=False, fork_window="initial"
):
    start = time.monotonic()
    deadline = start + SECONDS
    directory, _ = planning(root, subject)
    capacity(root, directory)
    version = db.connection.execute("PRAGMA data_version").fetchone()[0]
    db.connection.set_progress_handler(lambda: int(time.monotonic() >= deadline), 1000)
    try:
        with history_budget(deadline=deadline):
            identity, index = binding(
                db, root, subject, game_id, position_id, alternative, deadline
            )
        base = identity
        identity, full = select(base, root, subject, deadline, forks, fork_window)
        result, sample, later_sample = evaluate(
            index, base, identity, full, start, start + PROOF_SECONDS
        )
        payload = {
            "version": identity["version"],
            "binding": identity,
            "sample": sample,
            "branches": result,
        }
        if later_sample is not None:
            payload["fork_sample"] = later_sample
        capacity(root, directory)

        publish(
            directory,
            digest(canonical(identity)),
            payload,
            lambda: confirm(
                db,
                root,
                subject,
                game_id,
                position_id,
                alternative,
                deadline,
                base,
                index,
                full,
                version,
            ),
        )
        return view(payload)
    finally:
        db.connection.set_progress_handler(None, 0)
