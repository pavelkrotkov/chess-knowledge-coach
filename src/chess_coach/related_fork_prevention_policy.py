"""Require the exact owned current fork-prevention mapping and review."""

from .fork_defense_contract import MAPPER, SCOPE, VERSION
from .learner_identity import normalize_identity


def identity_matches(db, evidence, subject):
    identity = normalize_identity(subject)
    if not identity or evidence["subject"] != identity or not _eligible(evidence):
        return False
    if (evidence["mapping_producer"], evidence["mapper_version"]) != (MAPPER, VERSION):
        return False
    row = db.connection.execute(
        "SELECT producer,mapper_version,scope_key,subject,position_id,operation,status FROM mapping_runs WHERE id=?",
        (evidence["mapping_run_id"],),
    ).fetchone()
    return bool(
        row
        and tuple(row)
        == (MAPPER, VERSION, SCOPE, identity, evidence["position_id"], "prevent", "active")
    )


def _eligible(evidence):
    return (
        evidence["skill"] == "fork"
        and evidence["operation"] == "prevent"
        and evidence["outcome"] in {"success", "failure"}
        and evidence["review_status"] in {"accepted", "unreviewed"}
        and evidence["lifecycle_status"] == "active"
    )
