"""Find only proved immediate discovered checkmate moves."""

from .discovery_proof import prove


def mating(board, move):
    if move not in board.legal_moves or not board.gives_check(move):
        return []
    after = board.copy()
    after.push(move)
    if not after.is_checkmate():
        return []
    return [proof for proof in prove(board, move) if proof["mate"]]
