"""Recover a legal target move without applying its recorded FEN twice."""

from .objective_events import response


def answer(board, session, target):
    detail = response(target)
    if target["kind"] != "move" or detail.get("feedback") != "needs_verification":
        raise ValueError("verification event unavailable")
    if board.is_game_over(claim_draw=True):
        raise ValueError("terminal or claimable history")
    move = _legal_move(board, target["submitted_move"])
    after = board.copy()
    after.push(move)
    if after.fen() != detail.get("fen") or after.fen() != session["current_fen"]:
        raise ValueError("verification position changed")
    return move


def _legal_move(board, text):
    try:
        move = board.parse_uci(text)
    except (TypeError, ValueError):
        raise ValueError("verification move unavailable") from None
    if not move or move not in board.legal_moves:
        raise ValueError("verification move unavailable")
    return move
