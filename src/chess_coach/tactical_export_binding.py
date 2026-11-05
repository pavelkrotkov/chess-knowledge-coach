"""Recheck one owned supporting source and its immutable lineage."""

from .fact_fingerprint import canonical
from .lesson_mechanisms import describe
from .lesson_source import source
from .tactical_course_evidence import _binding


def example(db, subject, pattern, saved, budget):
    with budget.scope(snapshot=True):
        current = source(
            db, subject, {"id": saved["evidence_id"], "position_id": saved["position_id"]}
        )
        if current is None:
            raise ValueError("supporting source unavailable")
        item = describe(current)
        if item is None or not item["lines"]:
            raise ValueError("supporting lesson unavailable")
        if canonical(_binding(db, subject, item, current=current)) != canonical(saved):
            raise ValueError("supporting source changed")
        evidence = current["evidence"]
        if (
            evidence["skill"],
            evidence["operation"],
            evidence["mapping_producer"],
            evidence["outcome"],
        ) != (pattern["skill"], pattern["operation"], pattern["family"], "failure"):
            raise ValueError("supporting source differs")
        return item
