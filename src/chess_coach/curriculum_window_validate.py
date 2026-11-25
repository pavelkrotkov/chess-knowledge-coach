"""Validate signed goal/window cursor policy, scope and times."""

from datetime import timedelta

from .curriculum_window_history import validate_history
from .curriculum_window_scope import POLICY, options
from .mastery_time import parse_utc


def _header(value):
    if not isinstance(value, dict) or set(value) != {
        "v",
        "policy",
        "goal",
        "minutes",
        "page_limit",
        "issued_at",
        "expires_at",
        "state",
        "new_seen",
        "repeat_due",
        "source_refreshed",
        "selection_only",
    }:
        raise ValueError("invalid practice window")
    if value["v"] != 7 or value["policy"] != POLICY:
        raise ValueError("practice window policy changed")
    options(value["goal"], value["minutes"])
    _plan(value)
    validate_history(value)


def _plan(value):
    if type(value["page_limit"]) is not int or not 1 <= value["page_limit"] <= 50:
        raise ValueError("invalid practice window limit")
    if not isinstance(value["state"], dict) or value["state"].get("v") not in {6, 8}:
        raise ValueError("invalid practice window plan")


def _times(value):
    issued, expires = parse_utc(value["issued_at"]), parse_utc(value["expires_at"])
    if issued is None:
        raise ValueError("invalid practice window time")
    expected = issued + timedelta(minutes=value["minutes"]) if value["minutes"] else None
    if expires != expected:
        raise ValueError("invalid practice window deadline")


def validate(value):
    _header(value)
    _times(value)
