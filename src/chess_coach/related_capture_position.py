"""Compare learner-side material, phase and capture geometry."""

import chess


def _features(board, move, mover, target):
    dx = abs(chess.square_file(move.to_square) - chess.square_file(move.from_square))
    dy = abs(chess.square_rank(move.to_square) - chess.square_rank(move.from_square))
    return {
        "mover": mover.piece_type,
        "target": target.piece_type,
        "geometry": (dx, dy),
        "material": _material(board),
        "phase": _phase(board),
    }


def _material(board):
    return tuple(
        len(board.pieces(piece, color))
        for color in (board.turn, not board.turn)
        for piece in (chess.PAWN, chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN)
    )


def _phase(board):
    pieces = sum(
        len(board.pieces(p, c))
        for p in (chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN)
        for c in (chess.WHITE, chess.BLACK)
    )
    return "endgame" if pieces <= 6 else "middlegame"


def compatible(source, candidate):
    return bool(
        candidate
        and (source["mover"], source["target"]) == (candidate["mover"], candidate["target"])
    )


def similarity(source, candidate):
    """Rank geometry first, then phase and material difference."""
    return (
        int(source["geometry"] == candidate["geometry"]),
        int(source["phase"] == candidate["phase"]),
        -sum(abs(a - b) for a, b in zip(source["material"], candidate["material"], strict=True)),
    )


def prompt_key(fen):
    return " ".join(chess.Board(fen).fen().split()[:4])
