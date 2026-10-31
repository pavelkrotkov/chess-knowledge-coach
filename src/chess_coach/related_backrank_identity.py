"""Track the opening mover through a legal supplied witness."""

import chess


def replay(prompt, line):
    board = chess.Board(prompt)
    first = chess.Move.from_uci(line[0])
    tracked = first.from_square
    promoted = False
    for text in line:
        move = chess.Move.from_uci(text)
        if tracked is not None and move.from_square == tracked and move.promotion:
            promoted = True
        tracked = _advance(board, move, tracked)
        board.push(move)
    return board, tracked, promoted


def _advance(board, move, tracked):
    if tracked is None:
        return None
    if move.from_square == tracked:
        return move.to_square
    if move.to_square == tracked:
        return None
    if board.is_en_passant(move):
        captured = move.to_square + (-8 if board.turn == chess.WHITE else 8)
        if tracked == captured:
            return None
    return tracked
