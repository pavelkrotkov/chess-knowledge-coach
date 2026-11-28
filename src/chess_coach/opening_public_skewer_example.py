"""Bind one existing royal-skewer proof to its original public record."""

from .fact_fingerprint import canonical, digest
from .objective_short_history import history_hash
from .opening_public_proof_replay import _attribution


def example(db, row, binding, source, moves, rows, ply, board, recorded, proof):
    root = board.parse_san(proof["root"])
    value = {
        "ply": ply,
        "fen": board.fen(),
        "side_to_move": "white" if board.turn else "black",
        "recorded_uci": recorded.uci(),
        "recorded_san": board.san(recorded),
        "root_uci": root.uci(),
        "proof": proof,
        "history_hash": history_hash(board),
        "history_sha256": digest(canonical(rows[: ply - 1])),
        "full_history_sha256": digest(canonical(moves)),
        "source_identity": source,
    }
    _attribution(db, row[0], row[2], binding, value)
    return value
