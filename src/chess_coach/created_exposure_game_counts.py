"""Count one sampled candidate per independent game, without asserting absence."""

import json
from typing import Any


def sample(games):
    result: dict[str, Any] = {
        "games": len(games),
        "newest": games[0]["date"] if games else None,
        "oldest": games[-1]["date"] if games else None,
        "eligible_turns": 0,
        "scanned_turns": 0,
        "completed_games": 0,
        "withheld_games": 0,
        "no_candidate": 0,
        "unknown": 0,
        "protected": 0,
        "missed": 0,
        "opportunity_unresolved": 0,
        "examples": [],
    }
    for game in games:
        _add(result, game)
    result["pending_games"] = result["games"] - result["completed_games"]
    result["opportunities"] = sum(
        result[key] for key in ("protected", "missed", "opportunity_unresolved")
    )
    return result


def _add(result, game):
    rows = game["results"]
    result["eligible_turns"] += game["eligible"]
    result["scanned_turns"] += len(rows)
    if game.get("source_unavailable"):
        result["withheld_games"] += 1
        return
    selected = next((row for row in rows if row[1] != "no_nominee"), None)
    if selected is None and len(rows) < game["eligible"]:
        return
    result["completed_games"] += 1
    if selected is None:
        result["no_candidate"] += 1
        return
    result[selected[1]] += 1
    side, phase, reason = (None, None, selected[2])
    if selected[1] in {"protected", "missed", "opportunity_unresolved"}:
        side, phase, reason = json.loads(selected[2])
    result["examples"].append(
        {
            "position_id": selected[0],
            "outcome": selected[1],
            "color": side,
            "phase": phase,
            "reason": reason,
        }
    )


# Unsearched games and unresolved choices remain possible misses in the bounds.
# They are not counted as proved opportunities or as verified safe choices.
def bounded(sample):
    return {
        "played": sample["protected"],
        "other": sample["missed"],
        "unknown": sample["unknown"] + sample["no_candidate"],
        "opportunity_unresolved": sample["opportunity_unresolved"],
        "unchecked": sample["pending_games"],
        "resolved_games": sample["protected"] + sample["missed"],
    }
