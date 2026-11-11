"""Summarize verified and unresolved fork comparisons."""

from typing import Any


def _opportunity(sample, position, row):
    status = row[2] if row else "pending"
    if status == "retry":
        status = "pending"
    sample[status] += 1
    if row and row[3]:
        sample["configs"].add(row[3])
    if status == "miss" and len(sample["examples"]) < 20:
        sample["examples"].append(position)


def _turn(sample, turn, rows):
    position, outcome, reason = turn
    sample["timeouts"] += reason == "turn_deadline"
    sample["unknown"] += outcome in {"unknown", "unresolved"}
    sample["uncertain"] += outcome == "unresolved"
    if outcome not in {"played", "awaiting"}:
        return False
    sample["opportunities"] += 1
    _opportunity(sample, position, rows.get(str(position)))
    return True


def _sample(games, rows):
    sample: dict[str, Any] = {
        "played": 0,
        "miss": 0,
        "unresolved": 0,
        "pending": 0,
        "opportunities": 0,
        "opportunity_games": 0,
        "configs": set(),
        "eligible": 0,
        "unknown": 0,
        "uncertain": 0,
        "timeouts": 0,
        "scanned": 0,
        "examples": [],
    }
    # Every opportunity remains in the denominator until its comparison resolves.
    for game in games:
        sample["eligible"] += game["eligible"]
        sample["scanned"] += len(game["results"])
        found = [_turn(sample, turn, rows) for turn in game["results"]]
        sample["opportunity_games"] += any(found)
    sample["games"] = len(games)
    return sample
