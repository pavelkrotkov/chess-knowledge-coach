"""Offer current subject-owned back-rank prepared lines."""

from .back_rank_contract import MAPPER
from .back_rank_practice_source import VERSION, resolve
from .learner_identity import normalize_identity

LIMIT = 100


def list_candidates(db, subject):
    identity = normalize_identity(subject)
    if not identity:
        return {"version": VERSION, "candidates": [], "excluded": 0}
    rows = db.connection.execute(
        """SELECT e.id FROM evidence_mappings e JOIN mapping_runs r ON r.id=e.mapping_run_id
        WHERE e.subject=? AND r.producer=? ORDER BY e.id DESC LIMIT ?""",
        (identity, MAPPER, LIMIT + 1),
    ).fetchall()
    ready, excluded = [], 0
    for row in rows[:LIMIT]:
        try:
            item = resolve(db, VERSION, str(row["id"]), subject)
        except (ValueError, TypeError, KeyError, IndexError):
            excluded += 1
            continue
        ready.append(
            {
                "key": str(row["id"]),
                "objective": item["objective"],
                "review_status": item["provenance"]["review_status"],
            }
        )
    return {
        "version": VERSION,
        "candidates": ready,
        "excluded": excluded,
        "truncated": len(rows) > LIMIT,
    }
