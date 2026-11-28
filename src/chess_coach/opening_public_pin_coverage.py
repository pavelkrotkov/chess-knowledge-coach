"""Account for pin observations and bind their public examples."""

import chess

from .fact_fingerprint import canonical, digest
from .opening_public_fork_windows import bounds
from .opening_public_proof_replay import _attribution


def empty(context, selected, more, binding):
    first, _ = bounds(binding["ply"], 0, binding["policy"]["pin"]["window"])
    return {
        "status": "prepared",
        "eligible": context["matched_candidates"],
        "selected": len(selected),
        "excluded_context": context["excluded_context"],
        "unknown_context": context["unknown_context"],
        "more_eligible": more,
        "analyzed": 0,
        "unsupported": 0,
        "censored": sum(
            row[1] > bounds(binding["ply"], row[1], binding["policy"]["pin"]["window"])[1]
            for row in selected
        ),
        "short_records": sum(
            row[1] < first + binding["policy"]["pin"]["positions"] - 1 for row in selected
        ),
        "ended_before_window": sum(row[1] < first for row in selected),
        "preparation_incomplete": 0,
        "positions_available": 0,
        "positions_inspected": 0,
        "roots": 0,
        "unsupported_proofs": 0,
        "supported": 0,
        "example": None,
        "interrupted": False,
    }


def record(result, item, censored):
    for field in ("positions_available", "positions_inspected", "roots", "unsupported_proofs"):
        result[field] += item[field]
    result["unsupported"] += int(
        bool(item.get("unsupported_history") or item["unsupported_proofs"])
    )
    result["supported"] += int(item["example"] is not None)
    result["analyzed"] += int(item["roots"] > 0)
    result["preparation_incomplete"] += int(bool(item.get("incomplete")))
    if result["example"] is None:
        result["example"] = item["example"]


def example(db, row, binding, source, moves, ply, board, recorded, move, proof):
    first, last = bounds(binding["ply"], row[1], binding["policy"]["pin"]["window"])
    value = {
        "ply": ply,
        "fen": board.fen(en_passant="fen", promoted=True),
        "side_to_move": "white" if board.turn else "black",
        "pinner_piece": chess.piece_name(board.piece_type_at(move.from_square)),
        "pinned_piece": chess.piece_name(board.piece_type_at(chess.parse_square(proof["pinned"]))),
        "rear_piece": chess.piece_name(board.piece_type_at(chess.parse_square(proof["rear"]))),
        "window_start": first,
        "window_end": last,
        "recorded_uci": recorded.uci(),
        "recorded_san": board.san(recorded),
        "candidate_uci": move.uci(),
        "candidate_san": board.san(move),
        "recorded": move == recorded,
        "source_identity": source,
        "history_sha256": digest(canonical(moves[: ply - 1])),
        "full_history_sha256": digest(canonical(moves)),
        "proof": proof,
    }
    _attribution(db, row[0], row[2], binding, value)
    return value
