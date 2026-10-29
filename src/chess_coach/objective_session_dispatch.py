"""Choose a proven continuation or the original session event path."""

from .objective_short_continue import continuation
from .objective_short_event import record as record_continuation
from .unified_session_apply import record_event


def record(db, row, event_id, kind, move):
    resumed = continuation(db, row)
    if resumed is not None:
        return record_continuation(db, row, event_id, kind, move, resumed)
    return record_event(db, row, event_id, kind, move)
