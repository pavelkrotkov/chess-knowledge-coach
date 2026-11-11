"""A narrow, replayable miss of a certified unfamiliar fork objective."""

import chess

VERSION = "certified-fork-miss-v1"


def _valid(board, move, attacker, anchor):
    piece, target = board.piece_at(attacker), board.piece_at(anchor)
    return bool(
        move
        and move in board.legal_moves
        and piece == chess.Piece(chess.KNIGHT, board.turn)
        and target is not None
        and target.color != board.turn
    )


def reason(board, move, attacker, anchor):
    if not _valid(board, move, attacker, anchor):
        return None
    if move.from_square != attacker:
        return "named_attacker_not_moved"
    after = board.copy(stack=False)
    after.push(move)
    if after.piece_at(anchor) == board.piece_at(anchor) and anchor not in after.attacks(
        move.to_square
    ):
        return "named_target_not_attacked"
    return None
