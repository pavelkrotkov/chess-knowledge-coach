"""Validate the exact enrolled owned-fork result and full event history."""

import json

from .fork_history_result import details
from .mate_assessment_events import replay
from .training_feedback_request import validate_request
from .unified_fork_bounds import bounds
from .unified_fork_learning_events import answer, assistance
from .unified_training_owned_fork import SOURCE as SOURCE
from .unified_training_owned_fork import binding

SKILL = "fork"
POLICY = "unified-owned-fork-schedule-v1"
MAPPER = "unified-owned-fork-evidence-v1"


def proof(db, row, event_id=None):
    item = binding(db, row)
    if item is None:
        raise ValueError("fork training enrollment unavailable")
    observed = replay(db, row)
    status, _ = details(db, row, check=None)
    if status not in {"correct", "incorrect"}:
        raise ValueError("fork verification is not available")
    event = answer(db, row, event_id)
    raw = db.connection.execute(
        "SELECT result_json FROM objective_results WHERE attempt_id=? AND event_id=?",
        (row["attempt_id"], event["event_id"]),
    ).fetchone()
    detail = json.loads(raw[0])
    data = json.loads(row["provenance_json"])
    if not bounds(detail, data["fork_anchor"]):
        raise ValueError("fork proof bounds unavailable")
    assisted = assistance(detail, observed)
    fact = {
        "status": status,
        "reason": detail["reason"],
        "verifier": detail["verifier"],
        "event_prefix_hash": detail["event_prefix_hash"],
        "history_hash": detail["history_hash"],
        "fork_attacker": data["fork_attacker"],
        "fork_anchor": data["fork_anchor"],
        "gain_threshold": 3,
        "limits": detail["limits"],
        "proof": detail.get("proof"),
    }
    _, fingerprint = validate_request(
        row["attempt_id"],
        event["event_id"],
        event["submitted_move"],
        item["item_id"],
        row["subject"],
    )
    return item, event, fact, assisted, fingerprint
