"""Recognize complete unassisted short-mate attempts with worker proofs."""

from .coaching_short_async_final import completed as final_completed
from .coaching_short_async_root import completed as root_completed
from .objective_events import response


def completed(db, row, events):
    actions = _actions(events)
    if not actions or len(actions) > 2 or actions[-1][0] != len(events) - 1:
        return False
    index, event, detail = actions[0]
    if detail.get("feedback") == "needs_verification":
        return root_completed(db, row, events, actions, index, event)
    if len(actions) == 2 and detail.get("feedback") == "line_match":
        return final_completed(db, row, events, actions, event, detail)
    return False


def _actions(events):
    if any(event["kind"] != "move" for event in events):
        return []
    return [
        (index, event, response(event))
        for index, event in enumerate(events)
        if response(event).get("feedback") != "illegal"
    ]
