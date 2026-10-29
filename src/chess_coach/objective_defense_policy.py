"""Require the exact current owned back-rank prevention mapping."""

from .back_rank_contract import MAPPER, VERSION


def eligible(db, evidence, fact):
    if evidence["skill"] != "back_rank" or evidence["operation"] != "prevent":
        return False
    if evidence["review_status"] not in {"accepted", "unreviewed"}:
        return False
    if evidence["outcome"] not in {"success", "failure"}:
        return False
    if fact["payload"].get("defense", {}).get("status") != "opportunity":
        return False
    row = db.connection.execute(
        "SELECT producer,mapper_version,subject,operation,position_id,scope_key,status FROM mapping_runs WHERE id=?",
        (evidence["mapping_run_id"],),
    ).fetchone()
    return row is not None and tuple(row) == (
        MAPPER,
        VERSION,
        evidence["subject"],
        "prevent",
        evidence["position_id"],
        "back-rank-prevent",
        "active",
    )
