"""Classify unlisted legal moves without inventing a verifier."""

import json

from .related_mate import FILTER_VERSION, VERSION
from .unified_public_outcome import direct
from .unified_session_branch import move_state


def short_assessment(row):
    return (
        row["source_type"] == "corpus"
        and row["objective"] == "mate_within_two"
        and bool(json.loads(row["provenance_json"]).get("related_mate", {}).get("assessment"))
    )


def _related_immediate(row, board, index):
    if (
        index != 0
        or row["source_type"] not in {"corpus", "public"}
        or row["objective"] != "checkmate"
    ):
        return False
    binding = json.loads(row["provenance_json"]).get("related_mate")
    return (
        isinstance(binding, dict)
        and (
            binding.get("rank_version"),
            binding.get("line_filter_version"),
            binding.get("motif"),
            binding.get("operation"),
            binding.get("mate_timing"),
        )
        == (VERSION, FILTER_VERSION, "mate", "execute", "mate_in_one")
        and board.is_checkmate()
    )


def unmatched(row, board, index, candidates):
    if _related_immediate(row, board, index):
        return move_state(board, "objective_verified", "objective_verified", 1, candidates)
    if row["source_type"] == "public":
        if direct(row) and row["objective"] == "checkmate" and board.is_checkmate():
            return move_state(
                board, "objective_verified", "objective_verified", index + 1, candidates
            )
        return move_state(board, "ungraded", "needs_verification", index, candidates)
    feedback = "ungraded" if short_assessment(row) else "needs_verification"
    return move_state(board, feedback, "needs_verification", index, candidates)
