"""Synthetic fork-defense witnesses preserve legal history and uncertainty."""

import chess


def mirror(uci):
    move = chess.Move.from_uci(uci)
    return chess.Move(
        chess.square_mirror(move.from_square),
        chess.square_mirror(move.to_square),
        promotion=move.promotion,
    ).uci()


def line(moves, score):
    return {
        "status": "limited",
        "score_kind": "cp",
        "score_bound": "exact",
        "score_value": score,
        "pv": " ".join(moves),
        "root_move": moves[0],
    }
