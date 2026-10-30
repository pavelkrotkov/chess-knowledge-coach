"""Apply existing bounded protection proof to the exact compared roots."""

import time

import chess

from .objective_protection_before import probe
from .objective_protection_judge import judge
from .style_protection_budget import take

PROOF_SECONDS = 1.0


def original(board, target, budget):
    if not take(budget, "probes"):
        return None
    before = probe(board)
    if before is None or set(before["targets"]) != {target}:
        return None
    return before


def proof(board, text, target, before, evidence, budget):
    if not take(budget, "proofs"):
        return {"status": "unknown", "reason": "report_budget_exhausted"}
    move = chess.Move.from_uci(text)
    start = time.monotonic()
    result = judge(board, move, target, time.monotonic, start, PROOF_SECONDS, {})
    if result["status"] != "correct":
        return {"status": "unknown", "reason": result["reason"]}
    attackers = {chess.Move.from_uci(uci).from_square for uci in before["targets"][target]}
    captured = board.is_capture(move) and move.to_square in attackers
    return {
        "status": "supported",
        "evidence_id": evidence,
        "target": chess.square_name(target),
        "target_piece": chess.piece_name(board.piece_type_at(target)),
        "moved_target": move.from_square == target,
        "captured_attacker": captured,
        "captured_piece": chess.piece_name(board.piece_type_at(move.to_square))
        if captured
        else None,
        "captured_square": chess.square_name(move.to_square) if captured else None,
        "guard": "unknown",
        "boundary": "no supported profitable immediate capture of the named piece",
    }
