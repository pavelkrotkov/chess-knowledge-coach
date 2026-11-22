"""Read the bounded source history for one exact public branch."""

from .opening_check_response_walk import walk
from .opening_profile_queen_replay import _end


def replay(db, game_id, total, decision, move, deadline):
    first = decision["ply"]
    last, status = _end(first, total)
    rows = db.execute(
        "SELECT ply,parent,uci,san FROM moves WHERE game_id=? AND ply<=? ORDER BY ply",
        (game_id, last),
    ).fetchall()
    result = {"status": status, "events": [], "unanswered": False}
    if first < 1 or last < first or len(rows) != last:
        return {**result, "status": "unavailable"}
    try:
        return walk(rows, decision, move, deadline, result)
    except (ValueError, TypeError, IndexError):
        return {**result, "status": "unsupported"}
