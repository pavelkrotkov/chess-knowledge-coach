"""Conservative named pawn geometries, independent of opening labels."""

import chess

from .closed_center_structures import DEFINITIONS as CLOSED_DEFINITIONS
from .closed_center_structures import closed_center_matches
from .legacy_named_structures import DEFINITIONS, _files, legacy_matches
from .sicilian_structures import DEFINITIONS as SICILIAN_DEFINITIONS
from .sicilian_structures import sicilian_matches

VERSION = "1.2.0"
VERSIONS = ("1.0.0", "1.1.0", "1.2.0")


def match_structures(board, *, version=VERSION):
    """Return every supported match; color identifies the relevant side in each rule."""
    if version not in VERSIONS:
        raise ValueError("unknown named structure matcher version")
    white, black = _files(board, chess.WHITE), _files(board, chess.BLACK)
    legacy = legacy_matches(white, black)

    if version == "1.0.0":
        return legacy
    closed = (
        legacy
        + closed_center_matches(white, black, "white", False)
        + closed_center_matches(black, white, "black", True)
    )
    if version == "1.1.0":
        return closed
    return (
        closed
        + sicilian_matches(white, black, "white", "black", False)
        + sicilian_matches(black, white, "black", "white", True)
    )


def definitions(version=VERSION):
    if version not in VERSIONS:
        raise ValueError("unknown named structure matcher version")
    if version == "1.0.0":
        return DEFINITIONS
    closed = {**DEFINITIONS, **CLOSED_DEFINITIONS}
    if version == "1.1.0":
        return closed
    return {**closed, **SICILIAN_DEFINITIONS}
