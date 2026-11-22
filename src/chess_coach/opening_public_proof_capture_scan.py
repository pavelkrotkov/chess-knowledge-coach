"""Collect supported capture examples from shared replayed positions."""

from .fact_fingerprint import canonical, digest


def scan(candidates, rows, start, deadline, capture):
    example, reasons = None, set()
    for ply, board, move in candidates:
        if not board.is_capture(move):
            continue
        proof, missing = capture(board, move, start, deadline)
        if missing:
            reasons.add(missing)
        if proof is not None and example is None:
            example = {"proof": proof, "ply": ply, "history_sha256": digest(canonical(rows[:ply]))}
    return example, reasons
