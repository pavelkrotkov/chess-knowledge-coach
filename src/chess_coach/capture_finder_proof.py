"""Bound full capture certificates after cheap setup checks."""

from .related_capture_assessment import certificate, setup

PER_SOURCE = 16


def _supported(db, candidate):
    if candidate["type"] != "corpus":
        return False
    try:
        setup(db, candidate["version"], candidate["key"])
        return True
    except (ValueError, TypeError, KeyError, IndexError):
        return False


def prove(db, selection, deadline, remaining, expired):
    checked = 0
    for candidate in selection[3][:PER_SOURCE]:
        if expired(deadline) or checked >= remaining:
            break
        if not _supported(db, candidate):
            continue
        if expired(deadline):
            break
        checked += 1
        try:
            certificate(db, candidate["version"], candidate["key"])
            if not expired(deadline):
                return candidate, checked
        except (ValueError, TypeError, KeyError, IndexError):
            continue
    return None, checked
