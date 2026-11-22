"""Complete only a proved, whole canonical forced-promotion attempt."""

from .objective_events import assistance, prefix, prefix_hash
from .training_feedback_request import validate_request
from .unified_canonical_forced_root import root
from .unified_canonical_forced_terminal import select
from .unified_training_canonical_promotion import FORCED_SOURCE, binding

SOURCE = FORCED_SOURCE
SKILL = "promotion"
POLICY = "unified-canonical-forced-promotion-schedule-v1"
MAPPER = "unified-canonical-forced-promotion-evidence-v1"


def proof(db, row, event_id=None):
    item = binding(db, row, forced=True)
    if item is None:
        raise ValueError("forced promotion enrollment unavailable")
    request, result, board, move, roots = root(db, row)
    last = db.connection.execute(
        "SELECT event_id FROM unified_session_events WHERE attempt_id=? ORDER BY rowid DESC LIMIT 1",
        (row["attempt_id"],),
    ).fetchone()
    events = prefix(db, row["attempt_id"], last[0])
    if events[: len(roots)] != roots:
        raise ValueError("forced promotion event prefix changed")
    status, event, end_move, defense = select(row, result, board, move, roots, events)
    if event_id is not None and event["event_id"] != event_id:
        raise ValueError("forced promotion terminal event does not match")
    level = assistance(events)
    if (
        level == "assisted_unknown"
        or sum(event["kind"] == "hint" for event in events) != row["hints_used"]
    ):
        raise ValueError("forced promotion assistance unavailable")
    fact = {
        "status": status,
        "reason": result["reason"],
        "verifier": result["verifier"],
        "history_hash": result["history_hash"],
        "event_prefix_hash": result["event_prefix_hash"],
        "event_history_hash": prefix_hash(events),
        "root_event_id": request["event_id"],
        "root_move": move.uci(),
        "reply": defense,
        "final_move": end_move,
    }
    _, fingerprint = validate_request(
        row["attempt_id"],
        event["event_id"],
        event["submitted_move"],
        item["item_id"],
        row["subject"],
    )
    return item, event, fact, level != "unassisted", fingerprint
