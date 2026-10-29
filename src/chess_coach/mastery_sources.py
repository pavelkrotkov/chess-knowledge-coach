"""Read evidence and linked-source status for mastery eligibility."""

from __future__ import annotations

from .db import Database
from .fork_contract import PRODUCER as FORK_PRODUCER
from .fork_defense_contract import PRODUCER as DEFENSE_PRODUCER
from .material_contract import PRODUCER


def evidence_rows(db: Database, subject: str, skill: str, operation: str):
    return db.connection.execute(
        """SELECT e.id, e.position_id, e.subject, e.skill, e.operation, e.outcome, e.confidence, e.observation_at,
                  e.human_validated, e.source_provenance, e.mapping_run_id, e.mapper_version,
                  r.status AS mapping_status, r.producer AS mapping_producer, r.mapper_version AS run_mapper_version,
                  r.subject AS mapping_subject,
                  r.operation AS mapping_operation, r.position_id AS mapping_position,
                  p.game_id, p.ply, g.source, g.source_id,
                  v.decision AS review_decision, v.actor AS review_actor,
                  (SELECT COUNT(*) FROM evidence_fact_links l
                   WHERE l.evidence_id = e.id) AS link_count,
                  (SELECT COUNT(*) FROM evidence_fact_links l
                   JOIN detector_facts f ON f.id=l.fact_id JOIN detector_runs d ON d.id=f.run_id
                   WHERE l.evidence_id=e.id AND (d.producer=? OR f.fact_type='material_opportunity'))
                   AS material_fact_count,
                  (SELECT COUNT(*) FROM evidence_fact_links l
                   JOIN detector_facts f ON f.id=l.fact_id JOIN detector_runs d ON d.id=f.run_id
                   WHERE l.evidence_id=e.id AND (d.producer=? OR f.fact_type='fork_opportunity'))
                   AS fork_fact_count,
                  (SELECT COUNT(*) FROM evidence_fact_links l
                   JOIN detector_facts f ON f.id=l.fact_id JOIN detector_runs d ON d.id=f.run_id
                   WHERE l.evidence_id=e.id AND (d.producer=? OR f.fact_type='fork_defense_opportunity'))
                   AS fork_defense_fact_count,
                  (SELECT COUNT(*) FROM evidence_fact_links l
                   JOIN detector_facts f ON f.id=l.fact_id JOIN detector_runs d ON d.id=f.run_id
                   WHERE l.evidence_id=e.id AND (d.producer IN ('pin-execute', 'pin-prevent') OR f.fact_type IN ('pin_execute_opportunity', 'pin_prevent_opportunity'))) AS pin_fact_count,
                  (SELECT COUNT(*) FROM evidence_fact_links l
                   JOIN detector_facts f ON f.id=l.fact_id JOIN detector_runs d ON d.id=f.run_id
                   WHERE l.evidence_id=e.id AND (d.producer='bounded-mate-observation' OR f.fact_type='bounded_mate'))
                   AS bounded_mate_fact_count,
                  (SELECT COUNT(*) FROM evidence_fact_links l
                   JOIN detector_facts f ON f.id=l.fact_id JOIN detector_runs d ON d.id=f.run_id
                   WHERE l.evidence_id=e.id AND (d.producer='back-rank-observation' OR f.fact_type='back_rank'))
                   AS back_rank_fact_count,
                  (SELECT COUNT(*) FROM evidence_fact_links l
                   JOIN detector_facts f ON f.id=l.fact_id JOIN detector_runs d ON d.id=f.run_id
                   WHERE l.evidence_id=e.id AND (d.producer='king-safety-lesson' OR f.fact_type='king_safety_lesson'))
                   AS king_safety_fact_count,
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
        (PRODUCER, FORK_PRODUCER, DEFENSE_PRODUCER, subject, skill, operation),
    ).fetchall()
