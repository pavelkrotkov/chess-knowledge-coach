"""Select verified candidates from the exact current prepared window."""

from .capture_finder_proof import PER_SOURCE, _eligible, prove
from .related_capture_pool import require
from .related_capture_prepared_assessment import assessment
from .related_capture_ready import entries


class PreparationPending(Exception):
    """The current requested capture window has not been prepared."""


def _window(db, selection, version, subject, games):
    try:
        return require(db, db.capture_root, version, selection[2], subject, games)
    except ValueError:
        raise PreparationPending() from None


def _available(db, candidate, available, accept):
    if candidate["type"] != "corpus":
        return False
    entry = available.get(candidate["key"])
    if entry is None:
        raise PreparationPending()
    return entry.get("assessment") is not None and _eligible(db, candidate, accept)


def prepared(db, selection, deadline, remaining, expired, subject, games, version, *, accept=None):
    available = entries(_window(db, selection, version, subject, games))
    checked = 0
    for candidate in selection[3][:PER_SOURCE]:
        if expired(deadline) or checked >= remaining:
            break
        if not _available(db, candidate, available, accept):
            continue
        checked += 1
        try:
            assessment(db, candidate["version"], candidate["key"], *selection[:3], subject, games)
        except (ValueError, TypeError, KeyError, IndexError):
            continue
        _window(db, selection, version, subject, games)
        if not expired(deadline):
            return candidate, checked
    _window(db, selection, version, subject, games)
    return None, checked


def select(
    db, selection, deadline, remaining, expired, subject, games, version, difficulty, *, accept=None
):
    if difficulty is not None:
        return prove(db, selection, deadline, remaining, expired, accept=accept)
    return prepared(
        db, selection, deadline, remaining, expired, subject, games, version, accept=accept
    )
