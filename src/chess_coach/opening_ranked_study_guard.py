"""Guard ranked Study inputs while permitting its own exact ledger writes."""

from .deep_selection_source import learner_key
from .opening_context_launch_watch import paths
from .opening_queue_files import read
from .opening_study_source import fingerprint
from .opening_unfamiliar_guard import check as check_source
from .tactical_study_ledger import validate_owned


def guard(context, db, root, learner, directory, version, course):
    budget = context["budget"]
    if fingerprint(context["paths"]) != context["fingerprint"]:
        raise ValueError("opening source changed")
    own = directory / f"opening-study-{version}-intent.json"
    owner = learner_key(learner)
    identity = _directory(directory)
    watched = sorted(path for path in context["paths"] if path not in (directory, own))
    expected = fingerprint(watched)
    seen = [False]

    def check():
        budget.check()
        check_source(db, root, learner, context["guard"], budget)
        current = sorted(
            path for path in paths(root, learner, context["parent"]) if path not in (directory, own)
        )
        if (
            _directory(directory) != identity
            or current != watched
            or fingerprint(current) != expected
        ):
            raise ValueError("opening source changed")
        state = read(own)
        if state is None:
            if seen[0]:
                raise ValueError("opening Study intent changed")
        else:
            seen[0] = True
            validate_owned(state, course, owner)
        budget.check()

    check()
    return check


def _directory(directory):
    info = directory.lstat()
    return info.st_dev, info.st_ino, info.st_mode, info.st_uid
