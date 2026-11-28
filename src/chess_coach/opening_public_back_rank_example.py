"""Certify every qualified back-rank mate against its original history."""

from .back_rank_terminal import terminal
from .mate_proof_moves import immediate_mates
from .opening_public_mate_example import example
from .opening_public_mate_policy import check


def classify(board, deadline):
    qualified, other = [], 0
    for mate in immediate_mates(board):
        check(deadline)
        board.push_uci(mate["uci"])
        try:
            geometry = terminal(board)
        finally:
            board.pop()
        if geometry:
            qualified.append((mate, geometry))
        else:
            other += 1
    check(deadline)
    return qualified, other


def certificate(
    db, row, binding, source, moves, rows, ply, board, recorded, qualified, start, deadline
):
    value = example(
        db,
        row,
        binding,
        source,
        moves,
        rows,
        ply,
        board,
        recorded,
        [mate for mate, _ in qualified],
        start,
        deadline,
    )
    for proof, (_, geometry) in zip(value["alternatives"], qualified, strict=True):
        proof["geometry"] = geometry
    value["side_to_move"] = "white" if board.turn else "black"
    return value
