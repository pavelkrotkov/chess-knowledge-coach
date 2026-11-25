"""Allow previously offered new prompts to return once as due review."""


def eligible_again(candidate, seen, window):
    return bool(
        candidate is not None
        and window is not None
        and candidate["prompt_key"] in seen
        and candidate["prompt_key"] in window["repeat_due"]
    )


def take_again(candidate, seen, window):
    if eligible_again(candidate, seen, window):
        key = candidate["prompt_key"]
        seen.remove(key)
        window["repeat_due"].remove(key)
        window["new_seen"].remove(key)


def page_full(window, selected):
    return window is not None and len(selected) >= window["page_limit"]


def full(state, seen, window, selected):
    return len(seen) >= state["limit"] or page_full(window, selected)


def incomplete(reason, rows, examined, window, selected):
    return reason is not None or len(rows) > examined or page_full(window, selected)


def charge(state, window, previous, selected, reason):
    if window is not None:
        state["limit"] -= sum(item["prompt_key"] in previous for item in selected)
        if reason == "due_scan_incomplete" and len(state["seen"]) >= state["limit"]:
            return None
    return reason
