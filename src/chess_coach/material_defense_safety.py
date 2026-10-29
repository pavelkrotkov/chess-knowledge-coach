"""Validate ordinary defensive moves and newly exposed material."""

import chess

from .material_exchange_rules import has_legal_recapture


def safe_defense_move(board, move, before):
    if not _ordinary(board, move):
        return False
    if not board.is_capture(move):
        return True
    attackers = {
        chess.Move.from_uci(text).from_square
        for moves in before["targets"].values()
        for text in moves
    }
    return move.to_square in attackers and not has_legal_recapture(board, move)


def new_other_threat(before, following, protected):
    prior = set(before["targets"]) | set(before["uncertain"])
    after = set(following["targets"]) | set(following["uncertain"])
    return bool(after - prior - {protected})


def _ordinary(board, move):
    return (
        move in board.legal_moves
        and not board.gives_check(move)
        and not move.promotion
        and not board.is_en_passant(move)
    )
