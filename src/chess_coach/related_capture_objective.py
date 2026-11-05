"""Bind and reconstruct certified corpus captures for the objective worker."""

import json

from .objective_answer import answer
from .objective_capture_contract import TARGET_OBJECTIVE
from .objective_events import response
from .objective_history_replay import replay
from .related_capture_assessment import HISTORY, PROOF_VERSION, VERSION, setup


def is_source(row):
    if row["source_type"] != "corpus" or row["objective"] != "capture_named_target":
        return False
    return bool(json.loads(row["provenance_json"]).get("related_capture", {}).get("assessment"))


def apply(snapshot, assessment):
    snapshot["objective"] = "capture_named_target"
    snapshot["provenance"].update(
        objective_version=TARGET_OBJECTIVE,
        history_mode=HISTORY,
        source_fingerprint=assessment["source_fingerprint"],
        objective_target=assessment["target"],
        gain_threshold=assessment["gain_threshold"],
        capture_objective="capture_named_target",
    )


# Currentness checks replay only the reset setup; the immutable certificate
# records the proved root and is bound into the session snapshot.
def current(db, row, binding, snapshot_hash):
    from .unified_sources import resolve_source

    board, moves, fingerprint = setup(db, row["source_version"], row["source_key"])
    assessment = binding["assessment"]
    target = board.parse_uci(moves[1]).to_square
    import chess

    if (
        assessment["version"],
        assessment["proof_version"],
        assessment["history_mode"],
        assessment["source_fingerprint"],
        assessment["target"],
        assessment["gain_threshold"],
    ) != (VERSION, PROOF_VERSION, HISTORY, fingerprint, chess.square_name(target), 3):
        raise ValueError("capture assessment source changed")
    if assessment["proof"]["status"] != "correct":
        raise ValueError("capture assessment proof changed")
    candidate = resolve_source(db, "corpus", row["source_version"], row["source_key"])
    apply(candidate, assessment)
    candidate["provenance"]["related_capture"] = binding
    if snapshot_hash(candidate) != row["snapshot_hash"] or board.fen() != row["prompt_fen"]:
        raise ValueError("capture assessment changed")


def before_answer(db, session, events):
    board, _, _ = setup(db, session["source_version"], session["source_key"])
    if board.fen() != session["prompt_fen"]:
        raise ValueError("capture assessment history changed")
    # Only hints and illegal inputs can precede the first legal answer.
    for event in events[:-1]:
        if event["kind"] == "move" and response(event).get("feedback") != "illegal":
            raise ValueError("capture assessment first move changed")
        replay(board, event)
    return board, answer(board, session, events[-1])


def matches(session, data, request):
    if not is_source(session) or session["status"] != "needs_verification":
        return False
    return (
        session["snapshot_hash"] == request["snapshot_hash"]
        and session["learner_color"] == request["learner_color"]
        and data.get("objective_version") == request["objective_version"] == TARGET_OBJECTIVE
        and data.get("history_mode") == request["history_mode"] == HISTORY
        and data.get("source_fingerprint") == request["source_hash"]
    )
