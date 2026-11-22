"""Replay bounded public history and prove only supported observed captures."""

import time

import chess

from .fact_fingerprint import canonical, digest
from .material_exchange_rules import ordinary_capture
from .objective_capture_judge import judge
from .opening_public_proof_history import positions
from .opening_reference_url import site as valid_site


def _capture(board, move, start, deadline):
    target = board.piece_at(move.to_square)
    if target is None or target.piece_type == chess.PAWN:
        return None, "target_outside_scope"
    if not ordinary_capture(board, move):
        return None, "checking_or_special_move"

    def check():
        if time.monotonic() >= deadline:
            raise TimeoutError("public proof deadline")

    proof = judge(
        board,
        move,
        "capture_named_target",
        move.to_square,
        3,
        time.monotonic,
        start,
        deadline - start,
        {},
        check=check,
    )
    if proof["status"] != "correct":
        return None, proof["reason"]
    return proof, None


def _attribution(db, game_id, context, binding, example):
    site = db.execute("SELECT site FROM games WHERE id=?", (game_id,)).fetchone()
    if site is None:
        raise ValueError("public game unavailable")
    example["source"] = valid_site(site[0]) or binding["reference"]["source_archive"]
    example["record"] = game_id
    example["record_hash"] = digest(canonical([binding["index_sha256"], game_id, context]))


# Recorded public captures are examples, never evidence of a learner mistake.
def replay(db, row, binding, branch, start, deadline):
    game_id, total, context = row
    rows, candidates, censored, safe = positions(db, game_id, total, binding, branch, deadline)
    example, reasons = None, set()
    for ply, board, move in candidates:
        proof, missing = _capture(board, move, start, deadline)
        if missing:
            reasons.add(missing)
        if proof is not None and example is None:
            example = {"proof": proof, "ply": ply, "history_sha256": digest(canonical(rows[:ply]))}
    if not safe:
        reasons.add("history_or_draw_unsupported")
    if example:
        _attribution(db, game_id, context, binding, example)
    if time.monotonic() >= deadline:
        raise TimeoutError("public proof deadline")
    return {"unsupported": sorted(reasons), "censored": censored, "example": example}
