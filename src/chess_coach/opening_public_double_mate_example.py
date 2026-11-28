"""Certify each qualified double-check mate on its original history."""

from functools import partial

import chess

from .discovery_proof import prove
from .mate_proof_moves import immediate_mates
from .opening_public_mate_example import example
from .opening_public_mate_policy import check


def qualify(board, mate, tick):
    move = board.parse_uci(mate["uci"])
    after = board.copy(stack=True)
    after.push(move)
    king = chess.square_name(after.king(after.turn))
    checkers = sorted(chess.square_name(square) for square in after.checkers())
    proofs = [
        item
        for item in prove(board, move, check=tick)
        if item["mate"]
        and item["double_check"]
        and item["target"] == king
        and item["slider"] in checkers
    ]
    return proofs, checkers


def classify(board, deadline):
    qualified = []
    tick = partial(check, deadline)
    for mate in immediate_mates(board):
        tick()
        proofs, checkers = qualify(board, mate, tick)
        if proofs:
            qualified.append((mate, proofs, checkers))
    tick()
    return qualified


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
        [mate for mate, _, _ in qualified],
        start,
        deadline,
    )
    for proof, (_, discoveries, checkers) in zip(value["alternatives"], qualified, strict=True):
        move = chess.Move.from_uci(proof["move"])
        proof["moving_piece"] = chess.piece_name(board.piece_type_at(move.from_square))
        for discovery in discoveries:
            square = chess.parse_square(discovery["slider"])
            discovery["slider_piece"] = chess.piece_name(board.piece_type_at(square))
        proof["discoveries"] = discoveries
        proof["checkers"] = checkers
    value["side_to_move"] = "white" if board.turn else "black"
    return value
