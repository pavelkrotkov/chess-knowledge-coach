"""Compare fork source markers when present without replaying the detector."""

import json

from .recurrence_marker import material_state


def fork_state(db, row, fact, parts):
    stored = db.connection.execute(
        "SELECT input_json FROM detector_runs WHERE id=?", (fact["detector_run_id"],)
    ).fetchone()
    try:
        inputs = json.loads(stored[0])["detector_input"]
        if "source_marker" not in inputs:
            return "currentness unverified"
    except (ValueError, TypeError, KeyError, IndexError):
        return "currentness unverified"
    state = material_state(db, row, fact, parts)
    return "marker matches; proof not replayed" if state == "marker matches" else state
