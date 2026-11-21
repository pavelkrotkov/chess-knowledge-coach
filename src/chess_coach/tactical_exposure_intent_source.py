"""Recheck one tactical Study intent against its owner and artifact."""

from .opening_queue_files import read
from .tactical_exposure_history import historical
from .tactical_exposure_intent_state import tracked
from .tactical_study_receipt import NAME


def inspect_intent(path, root, directory, database, subject, owner, target, cutoff):
    match = NAME.fullmatch(path.name)
    state = read(path)
    if match is None or not isinstance(state, dict) or state.get("course_sha256") != match.group(1):
        return "coverage_unavailable"
    found = tracked(state, owner, target, cutoff)
    if found is not None:
        return found
    if state.get("learner_key") not in (None, owner) or state.get("study") is None:
        return "not_recorded"
    return historical(root, directory, database, subject, match.group(1), state, target, cutoff)
