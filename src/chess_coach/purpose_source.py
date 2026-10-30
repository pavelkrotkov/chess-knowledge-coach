"""Bind one learner-owned decision to its verified full game history."""

from .deep_selection_source import MAX_DECISIONS, learner_key
from .purpose_source_binding import history_fingerprint, owned_game
from .style_history import selected_boards
from .style_history_lines import history_safe


def source(db, position_id, learner):
    key = learner_key(learner)
    position = db.connection.execute(
        "SELECT * FROM positions WHERE id=?", (position_id,)
    ).fetchone()
    if position is None:
        raise ValueError("decision is unavailable")
    game, color = owned_game(db, position["game_id"], learner)
    rows = db.connection.execute(
        "SELECT id,ply,fen,uci FROM positions WHERE game_id=? ORDER BY ply", (game["id"],)
    ).fetchall()
    if len(rows) > MAX_DECISIONS:
        raise ValueError("game exceeds the decision limit")
    board = selected_boards(db, game["id"], {position_id}).get(position_id)
    if board is None:
        raise ValueError("verified standard-start history is unavailable")
    mover = "white" if board.turn else "black"
    if mover != color:
        raise ValueError("decision is unavailable")
    move = board.parse_uci(position["uci"])
    if not history_safe(board) or move.promotion:
        raise ValueError("draw-sensitive or promotion history is unsupported")
    return {
        "game_id": game["id"],
        "position": position,
        "board": board,
        "learner_key": key,
        "fingerprint": history_fingerprint(game, color, rows),
    }
