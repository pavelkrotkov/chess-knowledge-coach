"""Present due work when a practice window has expired."""


def due_only(state, summary, status, items, scan, reason):
    return {
        "as_of": state["as_of"],
        "evidence": summary,
        "corpus_status": status,
        "scan": scan,
        "items": items,
        "next_cursor": None,
        "continuation_reason": reason or "window_expired",
        "diagnostic": None,
        "limit_reached": len(state["seen"]) >= state["limit"],
    }
