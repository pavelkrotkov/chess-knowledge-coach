"""Report whether material evidence still matches its consumed current source."""

import json

from .material_contract import PRODUCER
from .material_policy import MAPPER
from .material_source_marker import source_marker


def evidence_currentness(db, evidence):
    if evidence["mapping_producer"] != MAPPER:
        return None
    facts = [item for item in evidence["facts"] if item["producer"] == PRODUCER]
    if evidence["lifecycle_status"] != "active" or len(facts) != 1:
        return "stale"
    fact = facts[0]
    if fact["detector_status"] != "active":
        return "stale"
    return _check(db, evidence, fact)


def _check(db, evidence, fact):
    row = db.connection.execute(
        "SELECT input_json FROM detector_runs WHERE id=?", (fact["detector_run_id"],)
    ).fetchone()
    try:
        recorded = json.loads(row["input_json"])["detector_input"]["source_marker"]
        current = source_marker(
            db, evidence["position_id"], evidence["game_id"], evidence["subject"]
        )
    except (TypeError, ValueError, KeyError):
        return "stale"
    return "current" if recorded == current else "stale"
