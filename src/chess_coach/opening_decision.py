"""Inspect one owned opening decision without requesting engine work."""

from .opening_decision_analysis import comparison
from .opening_decision_catalog import catalog
from .opening_decision_source import source
from .recurrence_cursor import _valid_id
from .style_history_lines import history_safe


def inspect(db, game_id, position_id, learner):
    if not _valid_id(game_id) or not _valid_id(position_id):
        raise ValueError("opening decision unavailable")
    version = db.connection.execute("PRAGMA data_version").fetchone()[0]
    opening, context, board = source(db, game_id, position_id, learner)
    if not history_safe(board):
        raise ValueError("opening history unavailable")
    played = board.parse_uci(context["played_move"])
    result = catalog(db, opening["dataset_id"], board, context["played_move"])
    analysis = comparison(db, learner, context, board, result["items"])
    if db.connection.execute("PRAGMA data_version").fetchone()[0] != version:
        raise ValueError("opening source changed during inspection")
    return {
        "game_id": game_id,
        "position_id": position_id,
        "ply": context["ply"],
        "color": context["learner_color"],
        "fen": context["pre_move_fen"],
        "played": board.san(played),
        "played_uci": context["played_move"],
        "opening": opening,
        "catalog": result,
        "analysis": analysis,
    }
