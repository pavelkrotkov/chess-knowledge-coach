"""Recheck one private Study intent against its owner and exact artifact."""

from .opening_exposure_history import historical as opening_historical
from .opening_queue_files import read
from .tactical_exposure_history import historical
from .tactical_exposure_intent_identity import kind
from .tactical_exposure_intent_progress import uncovered
from .tactical_exposure_intent_state import tracked


def inspect_intent(path, root, directory, database, subject, owner, target, cutoff):
    state = read(path)
    source, version = kind(path, state)
    found = tracked(state, owner, target, cutoff)
    if found is not None:
        return found
    if state.get("learner_key") not in (None, owner):
        return "not_recorded"
    if not uncovered(state, {}):
        return "not_recorded"
    if source == "opening":
        return opening_historical(directory, subject, version, state, target, cutoff)
    if source == "tactical":
        return historical(root, directory, database, subject, version, state, target, cutoff)
    return "legacy_coverage_unknown"
