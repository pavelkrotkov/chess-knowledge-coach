"""Read bounded direct references to existing owned capture sources."""

from copy import deepcopy

from .learner_identity import normalize_identity
from .objective_capture_contract import (
    GAIN_OBJECTIVE,
    GAIN_VERSION,
    TARGET_VERSION,
    valid_key,
)


def _reference(subject, version, key, snapshot):
    if (
        normalize_identity(subject) != subject
        or version not in {TARGET_VERSION, GAIN_VERSION}
        or not isinstance(key, str)
        or not valid_key(version, key)
        or not isinstance(snapshot, str)
        or len(snapshot) != 64
    ):
        return None
    return {"id": int(key), "version": version, "snapshot_hash": snapshot}


def matches(entry, reference):
    """Reconstruct the existing version-specific snapshot for an exact reference."""
    from .unified_source_current import snapshot_hash

    snapshot = deepcopy(entry["snapshot"])
    if reference["version"] == GAIN_VERSION:
        snapshot["objective"] = "bounded_material_gain"
        snapshot["provenance"]["objective_version"] = GAIN_OBJECTIVE
        snapshot["provenance"]["capture_objective"] = "bounded_material_gain"
    return snapshot_hash(snapshot) == reference["snapshot_hash"]


def session_marker(value):
    if not isinstance(value, list) or len(value) != 3:
        return []
    if not all(isinstance(item, str) and item for item in value[:2]):
        return []
    if type(value[2]) is not int or not valid_key(TARGET_VERSION, str(value[2])):
        return []
    return value
