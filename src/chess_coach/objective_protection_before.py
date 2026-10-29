"""Bound the original-history hypothetical threat probe."""

from .material_threats import threats
from .objective_protection_hypothetical import supported

MAX_CAPTURES = 64


def probe(board):
    if board.is_game_over(claim_draw=True) or board.is_repetition(2):
        return None
    result = threats(board, hypothetical=True)
    if not _valid(result):
        return None
    if not supported(board, next(iter(result["targets"]))):
        return None
    return result


def _valid(result):
    return (
        result is not None
        and not result["uncertain"]
        and len(result["targets"]) == 1
        and sum(len(moves) for moves in result["targets"].values()) <= MAX_CAPTURES
    )
