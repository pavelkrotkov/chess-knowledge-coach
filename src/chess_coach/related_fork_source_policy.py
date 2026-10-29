"""Require exact fork mapping, operation, ownership and review state."""

from .fork_contract import MAPPER, SCOPE, VERSION
from .learner_identity import normalize_identity


def identity_matches(db, evidence, subject):
    identity = normalize_identity(subject)
    if not identity or evidence["subject"] != identity:
        return False
    if (evidence["mapping_producer"], evidence["mapper_version"], evidence["operation"]) != (
        MAPPER,
        VERSION,
        "execute",
    ):
        return False
    if not _eligible(evidence):
        return False
    run = db.connection.execute(
        "SELECT producer,mapper_version,scope_key,subject,position_id,operation,status FROM mapping_runs WHERE id=?",
        (evidence["mapping_run_id"],),
    ).fetchone()
    return bool(
        run
        and tuple(run)
        == (MAPPER, VERSION, SCOPE, identity, evidence["position_id"], "execute", "active")
    )


def _eligible(evidence):
    return (
        evidence["skill"] == "fork"
        and evidence["outcome"] in {"success", "failure"}
        and evidence["review_status"] in {"accepted", "unreviewed"}
        and evidence["lifecycle_status"] == "active"
    )
