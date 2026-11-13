"""Share one source and deadline across mate and material prevention."""

import time

from .discovery_mate_prevent_source import process_source as mate_source
from .discovery_prevent_followup import remaining
from .material_source import prepare


def combined(db, position_id, learner, *, exclusions, successes=None):
    if db.connection.in_transaction:
        raise RuntimeError("discovery defense detection requires an idle database")
    source = prepare(db, position_id, learner)
    started = time.monotonic()
    mate = mate_source(db, source, started=started)
    if mate["outcome"] == "failure":
        return mate
    return remaining(db, source, started, mate, exclusions, successes)
