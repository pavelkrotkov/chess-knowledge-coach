"""Admit only current, exact, descriptive king-safety facts."""

from .king_safety_probe import state


def supported_king(db, evidence, fact, *, _history=None):
    return (
        (evidence["skill"], evidence["operation"], evidence["outcome"])
        == ("king_safety", "evaluate", "ambiguous")
        and evidence["mapping_scope"] == "king-safety-lesson"
        and evidence["mapper_version"] == "1.0.0"
        and (fact["producer"], fact["fact_type"]) == ("king-safety-lesson", "king_safety_lesson")
        and fact["detector_version"] == fact["run_detector_version"] == "1.0.0"
        and fact["payload"].get("version") == "1.0.0"
        and fact["payload"].get("mastery_eligible") is False
        and state(db, evidence["position_id"], evidence["subject"], _history=_history) == "current"
    )
