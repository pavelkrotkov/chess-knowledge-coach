"""Read evidence and linked-source status for mastery eligibility."""

from __future__ import annotations

from .db import Database


def evidence_rows(db: Database, subject: str, skill: str, operation: str):
    return db.connection.execute(
        """SELECT e.id, e.position_id, e.subject, e.operation, e.outcome, e.confidence, e.observation_at,
                  e.human_validated, e.source_provenance, e.mapping_run_id,
                  r.status AS mapping_status, r.subject AS mapping_subject,
                  r.operation AS mapping_operation, r.position_id AS mapping_position,
                  p.game_id, p.ply, g.source, g.source_id,
                  v.decision AS review_decision, v.actor AS review_actor,
                  (SELECT COUNT(*) FROM evidence_fact_links l
                   WHERE l.evidence_id = e.id) AS link_count,
                  (SELECT COUNT(*) FROM evidence_fact_links l
                   LEFT JOIN detector_facts f ON f.id = l.fact_id
                   LEFT JOIN detector_runs d ON d.id = f.run_id
                   WHERE l.evidence_id = e.id AND (
                     l.active != 1 OR l.subject != e.subject OR l.skill != e.skill
                     OR l.operation != e.operation OR f.id IS NULL OR f.position_id != e.position_id
                     OR d.id IS NULL OR d.position_id != e.position_id OR d.status != 'active'
                   )) AS invalid_links
        FROM evidence_mappings e
        LEFT JOIN mapping_runs r ON r.id = e.mapping_run_id
        LEFT JOIN positions p ON p.id = e.position_id
        LEFT JOIN games g ON g.id = p.game_id
        LEFT JOIN evidence_review_events v ON v.id = (
            SELECT id FROM evidence_review_events WHERE evidence_id = e.id ORDER BY id DESC LIMIT 1
        )
        WHERE e.subject = ? AND e.skill = ? AND e.operation = ? ORDER BY e.id""",
        (subject, skill, operation),
    ).fetchall()
