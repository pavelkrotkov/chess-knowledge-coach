"""Produce bounded owned-capture certificates within the existing worker turn."""

from .capture_certificate_progress import checkpoint, next_before, page, save
from .capture_certificate_refresh import check, refresh

SCAN = 20
PROOFS = 3


def run(db, subject, root, deadline):
    path, before = checkpoint(db, subject, root)
    if path is None:
        return
    rows, more = page(db, subject, before, SCAN)
    checked = 0
    last = None
    try:
        for row in rows:
            check(deadline)
            last = row["id"]
            checked += refresh(db, subject, root, row, deadline)
            if checked >= PROOFS:
                break
    except TimeoutError:
        pass
    # A timed-out source remains unknown and is retried on the next full pass.
    if last is not None:
        save(db, subject, path, next_before(rows, more, last))
