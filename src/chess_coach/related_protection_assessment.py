"""Certify a current unfamiliar protection exemplar on its reset history."""

import time

import chess

from .fact_fingerprint import canonical, digest
from .objective_protection_before import probe
from .objective_protection_contract import OBJECTIVE
from .objective_protection_judge import VERSION as VERIFIER
from .objective_protection_judge import judge
from .objective_short_history import history_hash
from .related_capture_assessment import HISTORY, setup
from .related_protection_assessment_lines import selected

VERSION = "related-protection-assessment-v1"
SECONDS = 5.0


def certificate(db, version, key, target, selected_lines):
    board, _, fingerprint = setup(db, version, key)
    line, move = selected(board, selected_lines)
    threat = probe(board)
    square = chess.parse_square(target)
    if threat is None or set(threat["targets"]) != {square}:
        raise ValueError("protection assessment target unavailable")
    started = time.monotonic()
    result = judge(board, move, square, time.monotonic, started, SECONDS, {})
    if result["status"] != "correct":
        raise ValueError("protection assessment proof unavailable")
    return {
        "version": VERSION,
        "objective_version": OBJECTIVE,
        "proof_version": VERIFIER,
        "history_mode": HISTORY,
        "source_fingerprint": fingerprint,
        "selected_line_hash": digest(canonical(line)),
        "target": target,
        "gain_threshold": 3,
        "proof": result,
    }


def valid(board, fingerprint, assessment, target, selected_lines):
    line, move = selected(board, selected_lines)
    proof = assessment["proof"]
    return (
        (
            assessment["version"],
            assessment["objective_version"],
            assessment["proof_version"],
            assessment["history_mode"],
            assessment["source_fingerprint"],
            assessment["target"],
            assessment["gain_threshold"],
        )
        == (VERSION, OBJECTIVE, VERIFIER, HISTORY, fingerprint, target, 3)
        and proof["verifier"] == VERIFIER
        and proof["status"] == "correct"
        and proof["reason"] == "no_profitable_immediate_capture"
        and assessment["selected_line_hash"] == digest(canonical(line))
        and proof["move"] == move.uci()
        and proof["history_hash"] == history_hash(board)
    )
