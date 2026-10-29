"""Read stored automatic mate coverage without running a proof."""

import json

from .learner_identity import normalize_identity
from .mate_auto_replay import replay
from .mate_contract import MAPPER, PRODUCER, VERSION
from .mate_inspection_source import checked_board, position_row, source


def automatic_view(db, position_id, learner):
    try:
        position = position_row(db, position_id)
        snapshot, fingerprint = source(db, position, learner)
        checked_board(db, position, snapshot)
        return _view(db, position_id, fingerprint, normalize_identity(learner))
    except (ValueError, TypeError, KeyError):
        return {"status": "unavailable"}


def _view(db, position_id, fingerprint, subject):
    row = db.connection.execute(
        """SELECT d.id,d.input_json,f.payload_json FROM detector_runs d
        JOIN detector_facts f ON f.run_id=d.id WHERE d.position_id=? AND d.producer=?
        AND d.detector_version=? AND d.status='active' AND f.fact_type='bounded_mate'""",
        (position_id, PRODUCER, VERSION),
    ).fetchone()
    if row is None:
        return {"status": "not_processed"}
    source_input = json.loads(row["input_json"])["detector_input"]
    if source_input["source_fingerprint"] != fingerprint:
        return {"status": "stale"}
    fact = json.loads(row["payload_json"])
    if not replay(db, position_id, fingerprint, subject):
        return {"status": "stale"}
    evidence = db.connection.execute(
        """SELECT e.id FROM evidence_mappings e JOIN mapping_runs r ON r.id=e.mapping_run_id
        JOIN evidence_fact_links l ON l.evidence_id=e.id JOIN detector_facts f ON f.id=l.fact_id
        WHERE f.run_id=? AND l.active=1 AND r.producer=? AND r.status='active' AND e.position_id=? AND e.subject=? ORDER BY e.id DESC LIMIT 1""",
        (row["id"], MAPPER, position_id, subject),
    ).fetchone()
    return {
        "status": fact["status"],
        "reason": fact.get("reason"),
        "evidence_id": evidence["id"] if evidence else None,
    }
