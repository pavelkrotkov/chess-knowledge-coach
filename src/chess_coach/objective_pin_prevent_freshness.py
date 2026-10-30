"""Recheck source identity without re-running its bounded observer."""

from .evidence_review_details import _reviews
from .evidence_review_facts import facts_for_evidence
from .evidence_review_json import decode
from .evidence_review_state import _summary, evidence_row
from .material_opportunity_links import valid_link
from .material_opportunity_source import load_source
from .material_source_marker import source_marker
from .pin_evidence_identity import mapper_current


def require_unchanged(db, evidence, fact, source):
    row = evidence_row(db, evidence["id"])
    summary = _summary(row)
    if any(evidence.get(key) != value for key, value in summary.items()):
        raise ValueError("pin prevention source changed")
    if decode(row["context_json"]) != evidence["context"]:
        raise ValueError("pin prevention context changed")
    if _reviews(db, evidence["id"]) != evidence["reviews"]:
        raise ValueError("pin prevention review changed")
    _require_facts(db, evidence, fact, source, summary)


def _require_facts(db, evidence, fact, source, summary):
    facts = facts_for_evidence(db, evidence["id"])
    fresh = {**summary, "facts": facts}
    if (
        facts != evidence["facts"]
        or not mapper_current(db, fresh)
        or not valid_link(db, fresh, fact)
    ):
        raise ValueError("pin prevention fact changed")
    if load_source(db, fact["detector_run_id"]) != source:
        raise ValueError("pin prevention detector input changed")
    if (
        source_marker(db, evidence["position_id"], evidence["game_id"], evidence["subject"])
        != source["source_marker"]
    ):
        raise ValueError("pin prevention inputs changed")
