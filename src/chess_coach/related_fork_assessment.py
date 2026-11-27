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


def certificate(db, version, key, *, check=None):
    board, moves, fingerprint = setup(db, version, key)
    return certify(board, moves, fingerprint, check=check)


def certify(board, moves, fingerprint, *, check=None):
    move = board.parse_uci(moves[1])
    started = time.monotonic() if check is None else None
    proof = fork_proof(board, move) if check is None else fork_proof(board, move, check=check)
    if check is not None:
        check()
    if proof is None or (started is not None and time.monotonic() - started > SECONDS):
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
