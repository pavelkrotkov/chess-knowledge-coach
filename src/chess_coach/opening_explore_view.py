"""Build the selected read-only repeated-branch view under one budget."""

from .opening_explore import explore
from .opening_explore_enrich import enrich
from .opening_fork_nomination import nomination


def report(db, root, learner, *, fork=False, revision=False, deadline=None):
    revision = revision or fork == "revision"
    options = {"deadline": deadline} if deadline is not None else {}
    result = explore(db, learner, **options)
    if fork in (True, "1", "revision") or revision:
        result["fork_nomination"] = nomination(db, root, learner, result)
        if revision:
            from .opening_revision_judgments import judgments

            result["revision_judgments"] = judgments(db, root, learner, result)
    else:
        enrich(db, root, learner, result)
    return result
