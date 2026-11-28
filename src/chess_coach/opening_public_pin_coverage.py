"""Account for pin observations and bind their public examples."""

from .fact_fingerprint import canonical, digest
from .opening_public_fork_windows import bounds
from .opening_public_proof_replay import _attribution


def empty(context, selected, more):
    return {
        "status": "prepared",
        "eligible": context["matched_candidates"],
        "selected": selected,
        "excluded_context": context["excluded_context"],
        "unknown_context": context["unknown_context"],
        "more_eligible": more,
        "analyzed": 0,
        "unsupported": 0,
        "censored": 0,
        "short_records": 0,
        "ended_before_window": 0,
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
    result["censored"] += int(censored)
    result["short_records"] += int(item["short_record"])
    result["ended_before_window"] += int(not item["positions_available"])
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
        "fen": board.fen(),
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
