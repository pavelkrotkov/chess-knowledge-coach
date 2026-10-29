"""Load subject-scoped candidates and explain eligibility exclusions."""

from .learner_identity import normalize_identity
from .material_opportunities import inspect_material_opportunity
from .material_policy import MAPPER
from .unified_own_game_snapshot import KINDS, snapshot

LIMIT = 100


def _rows(db, subject, position=None):
    identity = normalize_identity(subject)
    if not identity:
        raise ValueError("practice subject unavailable")
    clause = " AND e.position_id=?" if position is not None else ""
    params = (
        (identity, MAPPER, position, LIMIT + 1)
        if position is not None
        else (identity, MAPPER, LIMIT + 1)
    )
    return db.connection.execute(
        """SELECT e.id FROM evidence_mappings e JOIN mapping_runs r ON r.id=e.mapping_run_id
        WHERE e.subject=? AND r.producer=?"""
        + clause
        + " ORDER BY e.id DESC LIMIT ?",
        params,
    ).fetchall()


def _review(db, evidence_id):
    return db.connection.execute(
        "SELECT id,evidence_id,decision FROM evidence_review_events WHERE evidence_id=? ORDER BY id DESC LIMIT 1",
        (evidence_id,),
    ).fetchone()


def _reasons(view):
    checks = (
        (view["currentness"] != "current", "stale or unavailable source"),
        (view["outcome"] not in {"success", "failure"}, "ambiguous observation"),
        (
            view["review_status"] in {"rejected", "revoked"},
            "review rejected or revoked",
        ),
        (not view["family_validated"], "detector family not independently validated"),
        (not view["objective_witness"], "verified witness unavailable"),
        (view["objective"].get("kind") not in KINDS, "unsupported objective"),
        (not view["eligible_for_exercise_candidate"], "opportunity ineligible"),
    )
    return [reason for failed, reason in checks if failed]


def _inspect(db, evidence_id, subject):
    try:
        view = inspect_material_opportunity(db, evidence_id, learner=subject)
        review = _review(db, evidence_id)
        reasons = _reasons(view)
        if not reasons:
            snapshot(view, review, evidence_id)
        return view, review, reasons
    except (ValueError, KeyError, TypeError, IndexError):
        return None, None, ["stale or unavailable source"]
