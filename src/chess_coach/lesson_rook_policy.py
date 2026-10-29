"""Admit only the exact, current descriptive rook-plan contract."""

from .rook_plan_probe import state


def _mapping(evidence):
    return (
        (evidence["skill"], evidence["operation"], evidence["outcome"])
        == ("open_files", "evaluate", "ambiguous")
        and evidence["mapping_scope"] == "rook-plan-lesson"
        and evidence["mapper_version"] == "1.1.0"
    )


def _fact(fact):
    payload = fact["payload"]
    return (
        fact["producer"] == "rook-plan-lesson"
        and fact["fact_type"] == "rook_plan_lesson"
        and fact["detector_version"] == fact["run_detector_version"] == "1.1.0"
        and payload.get("version") == "1.1.0"
        and payload.get("mastery_eligible") is False
    )


def rook_supported(db, evidence, fact):
    return (
        _mapping(evidence)
        and _fact(fact)
        and state(db, evidence["position_id"], evidence["subject"]) == "current"
    )
