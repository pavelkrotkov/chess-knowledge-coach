"""Nominate positional candidates without treating a turn change as a move."""

from .back_rank_scan import mate_scan


def proposal(board, budget):
    if board.is_check() or board.ep_square is not None or board.is_repetition(2):
        return None
    probe = board.copy(stack=False)
    probe.turn = not probe.turn
    if not probe.is_valid() or probe.is_check():
        return None
    result = mate_scan(probe, budget)
    if result["status"] != "complete":
        return None
    return {item["move"]["uci"] for item in result["back_rank"]}
