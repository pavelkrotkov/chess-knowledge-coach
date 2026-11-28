"""Bind every legal immediate mate at one verified public source position."""

import time

from .fact_fingerprint import canonical, digest
from .objective_judge import judge
from .opening_public_mate_policy import check
from .opening_public_proof_replay import _attribution


def example(db, row, binding, source, moves, rows, ply, board, recorded, mates, start, deadline):
    proofs = []
    for mate in mates:
        check(deadline)
        proof = judge(
            board.copy(stack=True),
            board.parse_uci(mate["uci"]),
            {"learner_color": binding["color"]},
            [],
            time.monotonic,
            start,
            deadline - start,
            {},
        )
        if proof["status"] != "correct":
            raise ValueError("mate proof unavailable")
        proofs.append(proof)
    value = {
        "ply": ply,
        "fen": board.fen(),
        "recorded_uci": recorded.uci(),
        "recorded_san": board.san(recorded),
        "recorded_mate": any(mate["uci"] == recorded.uci() for mate in mates),
        "alternatives": proofs,
        "source_identity": source,
        "history_sha256": digest(canonical(rows[: ply - 1])),
        "full_history_sha256": digest(canonical(moves)),
    }
    _attribution(db, row[0], row[2], binding, value)
    return value
