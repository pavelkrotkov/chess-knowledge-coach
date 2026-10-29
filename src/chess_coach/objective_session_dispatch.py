"""Choose a proven continuation or the original session event path."""

from .objective_pawn_continue import continuation as pawn_continuation
from .objective_pawn_event import record as record_pawn
from .objective_short_continue import continuation
from .objective_short_event import record as record_continuation
from .unified_session_apply import record_event


def record(db, row, event_id, kind, move):
    pawn = pawn_continuation(db, row)
    if pawn is not None:
        return record_pawn(db, row, event_id, kind, move, pawn)
    resumed = continuation(db, row)
    if resumed is not None:
        return record_continuation(db, row, event_id, kind, move, resumed)
    return record_event(db, row, event_id, kind, move)
