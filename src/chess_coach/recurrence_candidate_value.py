"""Assemble a checked recurrence candidate for reporting."""

from .recurrence_review import review


def value(row, fact, game, decision, state):
    return {
        **{key: row[key] for key in ("id", "position_id", "game_id", "ply", "skill", "operation")},
        "game_key": game["key"],
        "family": row["mapping_producer"],
        "version": fact["detector_version"],
        "outcome": row["outcome"],
        "review": review(row),
        "currentness": state,
        "decision": decision,
    }
