"""Refresh one source certificate while preserving its legacy bucket neighbors."""

import time

from .capture_certificate_buckets import _in_bucket, _load, publish
from .capture_certificate_paths import paths
from .capture_certificate_producer import identity, prove
from .capture_certificate_store import LIMIT, load
from .material_opportunity_loading import load as source
from .opening_study_source import fingerprint
from .unified_own_game_evidence import _review


def check(deadline):
    if time.monotonic() >= deadline:
        raise TimeoutError("capture certification deadline reached")


def entries(db, root, subject, evidence_id):
    selected = paths(db, root, subject, evidence_id)
    current = _load(db, subject, selected[0], evidence_id)
    if current is not None:
        return dict(current["certificates"]), True
    if fingerprint(selected[:1])[0] is not None:
        return {}, False
    legacy = load(db, root, subject)
    old = legacy["certificates"] if legacy else {}
    index = (evidence_id - 1) // LIMIT
    return {key: value for key, value in old.items() if _in_bucket(key, index)}, False


def _unchanged(db, subject, row, entry):
    if not entry:
        return False
    record, fact, source_data = source(db, row["id"], subject)
    return entry.get("input") == identity(record, fact, source_data, _review(db, row["id"]))


def refresh(db, subject, root, row, deadline, *, reference=None):
    evidence_id = row["id"]
    # Migrate the entire bucket from the legacy file so other evidence remains available.
    records, published = entries(db, root, subject, evidence_id)
    previous = dict(records)
    key = str(evidence_id)
    changed = True
    try:
        changed = not _unchanged(db, subject, row, records.get(key))
        if changed:
            records[key] = prove(db, subject, evidence_id, lambda: check(deadline))
    except (ValueError, TypeError, KeyError, IndexError):
        records.pop(key, None)
    check(deadline)
    if reference is not None:
        _retain_matching(records, previous, key, reference)
    if records != previous or not published:
        publish(db, root, subject, evidence_id, records)
    return changed


def _retain_matching(records, previous, key, reference):
    from .capture_certificate_reference import matches

    if key in records and not matches(records[key], reference):
        if key in previous:
            records[key] = previous[key]
        else:
            records.pop(key)
