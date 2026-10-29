"""Reject material evidence whose consumed source is no longer current."""

import json

from .material_contract import PRODUCER
from .material_source_marker import source_marker


def source_reason(db, row):
    if not row["material_fact_count"]:
        return None
    records = db.connection.execute(
        """SELECT d.input_json FROM evidence_fact_links l
        JOIN detector_facts f ON f.id=l.fact_id JOIN detector_runs d ON d.id=f.run_id
        WHERE l.evidence_id=? AND d.producer=?""",
        (row["id"], PRODUCER),
    ).fetchall()
    if len(records) != row["material_fact_count"]:
        return "material_source_stale"
    try:
        current = source_marker(db, row["position_id"], row["game_id"], row["subject"])
        if any(
            json.loads(record["input_json"])["detector_input"]["source_marker"] != current
            for record in records
        ):
            return "material_source_stale"
    except (ValueError, TypeError, KeyError):
        return "material_source_stale"
    return None
