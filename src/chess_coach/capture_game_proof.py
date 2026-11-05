"""Identify capture opportunities before considering the recorded move."""

from .capture_game_roots import inspect
from .pawn_scope import history_known

MAX_CANDIDATES = 32


def _scan(board, captures, deadline, clock):
    proved, unknown = set(), set()
    for move in captures:
        if clock() >= deadline:
            return None, None, "deadline"
        state = inspect(board, move)
        # Discard even a proved root if its bounded inspection passed the deadline.
        if clock() >= deadline:
            return None, None, "deadline"
        if state == "proved":
            proved.add(move.uci())
        elif state == "unknown":
            unknown.add(move.uci())
    return proved, unknown, None


def _supported(board):
    return board.is_valid() and history_known(board) and not board.is_game_over(claim_draw=True)


def opportunities(board, deadline, clock):
    """Return proved and unresolved roots without consulting the played move."""
    if clock() >= deadline:
        return None, None, "deadline"
    if not _supported(board):
        return None, None, "unsupported_history"
    captures = [move for move in board.legal_moves if board.is_capture(move)]
    if clock() >= deadline:
        return None, None, "deadline"
    if len(captures) > MAX_CANDIDATES:
        return None, None, "candidate_limit"
    return _scan(board, captures, deadline, clock)


def classify(board, played, deadline, clock):
    proved, unknown, reason = opportunities(board, deadline, clock)
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
