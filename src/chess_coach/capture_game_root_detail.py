"""Retain bounded exact-root detail from the existing capture scan."""

from .capture_game_proof import VERSION as PROOF_VERSION
from .capture_game_root_budget import room
from .short_mate_trend_turns import inspect as inspect_turns

VERSION = "capture-game-roots-v1"


def _record(state, item, row, detail):
    section = item.get("root_details") or {"version": VERSION, "proof": PROOF_VERSION, "turns": []}
    if (section.get("version"), section.get("proof")) != (VERSION, PROOF_VERSION):
        return
    value = {**detail, "position_id": row[0], "outcome": row[1]}
    if value.get("reason") == "deadline":
        value["reason"] = row[2]
    section = {**section, "turns": [*section["turns"], value]}
    if room(state, item, section):
        item["root_details"] = section


def inspect(db, learner, item, deadline, quota, *, state, classifier, seconds):
    collected = []

    def classify(board, played, until, clock):
        detail = {}
        result = classifier(board, played, until, clock, details=detail)
        collected.append(detail)
        return result

    first = len(item["results"])
    used = inspect_turns(db, learner, item, deadline, quota, classifier=classify, seconds=seconds)
    for row, detail in zip(item["results"][first:], collected, strict=False):
        if detail:
            _record(state, item, row, detail)
    return used
