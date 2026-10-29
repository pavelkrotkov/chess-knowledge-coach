"""Recheck the lesson snapshot and its cited source."""

from .lesson_history import get
from .lesson_mechanisms import describe
from .lesson_source import source


def checked(db, subject, lesson_id, evidence_id):
    try:
        return _checked(db, subject, lesson_id, evidence_id)
    except (KeyError, TypeError, IndexError, AttributeError):
        raise ValueError("lesson source unavailable") from None


def _checked(db, subject, lesson_id, evidence_id):
    lesson = get(db, subject, lesson_id)["lesson"]
    example = next((x for x in lesson["examples"] if x["evidence_id"] == evidence_id), None)
    if not example:
        raise ValueError("lesson source unavailable")
    checked = source(db, subject, {"id": evidence_id, "position_id": example["position_id"]})
    if not checked:
        raise ValueError("lesson source unavailable")
    fresh = describe(checked)
    if not fresh or any(example.get(k) != v for k, v in fresh.items()):
        raise ValueError("lesson source changed")
    evidence, decision = checked["evidence"], checked["decision"]
    _check_scope(lesson, evidence)
    return lesson, example, fresh, evidence, decision


def _check_scope(lesson, evidence):
    if (lesson["family"], lesson["skill"], lesson["operation"]) != (
        evidence["mapping_producer"],
        evidence["skill"],
        evidence["operation"],
    ):
        raise ValueError("lesson scope changed")
    if lesson["source_version"] != evidence["facts"][0]["detector_version"]:
        raise ValueError("lesson version changed")
