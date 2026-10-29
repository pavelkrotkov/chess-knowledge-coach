"""Compute expected synthetic transfer identities independently of rendered JSON."""

import hashlib
import json

from chess_coach.unified_sources import resolve_source


def digest(value):
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode()).hexdigest()


def references(selection):
    _, _, _, ordered, scope, _ = selection
    return [digest([scope, item["type"], item["version"], item["key"]]) for item in ordered]


def expected_binding(db, selection, reference, subject, *, fork):
    source, _, _, ordered, _, _ = selection
    item = ordered[references(selection).index(reference)]
    expected = {
        "source_fingerprint": source["provenance"]["source_fingerprint"],
        "source_snapshot_hash": digest(source),
    }
    if fork:
        snapshot = resolve_source(db, item["type"], item["version"], item["key"], subject=subject)
        expected["source_lines_hash"] = digest(snapshot["lines"])
    return expected
