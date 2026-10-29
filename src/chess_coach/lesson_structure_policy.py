"""Admit only the exact, current descriptive pawn-structure contract."""

from .pawn_structure_probe import state


def _mapping(evidence):
    return (
        evidence["skill"] == "pawn_structure"
        and evidence["operation"] == "evaluate"
        and evidence["outcome"] == "ambiguous"
        and evidence["mapping_scope"] == "pawn-structure-lesson"
        and evidence["mapper_version"] == "1.1.0"
    )


def _fact(fact):
    payload = fact["payload"]
    return (
        fact["producer"] == "pawn-structure-lesson"
        and fact["fact_type"] == "pawn_structure_lesson"
        and fact["detector_version"] == fact["run_detector_version"] == "1.1.0"
        and payload.get("version") == "1.1.0"
        and payload.get("mastery_eligible") is False
    )


def structure_supported(db, evidence, fact, *, _history=None):
    return (
        _mapping(evidence)
        and _fact(fact)
        and state(db, evidence["position_id"], evidence["subject"], _history=_history) == "current"
    )
