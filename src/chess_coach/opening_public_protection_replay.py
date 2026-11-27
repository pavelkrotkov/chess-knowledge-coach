"""Qualify recorded public defenses against their own original histories."""

import time

import chess

from .fact_fingerprint import canonical, digest
from .material_threats import check_options
from .objective_protection_before import probe
from .objective_protection_judge import judge
from .opening_public_proof_history import positions
from .opening_public_proof_replay import _attribution


def replay(db, row, binding, branch, start, deadline):
    game_id, total, context = row
    rows, candidates, censored, safe = positions(
        db, game_id, total, binding, branch, deadline, all_moves=True
    )
    if not safe:
        return {
            "unsupported": ["history_or_draw_unsupported"],
            "censored": censored,
            "example": None,
            "fork": None,
        }
    example, reasons = None, set()

    def check():
        if time.monotonic() >= deadline:
            raise TimeoutError("public proof deadline")

    for ply, board, move in candidates:
        check()
        before = probe(board, **check_options(check))
        if before is None:
            reasons.add("threat_or_scope_unavailable")
            continue
        target = next(iter(before["targets"]))
        proof = judge(board, move, target, time.monotonic, start, deadline - start, {}, check=check)
        if proof["status"] != "correct":
            reasons.add("recorded_defense_unavailable")
            continue
        if example is None:
            example = {
                "ply": ply,
                "target": chess.square_name(target),
                "target_piece": chess.piece_name(board.piece_type_at(target)),
                "recorded_uci": move.uci(),
                "recorded_san": board.san(move),
                "history_sha256": digest(canonical(rows[: ply - 1])),
                "proof": proof,
            }
    check()
    if example is not None:
        _attribution(db, game_id, context, binding, example)
    return {"unsupported": sorted(reasons), "censored": censored, "example": example, "fork": None}
