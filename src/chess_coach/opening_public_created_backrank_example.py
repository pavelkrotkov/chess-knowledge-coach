"""Judge recorded and alternative responses on the original public history."""

import time

from .fact_fingerprint import canonical, digest
from .objective_defense_judge import judge
from .objective_short_history import history_hash
from .opening_public_mate_policy import check
from .opening_public_proof_replay import _attribution


def _eligible(item, recorded):
    return (
        item["move"]["uci"] != recorded.uci()
        and item["status"] == "complete"
        and not item["back_rank"]
        and not item["other_mates"]
    )


def _judge(board, move, start, deadline):
    check(deadline)
    result = judge(board.copy(stack=True), move, time.monotonic, start, deadline - start, {})
    check(deadline)
    return result


def example(db, row, binding, source, moves, rows, ply, board, recorded, observed, start, deadline):
    recorded_verdict = _judge(board, recorded, start, deadline)
    if recorded_verdict.get("reason") != "opponent_immediate_checkmate":
        raise ValueError("recorded mate verification unavailable")
    value = {
        "ply": ply,
        "fen": board.fen(en_passant="fen", promoted=True),
        "side_to_move": "white" if board.turn else "black",
        "recorded_uci": recorded.uci(),
        "recorded_san": board.san(recorded),
        "observer": observed,
        "recorded_verdict": recorded_verdict,
        "alternatives": [],
        "source_identity": source,
        "history_hash": history_hash(board),
        "history_sha256": digest(canonical(rows[: ply - 1])),
        "full_history_sha256": digest(canonical(moves)),
    }
    _attribution(db, row[0], row[2], binding, value)
    for item in observed["alternatives"]:
        if not _eligible(item, recorded):
            continue
        try:
            verdict = _judge(board, board.parse_uci(item["move"]["uci"]), start, deadline)
        except TimeoutError:
            return value, True
        value["alternatives"].append(verdict)
    return value, False
