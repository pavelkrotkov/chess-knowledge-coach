"""Describe one source-linked position with its original replay history."""

from .fact_fingerprint import canonical, digest


def example(board, moves, ply, move, first, last):
    return {
        "ply": ply,
        "window_start": first,
        "window_end": last,
        "fen": board.fen(),
        "recorded_uci": move.uci(),
        "recorded_san": board.san(move),
        "history_sha256": digest(canonical(moves[: ply - 1])),
        "repetition_observed": board.is_repetition(2),
        "draw_claim_available": board.can_claim_draw(),
        "piece_count": len(board.piece_map()),
    }
