"""Resolve the exact current purpose attempt inside the report snapshot."""

from .purpose_view import show
from .style_purpose_validate import slot_matches_request
from .style_purpose_view_state import unavailable, view_state


def current_view(db, learner, slot, snapshot, views):
    if not slot_matches_request(db, learner, slot):
        return "source_unknown", None
    request_id = slot["request_id"]
    if snapshot is None:
        views[request_id] = unavailable(slot)
        return "source_unknown", None
    view = views.get(request_id)
    if view is None:
        try:
            view = show(db, request_id, learner, snapshot=snapshot)
        except ValueError:
            return "source_unknown", None
        views[request_id] = view
    if view["game_id"] != slot["game_id"] or view["position_id"] != slot["position_id"]:
        return "source_unknown", None
    return view_state(view), view
