"""Validate an owned decision from a report-scoped reconstructed board."""

from .deep_selection_source import learner_key
from .style_history_lines import history_safe


def snapshot_item(db, game_id, color, learner, fingerprint, position_id, board):
    position = db.connection.execute(
        "SELECT * FROM positions WHERE id=?", (position_id,)
    ).fetchone()
    if position is None or position["game_id"] != game_id:
        return None
    if ("white" if board.turn else "black") != color:
        return None
    try:
        move = board.parse_uci(position["uci"])
    except ValueError:
        return None
    if not history_safe(board) or move.promotion:
        return None
    return {
        "game_id": game_id,
        "position": position,
        "board": board,
        "learner_key": learner_key(learner),
        "fingerprint": fingerprint,
    }
