"""Recheck one exact, unassisted first-encounter protection result."""

import json

from .mate_assessment_events import replay as replay_events
from .objective_current import current
from .objective_history_dispatch import replay
from .protection_plan_proof import valid
from .related_protection_objective import is_source


def _matches(row, corpus, evidence):
    if row["source_version"] != corpus or not is_source(row):
        return False
    binding = json.loads(row["provenance_json"])["related_protection"]
    return type(binding.get("evidence_id")) is int and binding["evidence_id"] == evidence


def inspect(db, row, corpus, evidence):
    if not _matches(row, corpus, evidence):
        raise ValueError("protection assessment unavailable")
    observed = replay_events(db, row)
    if (observed["hints"], observed["reveals"]) != (0, 0):
        raise ValueError("protection assessment assisted")
    requests = db.connection.execute(
        "SELECT * FROM objective_requests WHERE attempt_id=? ORDER BY rowid LIMIT 2",
        (row["attempt_id"],),
    ).fetchall()
    if len(requests) != 1:
        raise ValueError("protection result unavailable")
    request = requests[0]
    session, events = current(db, request)
    board, move = replay(db, session, events, request)
    stored = db.connection.execute(
        "SELECT result_json FROM objective_results WHERE attempt_id=? AND event_id=?",
        (row["attempt_id"], request["event_id"]),
    ).fetchone()
    if stored is None:
        raise ValueError("protection result pending")
    result = json.loads(stored["result_json"])
    if not valid(result, request, events, board, move, json.loads(row["provenance_json"])):
        raise ValueError("protection result unavailable")
    return {
        "status": result["status"],
        "attempt": row["attempt_id"],
        "evidence_id": evidence,
        "target": json.loads(row["provenance_json"])["objective_target"],
    }
