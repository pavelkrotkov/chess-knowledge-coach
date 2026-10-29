"""Resolve opaque transfer references and bind immutable source lineage."""

from .fact_fingerprint import canonical, digest
from .related_fork_lines import FILTER_VERSION
from .unified_source_current import snapshot_hash


def admit(selection, reference, version, motif):
    if selection is None:
        raise ValueError("transfer selection unavailable or stale")
    source, _, _, ordered, scope, _ = selection
    for item in ordered:
        expected = digest(canonical([scope, item["type"], item["version"], item["key"]]))
        if reference == expected:
            return (
                item["type"],
                item["version"],
                item["key"],
                _binding(source, version, motif, item),
                item.get("matching_lines"),
            )
    raise ValueError("transfer selection unavailable or stale")


def _binding(source, version, motif, item):
    provenance = source["provenance"]
    binding = {
        "position_id": provenance["position_id"],
        "evidence_id": provenance["evidence_id"],
        "source_fingerprint": provenance["source_fingerprint"],
        "source_snapshot_hash": snapshot_hash(source),
        "review_event_id": provenance["review_event_id"],
        "rank_version": version,
        "motif": motif,
        "operation": "execute",
        "pattern_cued": True,
    }

    if motif == "fork":
        binding.update(
            line_filter_version=FILTER_VERSION,
            selected_line_indices=item["matching_line_indices"],
            source_lines_hash=item["source_lines_hash"],
        )
    return binding
