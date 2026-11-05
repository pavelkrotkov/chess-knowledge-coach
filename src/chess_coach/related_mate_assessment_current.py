"""Recheck an admitted assessment against its immutable corpus source."""

from .mate_proof import MAX_NODES
from .mate_proof import VERSION as PROOF_VERSION
from .related_mate_assessment import VERSION, setup


def validate(db, row, binding, candidate):
    if row["source_type"] != "corpus" or binding["mate_timing"] != "mate_within_two":
        raise ValueError("assessment scope changed")
    board, _, fingerprint = setup(db, row["source_version"], row["source_key"])
    assessment = binding["assessment"]
    expected = (VERSION, PROOF_VERSION, MAX_NODES, "zeroing_setup", fingerprint, board.fen())
    actual = (
        assessment["version"],
        assessment["proof_version"],
        assessment["node_limit"],
        assessment["history_mode"],
        assessment["source_fingerprint"],
        candidate["prompt_fen"],
    )
    if actual != expected:
        raise ValueError("assessment source changed")
