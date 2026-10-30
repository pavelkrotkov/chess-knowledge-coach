"""Bind one learner-owned decision to its current full-history cheap source."""

from .deep_selection_source import learner_key, source_snapshot
from .style_history import selected_boards
from .style_history_lines import history_safe


def source(db, position_id, learner):
    key = learner_key(learner)
    position = db.connection.execute(
        "SELECT * FROM positions WHERE id=?", (position_id,)
    ).fetchone()
    if position is None:
        raise ValueError("decision is unavailable")
    snapshot = source_snapshot(db, position["game_id"], learner)
    board = selected_boards(db, position["game_id"], {position_id}).get(position_id)
    if board is None:
        raise ValueError("verified standard-start history is unavailable")
    mover = "white" if board.turn else "black"
    if mover != snapshot["color"]:
        raise ValueError("decision is unavailable")
    move = board.parse_uci(position["uci"])
    if not history_safe(board) or move.promotion:
        raise ValueError("draw-sensitive or promotion history is unsupported")
    return {
        "game_id": position["game_id"],
        "position": position,
        "board": board,
        "learner_key": key,
        "cheap_run_id": snapshot["cheap_run_id"],
        "fingerprint": snapshot["input_fingerprint"],
    }
