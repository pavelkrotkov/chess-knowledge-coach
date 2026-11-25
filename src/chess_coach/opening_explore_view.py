"""Build the selected read-only repeated-branch view under one budget."""

from .opening_explore import explore
from .opening_explore_enrich import enrich
from .opening_fork_nomination import nomination


def report(db, root, learner, *, fork=False, revision=False):
    revision = revision or fork == "revision"
    result = explore(db, learner)
    if fork in (True, "1", "revision") or revision:
        result["fork_nomination"] = nomination(db, root, learner, result)
        if revision:
            from .opening_revision_judgments import judgments

            result["revision_judgments"] = judgments(db, root, learner, result)
    else:
        enrich(db, root, learner, result)
    return result
