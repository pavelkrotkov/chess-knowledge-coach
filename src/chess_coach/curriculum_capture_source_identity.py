"""Bind the two bounded capture witnesses to their current source provenance."""

from .capture_plan_sources import _groups, witnesses
from .fact_fingerprint import canonical, digest
from .objective_capture_current import current
from .related_capture_position import prompt_key


def collect(db, subject, check):
    groups, limited, scanned = _groups(db, subject, check=check)
    selected, identities, seen = [], [], set()
    for source in witnesses(db, subject, groups, check=check):
        check()
        if source["games"] < 2:
            continue
        view, review = current(db, source["evidence_id"], subject, check=check)
        key = prompt_key(view["decision_fen"])
        if key in seen:
            continue
        seen.add(key)
        selected.append(source)
        identities.append(digest(canonical([source, view, review])))
        if len(selected) == 2:
            break
    check()
    return selected, limited, scanned, digest(canonical([limited, scanned, identities]))


def snapshot(db, subject, check):
    return collect(db, subject, check)[3]


def require(db, subject, expected, check):
    if snapshot(db, subject, check) != expected:
        raise ValueError("capture sources changed")
