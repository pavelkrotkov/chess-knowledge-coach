"""Select verified candidates from the exact current prepared window."""

from functools import partial

from .capture_finder_proof import prove
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


def _available(db, candidate, accept, *, available):
    if candidate["type"] != "corpus":
        return False
    entry = available.get(candidate["key"])
    if entry is None:
        raise PreparationPending()
    return entry.get("assessment") is not None and (accept is None or accept(candidate))


def prepared(db, selection, deadline, remaining, expired, subject, games, version, *, accept=None):
    available = entries(_window(db, selection, version, subject, games))
    qualify = partial(
        assessment,
        source=selection[0],
        baseline=selection[1],
        corpus=selection[2],
        subject=subject,
        games=games,
    )
    result = prove(
        db,
        selection,
        deadline,
        remaining,
        expired,
        accept=accept,
        eligible=partial(_available, available=available),
        certify=qualify,
    )
    _window(db, selection, version, subject, games)
    return result
