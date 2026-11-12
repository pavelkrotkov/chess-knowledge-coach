"""Prove each legal reply retains a concrete discovered target capture."""

import chess

from .discovery_branch import witness
from .discovery_witness import proof
from .material_lines import material


def candidates(board, after, move, candidates, replies, check):
    return [
        proof
        for item in candidates
        if (proof := _materialproof(board, after, move, item, replies, check))
    ]


def _materialproof(board, after, move, item, replies, check):
    if after.piece_type_at(item["target"]) == chess.KING:
        return None
    initial = material(board, board.turn)
    witnesses = []
    tick = check or (lambda: None)
    for reply in replies:
        tick()
        if reply.from_square == item["target"] or reply.to_square == item["slider"]:
            return None
        branch = witness(after, reply, item, board.turn, initial, check=check)
        if branch is None:
            return None
        witnesses.append(branch)
    return proof(board, move, item, witnesses, mate=False)
