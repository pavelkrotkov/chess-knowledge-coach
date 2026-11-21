"""Summarize bounded public opening games and their control coverage."""

import json

from .opening_fit_owned_summary import _control
from .opening_fit_replay import inspect
from .style_early_center import MAX_PLY

MAX_GAMES = 10


# Earlier indexes may lack time control; unknown stays unknown.
def _game(db, game, color, control, deadline, decision=None):
    identity, total, metadata = game
    context = json.loads(metadata)
    public_control = context.get("TimeControl")
    unknown = (None, "", "?")
    if decision:
        public_control = _control(public_control)
        unknown = (*unknown, "unknown")
    if public_control not in unknown and public_control != control:
        return "context", False
    if total < MAX_PLY:
        return "short", False
    rows = db.execute(
        "SELECT ply,parent,uci,san FROM moves WHERE game_id=? AND ply<=? ORDER BY ply",
        (identity, MAX_PLY),
    ).fetchall()
    return inspect(rows, color, deadline, decision=decision)


def summarize(db, rows, color, control, deadline, decision):
    counts = {"valid": 0, "available": 0, "short": 0, "inconsistent": 0, "context": 0}
    matched, unknown = 0, 0
    for game in rows[:MAX_GAMES]:
        try:
            state, available = _game(db, game, color, control, deadline, decision)
            if decision:
                public_control = _control(json.loads(game[2]).get("TimeControl"))
                unknown += public_control == "unknown"
                matched += state == "valid" and control != "unknown" and public_control == control
        except (ValueError, TypeError, KeyError, IndexError, AttributeError):
            state, available = "inconsistent", False
            unknown += bool(decision)
        counts[state] += 1
        counts["available"] += available
    result = {**counts, "sampled": min(len(rows), MAX_GAMES), "more": len(rows) > MAX_GAMES}
    if decision:
        result.update(matched_control=matched, unknown_control=unknown)
    return result
