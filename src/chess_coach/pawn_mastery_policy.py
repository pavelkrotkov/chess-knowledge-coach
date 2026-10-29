"""Keep all game-derived pawn-family evidence closed pending qualification."""

from .pawn_coach_contract import FACT_TYPE, FAMILY_SKILLS, MAPPER, PRODUCER
from .pawn_structure_mapping import MAPPER as STRUCTURE_MAPPER
from .rook_plan_mapping import MAPPER as ROOK_MAPPER


def mastery_allowed(db, row):
    if row["skill"] in FAMILY_SKILLS or row["mapping_producer"] in {
        MAPPER,
        STRUCTURE_MAPPER,
        ROOK_MAPPER,
    }:
        return False
    if not row["link_count"]:
        return True
    linked = db.connection.execute(
        """SELECT 1 FROM evidence_fact_links l JOIN detector_facts f ON f.id=l.fact_id
        LEFT JOIN detector_runs r ON r.id=f.run_id
        WHERE l.evidence_id=? AND (r.producer=? OR f.fact_type=?) LIMIT 1""",
        (row["id"], PRODUCER, FACT_TYPE),
    ).fetchone()
    return linked is None
