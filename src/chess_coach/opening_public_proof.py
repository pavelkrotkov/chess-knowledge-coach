"""Prepare or read an immutable bounded public opening capture comparison."""

import time

from .fact_fingerprint import canonical, digest
from .opening_public_proof_files import publish
from .opening_public_proof_prepare import branches
from .opening_public_proof_read import view
from .opening_public_proof_source import PROOF_SECONDS, SECONDS, binding, check
from .opening_public_proof_versions import combined
from .opening_recent_capacity import check as capacity
from .style_schedule_budget import history_budget
from .tactical_study_path import planning


def prepare(db, root, subject, game_id, position_id, alternative, *, forks=False):
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
        identity = combined(base) if forks else base
        result, sample = branches(index, identity, start, start + PROOF_SECONDS)
        payload = {
            "version": identity["version"],
            "binding": identity,
            "sample": sample,
            "branches": result,
        }
        capacity(root, directory)

        def confirm():
            check(deadline)
            with history_budget(deadline=deadline):
                current, actual = binding(
                    db, root, subject, game_id, position_id, alternative, deadline
                )
            if current != base or actual != index:
                raise ValueError("public preparation source changed")
            if db.connection.execute("PRAGMA data_version").fetchone()[0] != version:
                raise ValueError("owned decision changed")

        publish(directory, digest(canonical(identity)), payload, confirm)
        return view(payload)
    finally:
        db.connection.set_progress_handler(None, 0)
