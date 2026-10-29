"""Apply the announced one-move objective to a verified legal board."""

from .fact_fingerprint import canonical, digest
from .objective_events import response


def judge(board, move, request, events, clock, start, seconds, base):
    reason = _scope_reason(board, request, events)
    if reason:
        return {**base, "status": "unresolved", "reason": reason}
    if clock() - start > seconds:
        return {**base, "status": "unresolved", "reason": "timeout"}
    history_hash = digest(
        canonical(
            {
                "root": board.root().fen(en_passant="fen", promoted=True),
                "moves": [m.uci() for m in board.move_stack],
            }
        )
    )
    san = board.san(move)
    board.push(move)
    mate = board.is_checkmate()
    if clock() - start > seconds:
        return {**base, "status": "unresolved", "reason": "timeout"}
    return {
        **base,
        "status": "correct" if mate else "incorrect",
        "reason": "immediate_checkmate" if mate else "not_immediate_checkmate",
        "history_hash": history_hash,
        "move": move.uci(),
        "san": san,
    }


def _scope_reason(board, request, events):
    if any(response(event).get("feedback") == "line_match" for event in events[:-1]):
        return "objective_horizon_changed"
    color = "white" if board.turn else "black"
    return "learner_turn_changed" if color != request["learner_color"] else None
