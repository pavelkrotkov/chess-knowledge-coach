"""Bounded evidence pages and provisional recurrence screening."""

from .material_contract import SCOPE, VERSION
from .material_policy import MAPPER

ROW_LIMIT = 32


def rows(db, subject, phase, before, lower):
    return db.connection.execute(
        """SELECT e.id,e.outcome,e.mapper_version,p.game_id,r.producer,
        r.mapper_version AS run_version,r.scope_key,r.status,
        (SELECT decision FROM evidence_review_events WHERE evidence_id=e.id
         ORDER BY id DESC LIMIT 1) AS review
        FROM (SELECT * FROM evidence_mappings INDEXED BY idx_curriculum_evidence
              WHERE subject=? AND skill='hanging_piece' AND operation='prevent' AND id<? AND id>=?
              AND outcome=?
              ORDER BY id DESC LIMIT ?) e
        LEFT JOIN positions p ON p.id=e.position_id
        LEFT JOIN mapping_runs r ON r.id=e.mapping_run_id ORDER BY e.id DESC""",
        (subject, before, lower, "failure" if phase == 0 else "success", ROW_LIMIT),
    ).fetchall()


def eligible(row, phase):
    return (
        row["outcome"] == ("failure" if phase == 0 else "success")
        and row["producer"] == MAPPER
        and row["run_version"] == VERSION
        and row["scope_key"] == SCOPE
        and row["status"] == "active"
        and row["review"] not in ("reject", "revoke")
        and row["game_id"] is not None
    )


def recurring(rows, row):
    return any(
        other["id"] != row["id"]
        and eligible(other, 0)
        and other["mapper_version"] == row["mapper_version"]
        and other["game_id"] != row["game_id"]
        for other in rows
    )


def preferred(page, row, phase):
    return eligible(row, phase) and (phase == 1 or recurring(page, row))
