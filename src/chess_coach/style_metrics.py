"""Transparent static proxies on equal-horizon legal PV endpoints."""

import chess

HORIZON = 4
VALUES = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3, chess.ROOK: 5, chess.QUEEN: 9}


def endpoint(board, line):
    """Replay the same four plies of a validated line; short lines are unknown."""
    moves = (line.get("pv") or "").split()
    if len(moves) < HORIZON:
        return None
    result = board.copy()
    try:
        for uci in moves[:HORIZON]:
            move = chess.Move.from_uci(uci)
            if move not in result.legal_moves:
                return None
            result.push(move)
    except ValueError:
        return None
    return result


def _attacks(board, color):
    attacks = set()
    for piece in (chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN):
        for square in board.pieces(piece, color):
            attacks.update(
                s
                for s in board.attacks(square)
                if (chess.square_rank(s) >= 4 if color else chess.square_rank(s) <= 3)
            )
    return len(attacks)


def metrics(board, color):
    material = sum(
        value * (len(board.pieces(piece, color)) - len(board.pieces(piece, not color)))
        for piece, value in VALUES.items()
    )
    pieces = sum(
        len(board.pieces(piece, side))
        for piece in VALUES
        if piece != chess.PAWN
        for side in chess.COLORS
    )
    return {"material": material, "pieces": pieces, "enemy_half_attacks": _attacks(board, color)}
