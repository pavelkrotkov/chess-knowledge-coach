"""Scan a small subject-owned window for provisional pawn practice."""

from collections import Counter

from .learner_identity import normalize_identity
from .pawn_coach_contract import MAPPER
from .pawn_practice import VERSION, _objective, _view

LIMIT = 4


def _rows(db, subject):
    return db.connection.execute(
        """SELECT e.id FROM evidence_mappings e JOIN mapping_runs r ON r.id=e.mapping_run_id
        WHERE e.subject=? AND r.producer=? AND r.status='active'
        AND e.outcome IN ('success','failure') ORDER BY e.id DESC LIMIT ?""",
        (subject, MAPPER, LIMIT + 1),
    ).fetchall()


def list_candidates(db, subject):
    identity = normalize_identity(subject)
    if not identity:
        return {
            "version": VERSION,
            "candidates": [],
            "excluded": {"subject unavailable": 1},
            "scanned": 0,
            "truncated": False,
        }
    rows = _rows(db, identity)
    candidates, excluded = [], Counter()
    for row in rows[:LIMIT]:
        try:
            evidence = _view(db, row["id"], identity)
            candidates.append(
                {
                    "key": str(row["id"]),
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
        "scanned": min(len(rows), LIMIT),
        "truncated": len(rows) > LIMIT,
    }
