"""Expose the pawn's controlled squares and a legal one-step advance."""

import chess


def geometry(board, target):
    square = chess.parse_square(target["square"])
    owner = target["color"] == "white"
    control = [chess.square_name(s) for s in board.attacks(square)]
    destination = square + (8 if owner else -8)
    advance = None
    if board.turn == owner and 0 <= destination < 64:
        move = chess.Move(square, destination)
        if move in board.legal_moves:
            advance = board.san(move)
    return {"controlled_squares": control, "legal_advance": advance}


def supported_pieces(board, target):
    square = chess.parse_square(target["square"])
    owner = target["color"] == "white"
    return [
        other
        for other in board.attacks(square)
        if board.color_at(other) == owner
        and board.piece_type_at(other) in (chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN)
    ]
