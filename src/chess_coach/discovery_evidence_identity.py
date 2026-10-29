"""Bind discovery evidence to its exact active mapping run."""

from .discovery_contract import FACT, MAPPER, PRODUCER, SCOPE, VERSION


def belongs(evidence):
    if evidence["mapping_producer"] == MAPPER:
        return True
    return any(
        fact.get("producer") == PRODUCER or fact.get("fact_type") == FACT
        for fact in evidence["facts"]
    )


def run_matches(db, evidence):
    row = db.connection.execute(
        "SELECT r.producer,r.mapper_version,r.subject,r.operation,r.position_id,r.scope_key,r.status, e.mapper_version,e.subject,e.operation,e.position_id,e.skill,e.mapping_run_id FROM evidence_mappings e JOIN mapping_runs r ON r.id=e.mapping_run_id WHERE e.id=?",
        (evidence["id"],),
    ).fetchone()
    return row is not None and tuple(row) == (
        MAPPER,
        VERSION,
        evidence["subject"],
        "execute",
        evidence["position_id"],
        SCOPE,
        "active",
        VERSION,
        evidence["subject"],
        "execute",
        evidence["position_id"],
        "discovered_attack",
        evidence["mapping_run_id"],
    )
