"""Validate the owner, source and bounded snapshot in a capture offer."""

from .curriculum_cursor import revision
from .curriculum_priority_validate import _capture_input
from .curriculum_window_scope import GOALS
from .fact_fingerprint import digest


def scope(data, owner, source, version, key, mode):
    if owner is None or data[1] != digest(owner):
        raise ValueError("capture practice offer changed")
    if not isinstance(data[2], str) or data[2] not in GOALS:
        raise ValueError("capture practice offer changed")
    if (source, mode) != ("own-game", "unified"):
        raise ValueError("capture practice offer changed")
    if (data[4], data[5], data[6], data[8]) != (source, version, key, mode):
        raise ValueError("capture practice offer changed")


def binding(db, binding, root, budget):
    if not isinstance(binding, dict) or set(binding) != {
        "revision",
        "capture_input",
        "capture_sources",
    }:
        raise ValueError("capture practice offer changed")
    if type(binding["revision"]) is not int or binding["revision"] != revision(db):
        raise ValueError("capture practice offer changed")
    value = binding["capture_input"]
    _capture_input(value)
    _capture_input(binding["capture_sources"])
    if root is None or budget is None:
        raise ValueError("capture practice offer changed")
    return value
