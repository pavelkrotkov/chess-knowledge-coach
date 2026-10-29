"""Check current or superseded mapper versions for a stored mate fact."""

from .mate_contract import LEGACY_MAPPER_VERSION, MAPPER, MAPPER_VERSION


def mapping_current(db, fact, fact_id, subject):
    if fact.get("status") != "opportunity" or _has_mapping(db, fact_id, subject, MAPPER_VERSION):
        return True
    if _has_mapping(db, fact_id, subject, LEGACY_MAPPER_VERSION):
        return False
    raise ValueError("stored mate mapping is unavailable")


def _has_mapping(db, fact_id, subject, version):
    row = db.connection.execute(
        """SELECT COUNT(*) FROM evidence_fact_links l JOIN evidence_mappings e ON e.id=l.evidence_id
        JOIN mapping_runs r ON r.id=e.mapping_run_id WHERE l.fact_id=? AND l.active=1
        AND l.subject=? AND r.subject=? AND r.producer=? AND r.mapper_version=? AND r.status='active'""",
        (fact_id, subject, subject, MAPPER, version),
    ).fetchone()
    return row[0] == 1
