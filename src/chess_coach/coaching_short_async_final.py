"""Recognize a verified final mate after a prepared short-mate root."""

import json

from .coaching_short_request import verified


def completed(db, row, events, actions, first, detail):
    index, event, final_detail = actions[1]
    if (
        row["status"] != "needs_verification"
        or index != len(events) - 1
        or final_detail.get("feedback") != "needs_verification"
    ):
        return False
    pair = [first["submitted_move"], detail.get("opponent_move")]
    if not any(line[:2] == pair for line in json.loads(row["lines_json"])):
        return False
    result = verified(db, row, event)
    return (
        result is not None
        and result["complete"]
        and final_detail.get("fen") == row["current_fen"] == result["board"].fen()
    )
