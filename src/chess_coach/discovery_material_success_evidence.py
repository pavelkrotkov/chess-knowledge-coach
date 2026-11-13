"""Revalidate the exact material-success mapping and its current source."""

from functools import partial

from .discovery_material_success_contract import FACT, MAPPER, PRODUCER, SCOPE, VERSION
from .discovery_material_success_observation import observe
from .fork_evidence_current import current_fork
from .fork_evidence_verify import verified_fen


def _mapping(db, evidence):
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
        SCOPE,
        "active",
    )


def _valid(evidence, fact):
    payload = fact.get("payload")
    return (
        evidence["lifecycle_status"] == "active"
        and (
            evidence["skill"],
            evidence["operation"],
            evidence["mapper_version"],
            evidence["mapping_scope"],
        )
        == ("discovered_attack", "prevent", VERSION, SCOPE)
        and (fact["producer"], fact["fact_type"], fact["detector_status"])
        == (PRODUCER, FACT, "active")
        and fact["detector_version"] == fact["run_detector_version"] == VERSION
        and isinstance(payload, dict)
        and (payload.get("kind"), payload.get("outcome"))
        == ("discovery_material_success", evidence["outcome"])
    )


def current(db, evidence, *, _history=None):
    if evidence["mapping_producer"] == MAPPER and not _mapping(db, evidence):
        return {}, "stale", None
    return current_fork(
        db,
        evidence,
        mapper=MAPPER,
        validator=_valid,
        verify=partial(verified_fen, observer=_observe),
        _history=_history,
    )


def _observe(board, played, *_analysis):
    return observe(board, played)
