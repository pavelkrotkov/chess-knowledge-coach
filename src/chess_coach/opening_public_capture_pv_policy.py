"""Bind and select the versioned public capture-consequences policy."""

from .material_contract import CAPTURE_VERSION
from .opening_public_capture_pv_game import MAX_SEARCHES
from .opening_public_capture_pv_position import MAX_CAPTURES
from .opening_public_proof_versions import current as current_preparation

VERSION = "public-opening-capture-consequences-v1"


def policy(identity, *, forks=False, prevent=False, protection=False, window="initial"):
    if forks or prevent or protection or window != "initial":
        raise ValueError("invalid capture observation selection")
    return {
        **identity,
        "version": VERSION,
        "policy": {
            **identity["policy"],
            "capture_pv": {
                "objective": "capture_named_target",
                "producer_version": CAPTURE_VERSION,
                "searches_per_branch": MAX_SEARCHES,
                "captures_per_position": MAX_CAPTURES,
                "phase_seconds": 10,
                "search_policy": "all-legal-roots-v2",
            },
        },
    }


def selected(directory, identity, window):
    if window != "initial":
        raise ValueError("capture observation window unavailable")
    value, legacy = current_preparation(directory, identity, chosen=policy(identity))
    if value is not None and value["version"] != VERSION:
        return None, value, None
    return value, legacy, None
