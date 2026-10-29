"""Dispatch a reconstructed answer to its objective-specific verifier."""

import json

from .objective_capture_contract import GAIN_OBJECTIVE, TARGET_OBJECTIVE
from .objective_capture_judge import verify as verify_capture
from .objective_defense_judge import verify as verify_defense
from .objective_defense_source import OBJECTIVE as DEFENSE_OBJECTIVE
from .objective_judge import judge
from .objective_short_horizon import verify as verify_short
from .objective_short_source import OBJECTIVE as SHORT_OBJECTIVE


def verify(board, move, request, events, clock, start, seconds, base, session):
    if request["objective_version"] in {TARGET_OBJECTIVE, GAIN_OBJECTIVE}:
        return verify_capture(
            board,
            move,
            request,
            events,
            clock,
            start,
            seconds,
            base,
            json.loads(session["provenance_json"]),
        )
    if request["objective_version"] == DEFENSE_OBJECTIVE:
        return verify_defense(board, move, request, events, clock, start, seconds, base)
    if request["objective_version"] == SHORT_OBJECTIVE:
        return verify_short(board, move, request, events, clock, start, seconds, base)
    return judge(board, move, request, events, clock, start, seconds, base)
