"""Prepare attributable material inputs with current cheap/deep provenance."""

from .decision_history import decision_board
from .decision_inspection import inspect_decision
from .deep_selection_source import MAX_DECISIONS, source_snapshot
from .material_context import NotLearnerDecision as NotLearnerDecision
from .material_context import context_for_position
from .material_source_analysis import current_lines
from .material_source_marker import source_marker


def prepare(db, position_id, learner, *, history=None):
    if history is not None and (history.db is not db or history.learner != learner):
        raise ValueError("preview history scope differs")
    position = db.connection.execute(
        "SELECT * FROM positions WHERE id=?", (position_id,)
    ).fetchone()
    if position is None:
        raise ValueError("decision unavailable")
    game_id = position["game_id"]
    if db.connection.execute(
        "SELECT 1 FROM positions WHERE game_id=? LIMIT 1 OFFSET ?", (game_id, MAX_DECISIONS)
    ).fetchone():
        raise ValueError("game exceeds material verification limit")
    _context(db, game_id, position_id, learner, history)
    marker = source_marker(db, position_id, game_id, learner)
    context = _context(db, game_id, position_id, learner, history)
    cheap = source_snapshot(db, game_id, learner)
    board = decision_board(db, position) if history is None else history.board(game_id, position_id)
    analysis = inspect_decision(
        db, position_id, run_id=cheap["cheap_run_id"], learner=learner, _history=history
    )
    best, played, provenance = current_lines(db, analysis, cheap["cheap_run_id"], board)
    if source_marker(db, position_id, game_id, learner) != marker:
        raise ValueError("source changed during preparation")
    return {
        "position_id": position_id,
        "game_id": game_id,
        "context": context,
        "board": board,
        "best": best,
        "played": played,
        "provenance": provenance,
        "source_marker": marker,
        "cheap_run_id": cheap["cheap_run_id"],
    }


def _context(db, game_id, position_id, learner, history):
    if history is None:
        return context_for_position(db, game_id, position_id, learner)
    return history.context(game_id, position_id)
