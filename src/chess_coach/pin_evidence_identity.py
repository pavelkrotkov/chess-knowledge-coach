"""Verify the mapping identity before exposing a current pin fact."""

from .pin_pipeline import VERSION


def mapper_current(db, evidence):
    row = db.connection.execute(
        "SELECT mapper_version,subject,operation,position_id,scope_key FROM mapping_runs WHERE id=?",
        (evidence["mapping_run_id"],),
    ).fetchone()
    if not row or row[0] != evidence["mapper_version"] or row[0] != VERSION:
        return False
    return (
        row[1] == evidence["subject"]
        and row[2] == evidence["operation"]
        and row[3] == evidence["position_id"]
        and row[4] == f"pin-{row[2]}-v1"
    )
