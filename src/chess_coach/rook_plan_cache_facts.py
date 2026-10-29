"""Validate immutable lesson facts before using a replay shortcut."""

import json

from .fact_fingerprint import digest
from .rook_plan_cache_content import content
from .rook_plan_lesson import VERSION
from .rook_plan_publish import PRODUCER


def detector(db, position_id):
    row = db.connection.execute(
        "SELECT * FROM detector_runs WHERE position_id=? AND producer=? AND status='active'",
        (position_id, PRODUCER),
    ).fetchone()
    if (
        row is None
        or row["detector_version"] != VERSION
        or digest(row["input_json"]) != row["input_hash"]
    ):
        return None
    try:
        inputs = json.loads(row["input_json"])["detector_input"]
        inputs.pop("reactivation", None)
        found = content(db, row, position_id)
        return (row, inputs, *found) if found is not None else None
    except (TypeError, ValueError, KeyError, AttributeError):
        return None
