"""Validate and describe the actual verified pawn-result answer."""

import json

from . import pawn_proof, pawn_tables
from .objective_pawn_bounds import verdict
from .objective_pawn_contract import VERIFIER
from .objective_pawn_history import before_answer
from .objective_pawn_interval_binding import result_interval
from .objective_pawn_prior import bound_events
from .objective_short_history import history_hash


def checked_from_current_session(db, session, request, result):
    # The display caller has already rechecked this source and guards its generation.
    events = bound_events(db, session, request)
    board, move = before_answer(db, session, events)
    data = json.loads(session["provenance_json"])
    _binding(request, result, board, move, data, session["objective"])
    return (
        board,
        move,
        {
            "move": board.san(move),
            "goal": result["goal"],
            "lower": result["lower"],
            "upper": result["upper"],
        },
    )


def _binding(request, result, board, move, data, objective):
    fields = (
        "objective_version",
        "history_mode",
        "snapshot_hash",
        "event_prefix_hash",
        "source_hash",
    )
    if any(result.get(field) != request[field] for field in fields):
        raise ValueError("pawn result binding changed")
    goal, low, high = result_interval(result, data, objective)
    matches = (
        result.get("verifier") == VERIFIER,
        result.get("proof_version") == pawn_proof.VERSION,
        result.get("proof_manifest_sha256") == pawn_tables.MANIFEST_SHA256,
        result.get("history_hash") == history_hash(board),
        result.get("move") == move.uci(),
        result.get("san") == board.san(move),
        (result.get("status"), result.get("reason")) == verdict(low, high, goal),
    )
    if not all(matches):
        raise ValueError("pawn result proof changed")
