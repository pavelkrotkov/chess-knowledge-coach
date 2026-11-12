"""Certify one exclusive immediate-mate or bounded-capture prompt."""

from .mate_proof import VERSION as MATE_VERSION
from .mate_proof import immediate_mates
from .objective_capture_judge import VERSION as CAPTURE_VERSION
from .recognition_capture_exclusion import no_capture
from .related_capture_assessment import certificate

VERSION = "recognition-exclusive-v1"
MAX_ROOTS = 64


def prove(db, version, key, kind, prepared):
    board, moves, fingerprint = prepared
    if board.legal_moves.count() > MAX_ROOTS or board.is_game_over(claim_draw=True):
        return None
    mates = immediate_mates(board)
    supplied = board.parse_uci(moves[1])
    if kind == "capture":
        return _capture(db, version, key, fingerprint, mates)
    return _mate(board, kind, supplied, mates, fingerprint)


def _capture(db, version, key, fingerprint, mates):
    if mates:
        return None
    proof = certificate(db, version, key)
    return {
        "version": VERSION,
        "kind": "capture",
        "source_fingerprint": fingerprint,
        "proof": proof,
    }


def _mate(board, kind, supplied, mates, fingerprint):
    if kind != "mate" or len(mates) != 1 or mates[0]["uci"] != supplied.uci():
        return None
    if not no_capture(board):
        return None
    return {
        "version": VERSION,
        "kind": kind,
        "source_fingerprint": fingerprint,
        "capture_verifier": CAPTURE_VERSION,
        "mate_verifier": MATE_VERSION,
        "history_mode": "zeroing_setup",
        "mate": mates[0],
    }
