"""Pin both the exact comparison and its transient local source files."""

from .fact_fingerprint import canonical, digest
from .opening_queue_location import location
from .opening_study_source import fingerprint, inputs
from .opening_unfamiliar_measure_state import checked
from .tactical_course_deadline import PreviewDeadline


def current_stamp(db, root, learner, value):
    try:
        directory, _ = location(db, root, learner)
        paths = inputs(directory, value["source_identity"], root)
        return digest(canonical(fingerprint(paths))) == value["source_stamp"]
    except (Exception, PreviewDeadline):
        return False


def verify(db, root, learner, found, value, budget):
    directory, _ = location(db, root, learner)
    paths = inputs(directory, value["source_identity"], root)
    before = fingerprint(paths)
    again = checked(db, root, learner, *found, budget, identity=True)
    keys = ("source_identity", "measurement_hash", "nodes", "played", "other", "reason")
    result = {key: value[key] for key in keys}
    if again.get("status") != "complete" or any(value[key] != again.get(key) for key in keys):
        return None
    if fingerprint(paths) != before:
        return None
    result["source_stamp"] = digest(canonical(before))
    return result
