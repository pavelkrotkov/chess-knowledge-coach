"""Admit only complete, unique one-move exercise objectives."""

import chess


def _single_move(snapshot):
    lines = snapshot["lines"]
    return lines[0] if len(lines) == 1 and len(lines[0].split()) == 1 else None


def mate(snapshot):
    recorded = _single_move(snapshot)
    board = chess.Board(snapshot["prompt_fen"])
    mates = []
    for move in board.legal_moves:
        board.push(move)
        if board.is_checkmate():
            mates.append(move.uci())
        board.pop()
    return recorded is not None and mates == [recorded]


def capture(snapshot):
    recorded = _single_move(snapshot)
    provenance = snapshot["provenance"]
    if snapshot["objective"] != "capture_named_target" or recorded is None:
        return None
    board = chess.Board(snapshot["prompt_fen"])
    target = chess.parse_square(provenance["objective_target"])
    piece = board.piece_at(target)
    captures = [
        move.uci()
        for move in board.legal_moves
        if board.is_capture(move) and move.to_square == target
    ]
    if piece is None or captures != [recorded]:
        return None
    return f"{chess.piece_name(piece.piece_type)} on {chess.square_name(target)}"
