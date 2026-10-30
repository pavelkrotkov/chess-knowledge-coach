"""Resolve opaque transfer references and bind immutable source lineage."""

from .fact_fingerprint import canonical, digest
from .related_transfer_filter import filter_version
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
        "operation": "prevent"
        if motif in {"protection", "fork_prevention", "fork_avoidance"}
        else "execute",
        "pattern_cued": True,
    }

    if motif == "protection":
        binding["objective_target"] = item["objective_target"]
        binding["protection_mechanism"] = item["protection_mechanism"]
        binding["gain_threshold"] = 3

    if motif == "fork_prevention":
        binding.update(
            threat_origin="positional_before_played",
            defense_role=item["defense_role"],
            target_roles=item["target_roles"],
        )

    if motif == "fork_avoidance":
        binding.update(
            threat_origin="created_by_played_move",
            created_witness=item["created_witness"],
            defense_role=item["defense_role"],
            target_roles=item["target_roles"],
        )

    if motif == "mate":
        binding["mate_timing"] = source["objective"]

    if motif in {"fork", "protection", "fork_prevention", "fork_avoidance", "mate"}:
        binding.update(
            line_filter_version=filter_version(motif),
            selected_line_indices=item["matching_line_indices"],
            source_lines_hash=item["source_lines_hash"],
        )
    return binding
