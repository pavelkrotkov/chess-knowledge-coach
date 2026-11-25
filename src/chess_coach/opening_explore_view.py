"""Build the selected read-only repeated-branch view under one budget."""

from .opening_explore import explore
from .opening_explore_enrich import enrich
from .opening_fork_nomination import nomination


def report(db, root, learner, *, fork=False):
    result = explore(db, learner)
    if fork:
        result["fork_nomination"] = nomination(db, root, learner, result)
    else:
        enrich(db, root, learner, result)
    return result
