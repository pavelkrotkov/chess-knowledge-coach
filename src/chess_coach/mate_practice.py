"""Offer subject-owned bounded mate witnesses as prepared practice lines."""

from .learner_identity import normalize_identity
from .mate_contract import MAPPER
from .mate_practice_source import VERSION, resolve

LIMIT = 100


def list_candidates(db, subject):
    identity = normalize_identity(subject)
    if not identity:
        return {"version": VERSION, "candidates": [], "excluded": 0}
    rows = db.connection.execute(
        "SELECT e.id FROM evidence_mappings e JOIN mapping_runs r ON r.id=e.mapping_run_id WHERE e.subject=? AND r.producer=? ORDER BY e.id DESC LIMIT ?",
        (identity, MAPPER, LIMIT + 1),
    ).fetchall()
    result, excluded = [], 0
    for row in rows[:LIMIT]:
        try:
            item = resolve(db, VERSION, str(row["id"]), subject)
        except (ValueError, TypeError, KeyError, IndexError):
            excluded += 1
            continue
        result.append({"key": str(row["id"]), "review_status": item["provenance"]["review_status"]})
    return {
        "version": VERSION,
        "candidates": result,
        "excluded": excluded,
        "truncated": len(rows) > LIMIT,
    }
