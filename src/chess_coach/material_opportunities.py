"""Subject-scoped, read-only material opportunity and source lineage."""

from .material_opportunity_current import verify_current
from .material_opportunity_loading import load
from .material_opportunity_view import build_view


def inspect_material_opportunity(db, evidence_id, *, learner):
    evidence, fact, source = load(db, evidence_id, learner)
    result = build_view(evidence, fact, source)
    verify_current(db, learner, evidence, fact, source, result)
    return result
