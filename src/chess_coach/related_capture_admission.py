"""Resolve opaque references to current capture transfer sources."""

from .fact_fingerprint import canonical, digest
from .related_capture import VERSION, _selection
from .unified_source_current import snapshot_hash


def admit(db, subject, position, corpus_version, reference):
    """Resolve a source-bound opaque reference inside the session transaction."""
    selection = _selection(db, subject, position, corpus_version)
    if selection is None:
        raise ValueError("transfer selection unavailable or stale")
    source, _, _, ordered, scope, _ = selection
    for item in ordered:
        expected = digest(canonical([scope, item["type"], item["version"], item["key"]]))
        if reference == expected:
            provenance = source["provenance"]
            binding = {
                "position_id": provenance["position_id"],
                "evidence_id": provenance["evidence_id"],
                "source_fingerprint": provenance["source_fingerprint"],
                "source_snapshot_hash": snapshot_hash(source),
                "review_event_id": provenance["review_event_id"],
                "rank_version": VERSION,
                "motif": "material_capture",
                "operation": "execute",
                "pattern_cued": True,
            }
            return item["type"], item["version"], item["key"], binding
    raise ValueError("transfer selection unavailable or stale")
