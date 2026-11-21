"""Read bounded indexed history for exact-branch queen observations."""

from .opening_profile_game import EXTENDED_PLIES
from .opening_profile_play import STORED_PLIES
from .opening_profile_queen_walk import walk


def _end(first, total):
    last = min(total, STORED_PLIES, first + EXTENDED_PLIES - 1)
    if total <= last:
        return last, "ended"
    if last == STORED_PLIES and last < first + EXTENDED_PLIES - 1:
        return last, "frontier"
    return last, "cutoff"


def replay(db, game_id, total, decision, move, deadline):
    first = decision["ply"]
    last, status = _end(first, total)
    rows = db.execute(
        "SELECT ply,parent,uci,san FROM moves WHERE game_id=? AND ply<=? ORDER BY ply",
        (game_id, last),
    ).fetchall()
    unavailable = {
        "status": "unavailable",
        "start": None,
        "queenless_observed": False,
        "one_or_imbalanced": False,
    }
    if first < 1 or last < first or len(rows) != last:
        return unavailable
    try:
        return walk(rows, decision, move, status, deadline)
    except (ValueError, TypeError, IndexError):
        return unavailable
