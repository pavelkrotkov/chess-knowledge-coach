"""Certify a zeroing corpus setup and both sides of a named-piece contrast."""

import time

import chess

from .fact_fingerprint import canonical, digest
from .objective_created_contract import ASSESSMENT, OBJECTIVE, VERIFIER
from .objective_created_judge import judge
from .objective_protection_refute import witness as capture_witness
from .objective_short_history import history_hash
from .related_capture_assessment import HISTORY, setup
from .related_protection_assessment_lines import selected

SECONDS = 5.0


def certificate(db, version, key, lines, contrast, *, start=None, seconds=SECONDS):
    board, _, fingerprint = setup(db, version, key)
    line, good = selected(board, lines)
    bad = board.parse_uci(contrast["bad"])
    target = bad.from_square
    # Both candidate roots share the caller's bounded proof deadline.
    start = time.monotonic() if start is None else start
    good_proof = judge(board, good, target, time.monotonic, start, seconds, {})
    bad_proof = judge(board, bad, target, time.monotonic, start, seconds, {})
    after = board.copy(stack=True)
    after.push(bad)
    if (
        good_proof["status"] != "correct"
        or bad_proof["status"] != "incorrect"
        or capture_witness(after, [contrast["capture"]]) is None
        or time.monotonic() - start > seconds
    ):
        raise ValueError("created exposure assessment unavailable")
    return {
        "version": ASSESSMENT,
        "objective_version": OBJECTIVE,
        "proof_version": VERIFIER,
        "history_mode": HISTORY,
        "source_fingerprint": fingerprint,
        "target": chess.square_name(target),
        "selected_line_hash": digest(canonical(line)),
        "good": good_proof,
        "bad": bad_proof,
    }


def valid(board, fingerprint, assessment, lines, contrast):
    line, good = selected(board, lines)
    bad = board.parse_uci(contrast["bad"])
    fields = (
        assessment["version"],
        assessment["objective_version"],
        assessment["proof_version"],
        assessment["history_mode"],
        assessment["source_fingerprint"],
        assessment["target"],
        assessment["selected_line_hash"],
    )
    expected = (
        ASSESSMENT,
        OBJECTIVE,
        VERIFIER,
        HISTORY,
        fingerprint,
        chess.square_name(bad.from_square),
        digest(canonical(line)),
    )
    return fields == expected and _proofs(board, good, bad, assessment)


def _proofs(board, good, bad, assessment):
    history = history_hash(board)
    return all(
        (
            assessment["good"]["status"] == "correct",
            assessment["bad"]["status"] == "incorrect",
            assessment["good"]["move"] == good.uci(),
            assessment["bad"]["move"] == bad.uci(),
            assessment["good"]["history_hash"] == history,
            assessment["bad"]["history_hash"] == history,
        )
    )
