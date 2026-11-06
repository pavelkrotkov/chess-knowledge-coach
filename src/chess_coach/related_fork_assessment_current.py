"""Recheck the immutable fork certificate and zeroing corpus setup."""

import chess

from .fork_contract import VERSION as FORK_VERSION
from .fork_proof import MAX_REPLIES
from .objective_fork_contract import GOAL, OBJECTIVE, VERIFIER
from .objective_fork_snapshot import _anchor
from .related_capture_assessment import HISTORY, setup
from .related_fork_assessment import VERSION


def apply(snapshot, assessment):
    snapshot["objective"] = GOAL
    snapshot["provenance"].update(
        objective_version=OBJECTIVE,
        history_mode=HISTORY,
        source_fingerprint=assessment["source_fingerprint"],
        fork_attacker=assessment["attacker"],
        fork_anchor=assessment["anchor"],
        gain_threshold=assessment["gain_threshold"],
        source_outcome="failure",
    )


def _proof(board, moves, assessment):
    move = board.parse_uci(moves[1])
    proof = assessment["proof"]
    return (
        proof["move"] == move.uci()
        and proof["attacker"] == chess.square_name(move.to_square)
        and proof["minimum_gain"] == 3
        and 0 < proof["legal_replies"] <= MAX_REPLIES
        and assessment["attacker"] == chess.square_name(move.from_square)
        and assessment["anchor"] == _anchor(board, proof["targets"])
    )


def current(db, row, binding, snapshot):
    board, moves, fingerprint = setup(db, row["source_version"], row["source_key"])
    assessment = binding["assessment"]
    if (
        assessment["version"],
        assessment["proof_version"],
        assessment["fork_version"],
        assessment["history_mode"],
        assessment["source_fingerprint"],
        assessment["gain_threshold"],
        assessment["reply_limit"],
    ) != (VERSION, VERIFIER, FORK_VERSION, HISTORY, fingerprint, 3, MAX_REPLIES):
        raise ValueError("fork assessment changed")
    if board.fen() != row["prompt_fen"] or not _proof(board, moves, assessment):
        raise ValueError("fork assessment changed")
    apply(snapshot, assessment)
