"""Bind and reserve bounded root-refresh progress."""

from .capture_game_root_budget import fit, fits
from .fact_fingerprint import canonical, digest

VERSION = "capture-root-refresh-v1"


def marker(item, index):
    return {
        "version": VERSION,
        "identity": item["identity"],
        "signature": item["signature"],
        "next": index,
        "prefix": digest(canonical(item["results"][:index])),
    }


def cursor(item):
    saved = item.get("root_refresh")
    if not isinstance(saved, dict):
        return 0
    index = saved.get("next")
    if type(index) is not int or not 0 <= index <= len(item["results"]):
        return 0
    return index if saved == marker(item, index) else 0


def remember(state, item, first):
    offset = cursor(item)
    if offset == first and (first == 0 or "root_refresh" in item):
        previous = item.get("root_refresh")
        item["root_refresh"] = marker(item, len(item["results"]))
        fit(state)
        if not fits(state):
            if previous is None:
                item.pop("root_refresh", None)
            else:
                item["root_refresh"] = previous


def admit(state, item, cursor):
    old = item.get("root_refresh")
    # Reserve the largest index before proving, while retaining the real cursor.
    item["root_refresh"] = marker(item, len(item["results"]))
    fit(state)
    if not fits(state):
        if old is None:
            item.pop("root_refresh", None)
        else:
            item["root_refresh"] = old
        return False
    item["root_refresh"] = marker(item, cursor)
    return True
