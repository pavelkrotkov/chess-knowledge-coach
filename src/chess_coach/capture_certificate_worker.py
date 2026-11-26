"""Produce bounded owned-capture certificates within the existing worker turn."""

from .capture_certificate_progress import next_before, page, save, state
from .capture_certificate_reference import schedule, schedule_reference, session, session_reference
from .capture_certificate_refresh import check, refresh

SCAN = 20
PROOFS = 3


def _evidence(db, subject, current):
    rows, more = page(db, subject, current["before"], 1)
    if not rows:
        return None, current["before"]
    return rows[0], next_before(rows, more, rows[0]["id"])


def _visit(db, subject, root, current, lane, deadline):
    if lane == 0:
        row, marker = _evidence(db, subject, current)
        if row is None:
            return False, 0
        # Preserve the existing retry-on-next-pass policy for timed-out evidence.
        current["before"] = marker
        return True, refresh(db, subject, root, row, deadline)
    name = "session" if lane == 1 else "schedule"
    row, marker = session(db, subject, current[name]) if lane == 1 else schedule(db, current[name])
    if row is None:
        current[name] = marker
        return False, 0
    reference = session_reference(row, subject) if lane == 1 else schedule_reference(row, subject)
    count = refresh(db, subject, root, reference, deadline, reference=reference) if reference else 0
    current[name] = marker
    return True, count


def run(db, subject, root, deadline):
    path, current = state(db, subject, root)
    if path is None:
        return
    visited = checked = 0
    finished = set()
    try:
        while visited < SCAN and checked < PROOFS and len(finished) < 3:
            check(deadline)
            lane = current["lane"]
            current["lane"] = (lane + 1) % 3
            if lane in finished:
                continue
            present, used = _visit(db, subject, root, current, lane, deadline)
            if present:
                visited += 1
                checked += used
            else:
                finished.add(lane)
    except TimeoutError:
        pass
    save(db, subject, path, current)
