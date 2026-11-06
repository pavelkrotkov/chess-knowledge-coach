"""Classify a validated four-ply public center window."""

from .opening_profile_center_window import validate
from .style_center_features import features
from .style_center_lines import events


def inspect(rows, first, total, parent, root):
    state, data = validate(rows, first, total, parent, root)
    if data is None:
        return state, None
    original, board, moves = data
    observed = events(original, {"pv": " ".join(moves)})
    opened = set(features(board)["center_open_files"]) - set(
        features(original)["center_open_files"]
    )
    return "valid", {
        "capture": bool(observed["captures"]),
        "recapture": bool(observed["exchanges"]),
        "opened_d": "d" in opened,
        "opened_e": "e" in opened,
        "opened_any": bool(opened),
    }
