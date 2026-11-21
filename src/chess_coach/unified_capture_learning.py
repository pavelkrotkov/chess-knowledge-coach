"""Validate an enrolled owned capture against its immutable worker result."""

import json

from .capture_plan_result import result
from .mate_assessment_events import replay
from .training_feedback_request import validate_request
from .unified_training_owned_capture import SOURCE as SOURCE
from .unified_training_owned_capture import binding

SKILL = "hanging_piece"
POLICY = "unified-owned-capture-schedule-v1"
MAPPER = "unified-owned-capture-evidence-v1"


def proof(db, row, event_id=None):
    item = binding(db, row)
    if item is None:
        raise ValueError("capture training enrollment unavailable")
    observed = replay(db, row)
    checked = result(db, row, observed)
    if checked["status"] not in {"correct", "incorrect"}:
        raise ValueError("capture verification is not available")
    event = db.connection.execute(
        """SELECT event_id,kind,submitted_move,created_at FROM unified_session_events
        WHERE attempt_id=? ORDER BY rowid DESC LIMIT 1""",
        (row["attempt_id"],),
    ).fetchone()
    if not event or event["kind"] != "move" or (event_id and event["event_id"] != event_id):
        raise ValueError("capture answer does not match")
    raw = db.connection.execute(
        "SELECT result_json FROM objective_results WHERE attempt_id=? AND event_id=?",
        (row["attempt_id"], event["event_id"]),
    ).fetchone()
    detail = json.loads(raw[0])
    fact = {
        "status": checked["status"],
        "reason": detail["reason"],
        "verifier": detail["verifier"],
        "event_prefix_hash": detail["event_prefix_hash"],
        "objective_target": json.loads(row["provenance_json"])["objective_target"],
        "gain_threshold": 3,
    }
    _, fingerprint = validate_request(
        row["attempt_id"],
        event["event_id"],
        event["submitted_move"],
        item["item_id"],
        row["subject"],
    )
    return item, event, fact, checked["assistance"] != "unassisted", fingerprint
