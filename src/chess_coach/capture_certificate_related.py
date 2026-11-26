"""Bind related-assessment history to its exact owned capture source."""

import json
from copy import deepcopy

from .capture_certificate_reference import _reference
from .learner_identity import normalize_identity
from .objective_capture_contract import TARGET_VERSION


def related_reference(row, subject):
    try:
        binding = json.loads(row["provenance_json"])["related_capture"]
        if row["subject"] != normalize_identity(subject):
            return None
        evidence = binding["evidence_id"]
        reference = _reference(
            subject, TARGET_VERSION, str(evidence), binding["source_snapshot_hash"]
        )
        if reference is None or type(binding["position_id"]) is not int:
            return None
        reference["related"] = {
            key: binding[key] for key in ("position_id", "source_fingerprint", "review_event_id")
        }
        return reference
    except (ValueError, TypeError, KeyError, AttributeError):
        return None


def related_matches(db, entry, reference):
    from .related_capture_source import _opening
    from .unified_source_current import snapshot_hash

    snapshot = deepcopy(entry["snapshot"])
    provenance = snapshot["provenance"]
    expected = reference["related"]
    if any(provenance.get(key) != value for key, value in expected.items()):
        return False
    snapshot["objective"] = "material_capture"
    for key in ("objective_version", "history_mode", "capture_objective", "gain_threshold"):
        del provenance[key]
    provenance["witness_role"] = entry["witness"]["role"]
    snapshot["opening"] = _opening(db, expected["position_id"])
    return snapshot_hash(snapshot) == reference["snapshot_hash"]
