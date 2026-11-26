"""Produce bounded owned-capture certificates within the existing worker turn."""

import time

from .capture_certificate_producer import identity, prove
from .capture_certificate_store import load, publish
from .material_opportunity_loading import load as source
from .recurrence_cursor import MAX_ID
from .recurrence_sources import evidence
from .unified_own_game_evidence import _review

SCAN = 20
PROOFS = 3


def _check(deadline):
    if time.monotonic() >= deadline:
        raise TimeoutError("capture certification deadline reached")


def _unchanged(db, subject, row, entry):
    if not entry:
        return False
    record, fact, source_data = source(db, row["id"], subject)
    return entry.get("input") == identity(record, fact, source_data, _review(db, row["id"]))


def _refresh(db, subject, row, retained, deadline):
    _check(deadline)
    key = str(row["id"])
    try:
        if _unchanged(db, subject, row, retained.get(key)):
            return False
        retained[key] = prove(db, subject, row["id"], lambda: _check(deadline))
    except (ValueError, TypeError, KeyError, IndexError):
        retained.pop(key, None)
    return True


def run(db, subject, root, deadline):
    if root is None:
        return
    rows, _ = evidence(
        db, subject, "hanging_piece", "execute", MAX_ID, failure_only=True, limit=SCAN
    )
    previous = load(db, root, subject)
    old = previous["certificates"] if previous else {}
    retained = {str(row["id"]): old[str(row["id"])] for row in rows if str(row["id"]) in old}
    # Reused certificates consume no proof quota; an expired turn publishes nothing.
    checked = 0
    try:
        for row in rows:
            checked += _refresh(db, subject, row, retained, deadline)
            if checked >= PROOFS:
                break
        _check(deadline)
    except TimeoutError:
        return
    publish(db, root, subject, retained)
