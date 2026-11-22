"""Choose the proved terminal event or a narrow root counterexample."""

from .objective_promotion_witness import choose
from .objective_short_history import validate_unchanged_events
from .unified_canonical_forced_counterexample import counterexample
from .unified_canonical_forced_events import final


def reply(board, move, result):
    if move.promotion or result.get("status") != "correct":
        raise ValueError("forced promotion continuation unavailable")
    board.push(move)
    witness = choose(board, result["proof"])
    board.push(board.parse_uci(witness["reply"]))
    return witness["reply"]


def select(row, result, board, move, roots, events):
    remaining = events[len(roots) :]
    if not remaining:
        if row["status"] != "needs_verification":
            raise ValueError("forced promotion terminal state unavailable")
        key = result.get("status"), result.get("reason"), bool(move.promotion)
        if key == ("correct", "promotion_performed", True):
            return "correct", roots[-1], move.uci(), None
        if result.get("status") == "incorrect":
            return "incorrect", roots[-1], None, counterexample(board, move, result)
        raise ValueError("forced promotion continuation pending")
    if result.get("status") != "correct" or result.get("reason") != "forced_promotion_proved":
        raise ValueError("forced promotion root proof unavailable")
    defense = reply(board, move, result)
    validate_unchanged_events(remaining[:-1], board.fen())
    status, end_move = final(remaining[-1], board, defense, row)
    return status, remaining[-1], end_move, defense
