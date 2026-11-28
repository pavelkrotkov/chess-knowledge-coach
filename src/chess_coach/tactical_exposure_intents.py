"""Read bounded per-chapter Study intent history at an answer boundary."""

from itertools import chain, islice
from pathlib import Path

from .deep_selection_source import learner_key
from .fact_fingerprint import digest
from .opening_queue_files import read
from .opening_queue_location import location
from .tactical_exposure_intent_identity import kind
from .tactical_exposure_intent_source import inspect_intent
from .tactical_exposure_intent_state import tracked
from .tactical_study_intents import MAX_INTENTS


def _root(db):
    path = getattr(db, "path", None)
    if path is None or str(path) == ":memory:":
        return None
    path = Path(path).resolve()
    if path.parent.name != "data" or path.parent.parent.name != ".runtime":
        return None
    return path.parent.parent.parent


def check_intents(db, subject, key, cutoff, *, ignore_artifact=None):
    root = _root(db)
    if root is None:
        return "not_recorded"
    directory, database = location(db, root, subject)
    paths = list(
        islice(
            chain(
                directory.glob("tactical-study-*-intent.json"),
                directory.glob("opening-study-*-intent.json"),
            ),
            MAX_INTENTS + 1,
        )
    )
    if len(paths) > MAX_INTENTS:
        return "coverage_unavailable"
    # The original publisher used a single fixed, owner-private intent.
    legacy = directory / "poc-study-336-intent.json"
    if legacy.exists():
        paths.append(legacy)
    owner, target, result = learner_key(subject), digest(key), "not_recorded"
    for path in paths:
        if _own_intent(
            path,
            ignore_artifact,
            owner,
            target,
            cutoff,
            root=root,
            directory=directory,
            database=database,
            subject=subject,
        ):
            continue
        found = inspect_intent(path, root, directory, database, subject, owner, target, cutoff)
        if found == "provided":
            return found
        if found != "not_recorded":
            result = found
    return result


def _own_intent(path, artifact, owner, target, cutoff, *, root, directory, database, subject):
    if artifact is None:
        return False
    state = read(path)
    source, version = kind(path, state)
    delivery = state.get("tactical_delivery")
    if source != "tactical" or not isinstance(delivery, dict) or delivery.get("owner") != owner:
        return False
    if version != artifact:
        from .tactical_study_parts_binding import member

        if not member(root, directory, database, subject, artifact, state):
            return False
    return tracked(state, owner, target, cutoff) is not None
