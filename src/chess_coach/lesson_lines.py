"""Validate a displayed continuation against its reconstructed decision board."""

import chess


def legal_san(fen, moves):
    """Return canonical SAN only when the complete supplied line is legal."""
    if not isinstance(fen, str) or not isinstance(moves, list) or not moves:
        return None
    try:
        board = chess.Board(fen)
        result = []
        for san in moves:
            if not isinstance(san, str):
                return None
            move = board.parse_san(san)
            canonical = board.san(move)
            if canonical != san:
                return None
            result.append(canonical)
            board.push(move)
        return result
    except (ValueError, TypeError):
        return None
