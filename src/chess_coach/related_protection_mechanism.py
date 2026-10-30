"""Identify the supported action that saves a specified threatened piece."""

import chess


def mechanism(board, move, target, threat):
    if move.from_square == target:
        return "move_threatened_piece"
    if board.is_capture(move):
        return "capture_attacker"
    if _blocks_attacker(move, target, threat):
        return "interpose"
    after = board.copy(stack=True)
    after.push(move)
    if target in after.attacks(move.to_square):
        return "guard"
    return "indirect_defense"


def _blocks_attacker(move, target, threat):
    attacks = threat["targets"][target]
    return any(
        chess.BB_SQUARES[move.to_square]
        & chess.between(chess.Move.from_uci(text).from_square, target)
        for text in attacks
    )
