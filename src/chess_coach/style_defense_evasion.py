"""Describe a legal root response to check without claiming future safety."""

import chess


def response(board, uci):
    move = chess.Move.from_uci(uci)
    if move not in board.legal_moves:
        raise ValueError("illegal response")
    if not board.is_check():
        return None
    captured = _captured_square(board, move)
    return {
        "move": uci,
        "king_move": board.piece_type_at(move.from_square) == chess.KING,
        "capture": captured is not None,
        "captured_square": chess.square_name(captured) if captured is not None else None,
        "captured_piece": chess.piece_name(board.piece_type_at(captured))
        if captured is not None
        else None,
        "captured_checker": captured in board.checkers() if captured is not None else False,
        "interposition": _interposes(board, move),
        "countercheck": board.gives_check(move),
    }


def _captured_square(board, move):
    if not board.is_capture(move):
        return None
    if board.is_en_passant(move):
        return move.to_square + (-8 if board.turn == chess.WHITE else 8)
    return move.to_square


def _interposes(board, move):
    checkers = board.checkers()
    if len(checkers) != 1:
        return False
    checker = next(iter(checkers))
    if board.piece_type_at(checker) not in (chess.BISHOP, chess.ROOK, chess.QUEEN):
        return False
    return bool(chess.between(checker, board.king(board.turn)) & chess.BB_SQUARES[move.to_square])
