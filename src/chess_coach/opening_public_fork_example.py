"""Bind one fork witness to its original source position."""

import chess

from .fact_fingerprint import canonical, digest


def example(board, move, recorded, rows, ply, proof, kind):
    target_names = proof["targets"]
    kings = [
        name
        for name in target_names
        if board.piece_at(chess.parse_square(name)).piece_type == chess.KING
    ]
    return {
        "kind": kind,
        "ply": ply,
        "fen": board.fen(),
        "recorded_uci": recorded.uci(),
        "recorded_san": board.san(recorded),
        "candidate_uci": move.uci(),
        "candidate_san": board.san(move),
        "recorded": move == recorded,
        "attacker": chess.square_name(move.from_square),
        "anchor": kings[0] if kings else target_names[0],
        "history_sha256": digest(canonical(rows[: ply - 1])),
        "proof": proof,
    }
