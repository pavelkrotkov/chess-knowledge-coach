"""Subject-scoped, read-only material opportunity and source lineage."""

from .material_opportunity_current import verify_current
from .material_opportunity_loading import load
from .material_opportunity_view import build_view


def inspect_material_opportunity(db, evidence_id, *, learner, _history=None, _check=None):
    evidence, fact, source = load(db, evidence_id, learner)
    result = build_view(evidence, fact, source)
    options = {"check": _check} if _check is not None else {}
    if fact["payload"].get("kind") == "material_capture":
        from .capture_certificate_reader import apply

        apply(db, learner, evidence, fact, source, result, _history, **options)
    else:
        verify_current(db, learner, evidence, fact, source, result, _history, **options)
    return result
