"""Verify one mate-now answer using a bounded original-history replay."""

from .objective_contract import OWNED_HISTORY, UNAVAILABLE
from .objective_current import current
from .objective_events import assistance
from .objective_history import before_answer
from .objective_judge import judge

VERSION = "mate-one-verifier-v1"
SECONDS = 5.0


def compute(db, request, clock, *, seconds=SECONDS):
    start = clock()
    base = provenance(request, seconds)
    try:
        session, events = current(db, request)
        base["assistance"] = assistance(events[:-1])
    except (ValueError, KeyError, TypeError, IndexError):
        return {**base, "status": "unresolved", "reason": "source_unavailable"}
    if request["history_mode"] == UNAVAILABLE:
        return {**base, "status": "unresolved", "reason": "history_unavailable"}
    if request["history_mode"] != OWNED_HISTORY:
        return {**base, "status": "unresolved", "reason": "history_mode_not_supported"}
    try:
        board, move = before_answer(db, session, events)
    except (ValueError, KeyError, TypeError, IndexError):
        return {**base, "status": "unresolved", "reason": "history_unavailable"}
    return judge(board, move, request, events, clock, start, seconds, base)


def provenance(request, seconds=SECONDS):
    return {
        "verifier": VERSION,
        "objective_version": request["objective_version"],
        "history_mode": request["history_mode"],
        "snapshot_hash": request["snapshot_hash"],
        "event_prefix_hash": request["event_prefix_hash"],
        "source_hash": request["source_hash"],
        "limits": {"plies": 1, "compute_timeout_seconds": seconds},
        "learning_eligible": False,
    }


def unresolved(request, reason):
    return {**provenance(request), "status": "unresolved", "reason": reason}
