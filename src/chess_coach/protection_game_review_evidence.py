"""Recheck an applicable material-protection observation and review."""

from .material_contract import SCOPE, VERSION
from .material_opportunity_loading import load
from .material_policy import MAPPER, fact_allowed


def checked(db, position_id, game_id, subject, row, payload):
    link = db.connection.execute(
        """SELECT evidence_id FROM evidence_fact_links WHERE fact_id=? AND subject=?
        AND skill='hanging_piece' AND operation='prevent' AND active=1""",
        (row["fact_id"], subject),
    ).fetchone()
    if link is None:
        raise ValueError("protection mapping unavailable")
    evidence, fact, source = load(db, link["evidence_id"], subject)
    mapping = db.connection.execute(
        "SELECT producer,mapper_version,subject,operation,position_id,scope_key,status "
        "FROM mapping_runs WHERE id=?",
        (evidence["mapping_run_id"],),
    ).fetchone()
    expected = (MAPPER, VERSION, subject, "prevent", position_id, SCOPE, "active")
    if mapping is None or tuple(mapping) != expected:
        raise ValueError("protection mapping unavailable")
    if (evidence["position_id"], evidence["game_id"]) != (position_id, game_id):
        raise ValueError("protection evidence unavailable")
    checks = (
        evidence["lifecycle_status"] == "active",
        evidence["review_status"] in {"unreviewed", "accepted"},
        evidence["material_source_currentness"] == "current",
        fact["detector_status"] == "active",
        fact["id"] == row["fact_id"],
        fact["payload"] == payload,
        fact_allowed(
            fact,
            skill=evidence["skill"],
            operation=evidence["operation"],
            outcome=evidence["outcome"],
        ),
    )
    if not all(checks):
        raise ValueError("protection evidence unavailable")
    review = db.connection.execute(
        "SELECT id FROM evidence_review_events WHERE evidence_id=? ORDER BY id DESC LIMIT 1",
        (evidence["id"],),
    ).fetchone()
    return [
        row["id"],
        row["fact_id"],
        evidence["id"],
        evidence["review_status"],
        review["id"] if review else None,
        source["source_marker"],
    ]
