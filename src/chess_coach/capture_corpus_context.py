"""Nominate an owner-scoped rating context from bounded evidence."""

import json
import os

from .capture_certificate_progress import next_evidence
from .related_capture_context import bounds, rating


def context(db, subject, data, check):
    context = data.get("context")
    if context is not None:
        return context, False
    row, marker = next_evidence(db, subject, data.get("before", 9223372036854775807))
    data["before"] = marker
    if row is None:
        return None, False
    evidence = db.connection.execute(
        "SELECT context_json,position_id FROM evidence_mappings WHERE id=?",
        (row["id"],),
    ).fetchone()
    try:
        turn = json.loads(evidence["context_json"])["pre_move_fen"].split()[1]
        if turn not in {"w", "b"}:
            return None, True
        current_rating = rating(db, evidence["position_id"], "white" if turn == "w" else "black")
    except (TypeError, KeyError, IndexError, ValueError):
        return None, True
    check()
    lower, upper = bounds(current_rating)
    last = db.connection.execute(
        "SELECT version FROM puzzle_corpora WHERE state='ready' ORDER BY version DESC LIMIT 1"
    ).fetchone()
    if last is None:
        return None, True
    context = {
        "lower": lower,
        "upper": upper,
        "last": "",
        "ceiling": last["version"],
        "preferred": os.environ.get("CHESS_CORPUS") or "",
        "first": True,
    }
    data["context"] = context
    return context, True
