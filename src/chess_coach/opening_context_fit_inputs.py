"""Identify eligible unfamiliar choices and applicable first turns."""


def first_turn(color, path, items):
    ply = 1 if color == "white" else 2
    if len(path) != ply - 1:
        return False
    return all(item["source"]["source_history"]["ply"] == ply for item in items)


def reasons(items, history_ready):
    result = {}
    for item in items:
        reason = item["comparison"]["status"]
        if item["history"] == "seen_in_checked_sample":
            reason = "seen_in_checked_sample"
        elif not history_ready:
            reason = "history_unavailable"
        result[item["uci"]] = reason
    return result


def attach(assess, group, db, root, subject, color, path, items, budget, history_ready, annotation):
    if annotation is None:
        group["fit"] = assess(db, root, subject, color, path, items, budget, history_ready)
        group["items"].sort(key=lambda item: item["uci"] != group["fit"].get("winner"))
    return group
