"""Verify indexed first-turn matches against the owned original game."""

import chess

from .learner_context import decision_context_boards
from .opening_explore_guard import require_bounded
from .opening_storage import position_key

LIMIT = 32


def _matches(db, learner, game_id, color, parent, uci):
    require_bounded(db, game_id)
    turns = decision_context_boards(db, game_id, learner=learner)
    first, board = next(turns)
    if first["learner_color"] != color:
        raise ValueError("history ownership unavailable")
    if board.fen() != chess.Board().fen():
        return False
    if color == "white":
        return bool(first["subject"]) and first["played_move"] == uci
    second, board = next(turns)
    return (
        bool(second["subject"]) and position_key(board) == parent and second["played_move"] == uci
    )


def seen(db, subject, choice, color, parent):
    prefix = choice["child_key"] + " "
    rows = db.connection.execute(
        f"""SELECT g.id FROM positions p INDEXED BY idx_positions_fen_game
        JOIN games g ON g.id=p.game_id WHERE p.fen>=? AND p.fen<? AND p.ply=?
        AND g.variant='Standard'
        AND (length(substr(CAST(g.{color} AS BLOB),1,257))>256
             OR normalized_opening_owner(g.{color})=?) LIMIT ?""",
        (prefix, prefix + "\uffff", 1 if color == "white" else 2, subject, LIMIT + 1),
    ).fetchall()
    if len(rows) > LIMIT:
        return True
    for row in rows:
        try:
            if _matches(db, subject, row["id"], color, parent, choice["uci"]):
                return True
        except (ValueError, TypeError, IndexError, StopIteration):
            return True
    return False
