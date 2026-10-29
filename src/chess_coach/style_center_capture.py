"""Record legal pawn-on-pawn captures, including en passant."""

import chess


def capture(board, move, ply):
    if board.piece_type_at(move.from_square) != chess.PAWN or not board.is_capture(move):
        return None
    captured = move.to_square
    if board.is_en_passant(move):
        captured += -8 if board.turn == chess.WHITE else 8
    if board.piece_type_at(captured) != chess.PAWN:
        return None
    return {
        "ply": ply,
        "color": "white" if board.turn else "black",
        "move": move.uci(),
        "from": chess.square_name(move.from_square),
        "to": chess.square_name(move.to_square),
        "captured": chess.square_name(captured),
        "central": chess.square_file(move.from_square) in (3, 4)
        or chess.square_file(move.to_square) in (3, 4),
    }
