"""Identify capture opportunities before considering the recorded move."""

import chess

from .capture_game_roots import inspect
from .pawn_scope import history_known
from .related_capture_position import _material, _phase

# Bump when qualification or played-choice semantics change.
VERSION = "direct-capture-v3"
MAX_CANDIDATES = 32


def _detail(board, move, state):
    target = board.piece_at(move.to_square)
    mover = board.piece_at(move.from_square)
    mechanism = ("checking" if board.gives_check(move) else "direct") if mover and target else None
    geometry = (
        [
            abs(chess.square_file(move.to_square) - chess.square_file(move.from_square)),
            abs(chess.square_rank(move.to_square) - chess.square_rank(move.from_square)),
        ]
        if mover and target
        else None
    )
    return [
        move.uci(),
        target.symbol() if target else None,
        state,
        mechanism,
        mover.piece_type if mover else None,
        geometry,
    ]


def _scan(board, captures, deadline, clock, details=None):
    proved, unknown = set(), set()
    for move in captures:
        if clock() >= deadline:
            return None, None, "deadline"
        state = inspect(board, move)
        # Discard even a proved root if its bounded inspection passed the deadline.
        if clock() >= deadline:
            return None, None, "deadline"
        if details is not None:
            details["roots"].append(_detail(board, move, state))
            if clock() >= deadline:
                return None, None, "deadline"
        if state == "proved":
            proved.add(move.uci())
        elif state == "unknown":
            unknown.add(move.uci())
    return proved, unknown, None


def _supported(board):
    return board.is_valid() and history_known(board) and not board.is_game_over(claim_draw=True)


def opportunities(board, deadline, clock, *, details=None):
    """Return proved and unresolved roots without consulting the played move."""
    if clock() >= deadline:
        return None, None, "deadline"
    if not _supported(board):
        return None, None, "unsupported_history"
    captures = [move for move in board.legal_moves if board.is_capture(move)]
    if details is not None:
        details["total"] = len(captures)
    if clock() >= deadline:
        return None, None, "deadline"
    if len(captures) > MAX_CANDIDATES:
        return None, None, "candidate_limit"
    return _scan(board, captures, deadline, clock, details)


def _outcome(proved, unknown, reason, played):
    if reason:
        return "unknown", reason
    # Unresolved capture roots cannot establish that no opportunity existed.
    if not proved:
        return ("unknown", "unresolved_capture") if unknown else ("no_opportunity", None)
    if played in proved:
        return "played", None
    if played in unknown:
        return "opportunity_unresolved", "played_capture_unresolved"
    # Another move can have merits; this is not a mistake classification.
    return "other", None


def classify(board, played, deadline, clock, *, details=None):
    if details is None:
        return _outcome(*opportunities(board, deadline, clock), played)
    details.update(
        side="white" if board.turn else "black",
        played=played,
        material=_material(board),
        phase=_phase(board),
        total=None,
        roots=[],
    )
    proved, unknown, reason = opportunities(board, deadline, clock, details=details)
    if reason:
        details["roots"] = []
    details["unsearched"] = (
        None if details["total"] is None else details["total"] - len(details["roots"])
    )
    details["reason"] = reason
    return _outcome(proved, unknown, reason, played)
