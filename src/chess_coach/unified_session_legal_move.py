"""Route a legal practice move through a certified or supplied branch."""

import json

from .objective_promotion_routing import needs_verification
from .unified_session_branch import advance, move_state


def apply(row, board, lines, candidates, move):
    board.push(move)
    index = row["next_index"]
    final = _short_final(row, board, index, candidates)
    if final is not None:
        return final
    if needs_verification(row):
        return move_state(board, "needs_verification", "needs_verification", index, candidates)
    matched = _matches(lines, candidates, index, move)
    if not matched:
        return _unmatched(row, board, index, candidates)
    return advance(board, row["objective"], lines, matched, index)


def _short_assessment(row):
    return (
        row["source_type"] == "corpus"
        and row["objective"] == "mate_within_two"
        and bool(json.loads(row["provenance_json"]).get("related_mate", {}).get("assessment"))
    )


def _unmatched(row, board, index, candidates):
    feedback = "ungraded" if _short_assessment(row) else "needs_verification"
    return move_state(board, feedback, "needs_verification", index, candidates)


def _short_final(row, board, index, candidates):
    if index != 2 or not _short_assessment(row):
        return None
    if board.is_checkmate():
        return move_state(board, "objective_verified", "objective_verified", index + 1, candidates)
    return move_state(board, "incorrect", "line_completed", index + 1, candidates)


def _matches(lines, candidates, index, move):
    return [i for i in candidates if index < len(lines[i]) and lines[i][index] == move.uci()]
