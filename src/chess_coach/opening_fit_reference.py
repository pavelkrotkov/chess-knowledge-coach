"""Replay exact public first-turn branches for early central-capture availability."""

import json
import sqlite3

from .opening_fit_reference_counts import summarize
from .opening_fit_reference_rows import selected
from .opening_profile_lookup import _validate, guard
from .opening_profile_store import TRANSFORM
from .style_early_center import MAX_PLY


def sample(
    path,
    parent,
    move,
    color,
    control,
    deadline,
    *,
    decision_ply=None,
    transform=TRANSFORM,
    source_metadata=None,
    match_context=False,
):
    db = sqlite3.connect(path.as_uri() + "?mode=ro&immutable=1", uri=True, timeout=1)
    try:
        guard(db, deadline)
        metadata = {
            k: json.loads(v) for k, v in db.execute("SELECT key,value FROM metadata LIMIT 32")
        }
        _validate(metadata, transform=transform, source_metadata=source_metadata)
        ply = decision_ply if decision_ply is not None else (1 if color == "white" else 2)
        if not 1 <= ply <= MAX_PLY or (ply % 2 == 1) != (color == "white"):
            raise ValueError("opening decision ply unavailable")
        rows, coverage = selected(db, parent, move, ply, control, match_context)
        decision = {"parent": parent, "move": move, "ply": ply} if decision_ply else None
        result = summarize(db, rows, color, control, deadline, decision)
        if coverage is not None:
            result.update(coverage, source_coverage=metadata["coverage"])
        return result
    finally:
        db.close()
