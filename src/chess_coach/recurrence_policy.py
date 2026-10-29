"""Validate active mapping ownership and linked detector facts."""

from .recurrence_scopes import valid_scope


def mapping_ok(row):
    return (
        row["mapping_status"] == "active"
        and row["mapping_subject"] == row["subject"]
        and row["mapping_position"] == row["position_id"]
        and row["mapping_operation"] == row["operation"]
        and row["mapper_version"] == row["run_mapper_version"]
        and row["source_provenance"] == "linked"
        and valid_scope(row)
    )


def ownership_ok(row, decision):
    return (
        decision is not None
        and decision["subject"] == row["subject"]
        and decision["observation_at"] == row["observation_at"]
        and row["review_decision"] not in {"reject", "revoke"}
    )


def fact_ok(db, row, fact):
    if not fact or fact["detector_status"] != "active":
        return False
    payload = fact["payload"]
    if not isinstance(payload, dict):
        return False
    if (
        row["mapping_producer"]
        not in {
            "back-rank-observation-mapper",
            "pawn-structure-lesson-mapper",
            "rook-plan-lesson-mapper",
            "king-safety-lesson-mapper",
        }
        and payload.get("outcome") != row["outcome"]
    ):
        return False
    positions = db.connection.execute(
        """SELECT f.position_id,d.position_id FROM detector_facts f JOIN detector_runs d
        ON d.id=f.run_id WHERE f.id=?""",
        (fact["id"],),
    ).fetchone()
    return positions is not None and tuple(positions) == (row["position_id"], row["position_id"])
