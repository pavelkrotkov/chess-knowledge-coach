"""Verify one mate-now answer using a bounded original-history replay."""

from .objective_contract import UNAVAILABLE
from .objective_current import current
from .objective_events import assistance
from .objective_history_dispatch import replay, supported
from .objective_provenance import SECONDS as SECONDS
from .objective_provenance import VERSION as VERSION
from .objective_provenance import provenance as provenance
from .objective_verify_dispatch import verify


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
    if not supported(request):
        return {**base, "status": "unresolved", "reason": "history_mode_not_supported"}
    try:
        board, move = replay(db, session, events, request)
    except (ValueError, KeyError, TypeError, IndexError):
        return {**base, "status": "unresolved", "reason": "history_unavailable"}
    return verify(board, move, request, events, clock, start, seconds, base, session)


def unresolved(request, reason):
    return {**provenance(request), "status": "unresolved", "reason": reason}
