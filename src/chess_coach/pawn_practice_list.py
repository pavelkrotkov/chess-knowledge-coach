"""Verify at most one subject-owned pawn preview per page."""

from collections import Counter

from .learner_identity import normalize_identity
from .pawn_coach_contract import MAPPER
from .pawn_practice import VERSION, _objective, _view
from .pawn_practice_keys import evidence_id


def _rows(db, subject, before):
    return db.connection.execute(
        """SELECT e.id FROM evidence_mappings e JOIN mapping_runs r ON r.id=e.mapping_run_id
        WHERE e.subject=? AND r.producer=? AND r.status=?
        AND e.outcome IN (?,?) AND (?=0 OR e.id<?)
        ORDER BY e.id DESC LIMIT 2""",
        (subject, MAPPER, "active", "success", "failure", before, before),
    ).fetchall()


def list_candidates(db, subject, *, before=None):
    cursor = evidence_id(before) if before is not None else 0
    identity = normalize_identity(subject)
    if not identity:
        return {
            "version": VERSION,
            "candidates": [],
            "excluded": {"subject unavailable": 1},
            "scanned": 0,
            "truncated": False,
            "next_before": None,
        }
    rows = _rows(db, identity, cursor)
    candidates, excluded = [], Counter()
    if rows:
        try:
            evidence = _view(db, rows[0]["id"], identity)
            candidates.append(
                {
                    "key": str(rows[0]["id"]),
                    "objective": _objective(evidence),
                    "review_status": evidence["review_status"],
                }
            )
        except ValueError:
            excluded["stale, rejected, or unavailable"] += 1
    return {
        "version": VERSION,
        "candidates": candidates,
        "excluded": dict(excluded),
        "scanned": min(len(rows), 1),
        "truncated": len(rows) > 1,
        "next_before": str(rows[0]["id"]) if len(rows) > 1 else None,
    }
