"""Certify a reset-history corpus fork using the existing bounded proof."""

import time

import chess

from .fork_contract import VERSION as FORK_VERSION
from .fork_proof import MAX_REPLIES, fork_proof
from .objective_fork_contract import VERIFIER
from .objective_fork_snapshot import _anchor
from .related_capture_assessment import HISTORY, setup

VERSION = "related-fork-assessment-v1"
SECONDS = 5.0


def certificate(db, version, key):
    board, moves, fingerprint = setup(db, version, key)
    return certify(board, moves, fingerprint)


def certify(board, moves, fingerprint):
    move = board.parse_uci(moves[1])
    started = time.monotonic()
    proof = fork_proof(board, move)
    if time.monotonic() - started > SECONDS or proof is None:
        raise ValueError("fork assessment proof unavailable")
    return {
        "version": VERSION,
        "proof_version": VERIFIER,
        "fork_version": FORK_VERSION,
        "history_mode": HISTORY,
        "source_fingerprint": fingerprint,
        "attacker": chess.square_name(move.from_square),
        "anchor": _anchor(board, proof["targets"]),
        "gain_threshold": 3,
        "reply_limit": MAX_REPLIES,
        "proof": proof,
    }
