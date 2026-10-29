"""Replay immutable session moves and automatic replies in order."""

from .objective_events import response


def replay(board, event):
    detail = response(event)
    if event["kind"] == "hint" or detail.get("feedback") == "illegal":
        if detail.get("fen") != board.fen():
            raise ValueError("verification history changed")
        return
    if event["kind"] != "move" or detail.get("feedback") != "line_match":
        raise ValueError("verification history unavailable")
    _push(board, event["submitted_move"])
    reply = detail.get("opponent_move")
    if reply:
        _push(board, reply)
    if detail.get("fen") != board.fen():
        raise ValueError("verification history changed")


def _push(board, text):
    if board.is_game_over(claim_draw=True):
        raise ValueError("terminal or claimable history")
    try:
        move = board.parse_uci(text)
        if not move or move not in board.legal_moves:
            raise ValueError("verification history unavailable")
        board.push(move)
    except (TypeError, ValueError):
        raise ValueError("verification history unavailable") from None
