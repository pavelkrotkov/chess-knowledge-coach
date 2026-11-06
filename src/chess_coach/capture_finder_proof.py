"""Bound full capture certificates after cheap setup checks."""

from .related_capture_assessment import certificate, setup

PER_SOURCE = 16


def prove(db, selection, deadline, remaining, expired):
    checked = 0
    for candidate in selection[3][:PER_SOURCE]:
        if expired(deadline) or checked >= remaining:
            break
        if candidate["type"] != "corpus":
            continue
        try:
            setup(db, candidate["version"], candidate["key"])
        except (ValueError, TypeError, KeyError, IndexError):
            continue
        checked += 1
        try:
            certificate(db, candidate["version"], candidate["key"])
            if not expired(deadline):
                return candidate, checked
        except (ValueError, TypeError, KeyError, IndexError):
            continue
    return None, checked
