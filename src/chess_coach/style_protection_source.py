"""Find a unique current protection reference inside a read snapshot."""

from .learner_identity import normalize_identity
from .material_policy import MAPPER
from .objective_capture_current import current
from .objective_protection_contract import VERSION
from .objective_protection_source import resolve
from .style_protection_budget import take


def reference(db, subject, position_id):
    identity = normalize_identity(subject)
    if not identity:
        return None, "no_source"
    rows = db.connection.execute(
        """SELECT e.id FROM evidence_mappings e JOIN mapping_runs r ON r.id=e.mapping_run_id
        WHERE e.position_id=? AND e.subject=? AND r.producer=? AND r.status=\u0027active\u0027
        AND e.skill=\u0027hanging_piece\u0027 AND e.operation=\u0027prevent\u0027 ORDER BY e.id DESC LIMIT 2""",
        (position_id, identity, MAPPER),
    ).fetchall()
    if len(rows) == 1:
        return rows[0][0], None
    return None, "multiple_sources" if rows else "no_source"


def load(db, subject, evidence, budget):
    if not take(budget, "resolutions") or not take(budget, "proofs"):
        return None
    return resolve(db, VERSION, str(evidence), subject)


def recheck(db, subject, evidence, provenance, budget):
    if not take(budget, "resolutions"):
        return False
    view, review = current(db, evidence, subject, kind="material_protection", operation="prevent")
    return (
        view["source_fingerprint"] == provenance["source_fingerprint"]
        and (review["id"] if review else None) == provenance["review_event_id"]
        and view["position_id"] == provenance["position_id"]
    )
