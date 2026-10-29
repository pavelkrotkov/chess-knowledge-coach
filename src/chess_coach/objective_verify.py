"""Verify one mate-now answer using a bounded original-history replay."""

from .objective_contract import OWNED_HISTORY, UNAVAILABLE
from .objective_current import current
from .objective_defense_judge import verify as verify_defense
from .objective_defense_source import OBJECTIVE as DEFENSE_OBJECTIVE
from .objective_events import assistance
from .objective_history import before_answer
from .objective_judge import judge
from .objective_provenance import SECONDS as SECONDS
from .objective_provenance import VERSION as VERSION
from .objective_provenance import provenance as provenance
from .objective_short_horizon import verify as verify_short
from .objective_short_source import OBJECTIVE as SHORT_OBJECTIVE


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
    if request["objective_version"] == DEFENSE_OBJECTIVE:
        return verify_defense(board, move, request, events, clock, start, seconds, base)
    if request["objective_version"] == SHORT_OBJECTIVE:
        return verify_short(board, move, request, events, clock, start, seconds, base)
    return judge(board, move, request, events, clock, start, seconds, base)


def unresolved(request, reason):
    return {**provenance(request), "status": "unresolved", "reason": reason}
