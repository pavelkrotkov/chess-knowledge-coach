"""Validate legal lines and narrowly verifiable terminal objectives."""

import chess


def validate_line(initial, line, objective):
    if not isinstance(line, str) or not 1 <= len(line.split()) <= 64:
        raise ValueError("invalid solution line")
    board = initial.copy()
    promoted = False
    moves = []
    mover = None
    for text in line.split():
        move = chess.Move.from_uci(text)
        if move not in board.legal_moves:
            raise ValueError("illegal solution move")
        mover = board.turn
        promoted |= move.promotion is not None and mover == initial.turn
        board.push(move)
        moves.append(move.uci())
    _outcome(board, initial, mover, promoted, objective)
    return " ".join(moves)


def _outcome(board, initial, mover, promoted, objective):
    if objective == "checkmate" and (not board.is_checkmate() or mover != initial.turn):
        raise ValueError("line does not end in checkmate")
    if objective == "promotion" and not promoted:
        raise ValueError("line does not contain promotion")
