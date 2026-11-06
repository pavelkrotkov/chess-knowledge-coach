"""Resolve current and earlier results for a selected catalog move."""

from .opening_queue_result import result


def state(directory, current, slot, board):
    if slot and slot["id"] == current["id"]:
        return _slot_state(directory, slot, board)
    for attempt in (2, 1, 0):
        item = {**current, "attempt": attempt}
        value = result(directory, item, board)
        if value is not None:
            return {**value, "retry_available": attempt < 2}
    if slot and _same_choice(slot, current):
        return {"status": "stale"}
    return {"status": "none"}


def _slot_state(directory, slot, board):
    value = result(directory, slot, board)
    if value is not None:
        return {**value, "retry_available": slot["attempt"] < 2}
    return {
        "status": "unavailable" if slot["state"] == "unavailable" else "queued",
        "retry_available": slot["attempt"] < 2,
    }


def _same_choice(old, current):
    fields = ("game_id", "position_id", "alternative")
    return all(old["source"].get(key) == current["source"].get(key) for key in fields)
