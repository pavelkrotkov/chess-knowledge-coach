"""Inspect owned diagnostics without changing ordinary or learning state."""

import json

from .deep_selection_source import learner_key
from .purpose_current import current, owned
from .purpose_view_lines import final_view, scout_view
from .recurrence_snapshot import read_snapshot


def _attempt(row, snapshot):
    try:
        result = json.loads(row["result_json"])
        if not isinstance(result, dict):
            raise ValueError("invalid attempt")
        final = final_view(
            result, snapshot["board"], snapshot["position"]["uci"], snapshot["position"]
        )
        if row["status"] == "complete" and (final is None or final["comparison_issue"] is not None):
            return {
                "number": row["attempt_number"],
                "status": "insufficient",
                "detail": "stored_result_invalid",
            }
        return {
            "number": row["attempt_number"],
            "status": row["status"],
            "detail": row["detail"],
            "engine": result.get("engine"),
            "runtime_engine": result.get("runtime_engine"),
            "scout": scout_view(result),
            "final": final,
            "worker_seconds_limit": result.get("worker_seconds_limit"),
            "worker_seconds_elapsed": result.get("worker_seconds_elapsed"),
        }
    except (TypeError, ValueError, KeyError):
        return {
            "number": row["attempt_number"],
            "status": "insufficient",
            "detail": "stored_result_invalid",
        }


def show(db, request_id, learner, *, snapshot=None):
    with read_snapshot(db):
        row = owned(db, request_id, learner)
        base = {
            "request_id": row["id"],
            "game_id": row["game_id"],
            "position_id": row["position_id"],
            "purpose": row["purpose"],
            "policy": row["policy_version"],
            "status": row["status"],
            "scope": "played move and scout nominee only; not a global-best ranking",
            "boundary": "Diagnostic only; no evidence, review, mastery or defense qualification is established.",
        }
        try:
            snapshot, config = current(db, row, learner, snapshot=snapshot)
        except ValueError:
            rows = db.connection.execute(
                "SELECT attempt_number,status,detail FROM purpose_analysis_attempts "
                "WHERE request_id=? ORDER BY attempt_number",
                (request_id,),
            )
            attempts = [
                {
                    "number": item["attempt_number"],
                    "status": item["status"],
                    "detail": item["detail"],
                }
                for item in rows
            ]
            return {**base, "source_state": "stale", "attempts": attempts}
        keys = (
            "scout_nodes",
            "scout_seconds",
            "nodes",
            "time_limit",
            "multipv",
            "threads",
            "hash_mb",
            "min_depth",
            "engine_sha256",
        )
        rows = db.connection.execute(
            "SELECT * FROM purpose_analysis_attempts WHERE request_id=? ORDER BY attempt_number",
            (request_id,),
        )
        return {
            **base,
            "source_state": "current",
            "limits": {key: config.get(key) for key in keys},
            "attempts": [_attempt(item, snapshot) for item in rows],
        }


def listing(db, learner):
    rows = db.connection.execute(
        "SELECT id,position_id,status,created_at FROM purpose_analysis_requests WHERE learner_key=? ORDER BY id DESC LIMIT 100",
        (learner_key(learner),),
    )
    return [dict(row) for row in rows]
