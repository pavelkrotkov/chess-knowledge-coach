"""Bind selected plan offers and expose the signed continuation."""

from .curriculum_window_cursor import encode
from .curriculum_window_display import annotate, status
from .curriculum_window_offer import issue
from .curriculum_window_scope import expired


def offers(db, value, page):
    if expired(value):
        return
    for item in page["items"]:
        if item["kind"] == "new":
            from .curriculum_capture_offer_page import offer

            item["window_offer"] = offer(db, value, item) or issue(db, value, item)


def _continuation(page, expired_now, plan_state, cursor):
    due_pending = page["scan"]["due_incomplete"] and len(plan_state["seen"]) < plan_state["limit"]
    if page["next_cursor"] is not None or (expired_now and due_pending):
        page["next_cursor"] = cursor


def finish(db, value, plan_state, page, expired_now, selection_cursor):
    for item in page["items"]:
        if item["kind"] == "new" and item["prompt_key"] not in value["new_seen"]:
            value["new_seen"].append(item["prompt_key"])
    cursor = encode(db, value)
    _continuation(page, expired_now, plan_state, cursor)
    page["window_cursor"] = cursor
    page["window_selection_cursor"] = selection_cursor
    annotate(page, value["goal"])
    page["window"] = {
        "goal": value["goal"],
        "goal_status": status(page, value["goal"]),
        "minutes": value["minutes"],
        "issued_at": value["issued_at"],
        "expires_at": value["expires_at"],
        "expired": expired_now,
        "source_refreshed": value["source_refreshed"],
    }
    return page
