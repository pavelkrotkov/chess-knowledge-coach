"""Bound the original-history hypothetical threat probe."""

from .material_threats import threats
from .objective_protection_hypothetical import supported

MAX_CAPTURES = 64


def probe(board, *, check=None, inner_check=None):
    if inner_check is not None:
        inner_check()
    if board.is_game_over(claim_draw=True) or board.is_repetition(2):
        return None
    result = threats(board, hypothetical=True, check=check, inner_check=inner_check)
    if not _valid(result):
        return None
    if not supported(board, next(iter(result["targets"])), check=inner_check):
        return None
    return result


def _valid(result):
    return (
        result is not None
        and not result["uncertain"]
        and len(result["targets"]) == 1
        and sum(len(moves) for moves in result["targets"].values()) <= MAX_CAPTURES
    )
