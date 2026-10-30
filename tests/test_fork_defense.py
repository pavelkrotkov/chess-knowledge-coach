"""Synthetic fork-defense witnesses preserve legal history and uncertainty."""

import chess


def mirror(uci):
    move = chess.Move.from_uci(uci)
    return chess.Move(
        chess.square_mirror(move.from_square),
        chess.square_mirror(move.to_square),
        promotion=move.promotion,
    ).uci()
