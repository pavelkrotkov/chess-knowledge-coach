"""Advance a deterministic prefix until the first exposure nominee."""

import json
import time

from .created_exposure_game_profile import features
from .created_exposure_game_proof import classify
from .related_capture_position import _phase
from .short_mate_trend_turns import _reason

TURN_SECONDS = 0.5


# Once a candidate is found, uncertainty ends this game's sampled prefix too.
def finished(item):
    return any(row[1] != "no_nominee" for row in item["results"])


def _result(context, board, blocked, profile, deadline):
    position = context["position_id"]
    if position in blocked:
        return [position, "unknown", "source_unavailable"]
    local = min(time.monotonic() + TURN_SECONDS, deadline)
    outcome, reason = classify(
        board, context["played_move"], features(profile), local, time.monotonic
    )
    reason = _reason(reason, local, deadline)
    if reason == "cycle_deadline":
        return None
    if reason == "no_sampled_nominee":
        return [position, "no_nominee", reason]
    if outcome in {"protected", "missed", "opportunity_unresolved"}:
        reason = json.dumps(
            ["white" if board.turn else "black", _phase(board), reason],
            separators=(",", ":"),
        )
    return [position, outcome, reason]


def advance(item, turns, blocked, profile, deadline, quota):
    used = 0
    while used < quota and len(item["results"]) < len(turns) and not finished(item):
        if time.monotonic() + TURN_SECONDS >= deadline:
            break
        result = _result(*turns[len(item["results"])], blocked, profile, deadline)
        if result is None:
            break
        item["results"].append(result)
        used += 1
    return used
