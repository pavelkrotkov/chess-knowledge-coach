"""Replay legal ordered moves from a public opening parent."""

import chess

from .opening_storage import position_key


def board_for(parent):
    board = chess.Board(parent)
    if not board.is_valid() or position_key(board) != parent:
        raise ValueError("ordered parent unavailable")
    return board


def advance(board, rows, first):
    moves = []
    for offset, (ply, parent, uci, san) in enumerate(rows):
        if ply != first + offset or position_key(board) != parent:
            raise ValueError("ordered parent differs")
        move = board.parse_uci(uci)
        if move not in board.legal_moves:
            raise ValueError("ordered move is illegal")
        if board.san(move) != san:
            raise ValueError("ordered notation differs")
        moves.append(uci)
        board.push(move)
    return moves
