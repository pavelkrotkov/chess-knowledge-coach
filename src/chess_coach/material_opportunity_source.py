"""Read the immutable detector source record for a material opportunity."""

import json


def load_source(db, detector_run_id):
    record = db.connection.execute(
        "SELECT input_json FROM detector_runs WHERE id=?", (detector_run_id,)
    ).fetchone()
    if record is None:
        raise ValueError("material opportunity unavailable")
    try:
        source = json.loads(record["input_json"])["detector_input"]
    except (ValueError, TypeError, KeyError):
        raise ValueError("material opportunity unavailable") from None
    if not isinstance(source, dict):
        raise ValueError("material opportunity unavailable")
    return source
