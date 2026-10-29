"""Require the exact current owned mate-in-one mapping and fact."""

from .mate_contract import MAPPER, MAPPER_VERSION
from .mate_selection import mapping_skill
from .objective_contract import VERSION


def valid_key(version, key):
    return version == VERSION and key.isdecimal() and 0 < int(key) < 2**63 and str(int(key)) == key


def eligible(db, evidence, fact):
    return _mapping(db, evidence) and _fact(evidence, fact["payload"])


def _mapping(db, evidence):
    return (
        evidence["skill"] == "mate_in_one"
        and evidence["operation"] == "execute"
        and evidence["outcome"] in {"success", "failure"}
        and evidence["review_status"] in {"accepted", "unreviewed"}
        and _run(db, evidence)
    )


def _run(db, evidence):
    row = db.connection.execute(
        "SELECT producer,position_id,subject,operation,scope_key,mapper_version,status FROM mapping_runs WHERE id=?",
        (evidence["mapping_run_id"],),
    ).fetchone()
    if row is None:
        return False
    return tuple(row) == (
        MAPPER,
        evidence["position_id"],
        evidence["subject"],
        "execute",
        "bounded-mate-v1",
        MAPPER_VERSION,
        "active",
    )


def _fact(evidence, payload):
    try:
        return (
            payload.get("status") == "opportunity"
            and payload.get("outcome") == evidence["outcome"]
            and mapping_skill(payload) == "mate_in_one"
        )
    except (TypeError, ValueError, KeyError):
        return False
