"""Map active detector facts without altering other producers' evidence."""

import json

from .db import Database
from .mapping_runs import record_mapping_run_in_transaction
from .mapping_transaction import mapping_transaction
from .ontology_scopes import previous_scopes

FACT_OPERATIONS = {"fork": "execute", "hanging_piece": "prevent", "absolute_pin": "recognize"}


def map_facts(db: Database, mapper_version: str, *, detector_version: str | None) -> list[dict]:
    with mapping_transaction(db):
        rows = _source_rows(db, detector_version)
        groups = _groups(rows, mapper_version, detector_version)
        previous_scopes(db, detector_version, groups)
        for (position_id, operation, scope_key), items in groups.items():
            _record_group(db, position_id, operation, scope_key, mapper_version, items)
    return [item["report"] for items in groups.values() for item in items]


def _source_rows(db: Database, version: str | None):
    return db.connection.execute(
        """SELECT f.* FROM detector_facts f
        LEFT JOIN detector_runs r ON r.id = f.run_id
        WHERE (f.run_id IS NULL OR r.status = 'active') AND f.position_id IS NOT NULL
        AND (? IS NULL OR f.detector_version = ?) ORDER BY f.id""",
        (version, version),
    ).fetchall()


def _groups(rows, mapper_version: str, detector_version: str | None) -> dict:
    groups = {}
    for row in rows:
        skill = row["fact_type"]
        if skill not in FACT_OPERATIONS:
            continue
        operation = FACT_OPERATIONS[skill]
        report = {
            "position_id": row["position_id"],
            "skill": skill,
            "operation": operation,
            "confidence": 1.0,
            "source_facts": [row["id"]],
            "detector_version": row["detector_version"],
            "mapper_version": mapper_version,
            "payload": json.loads(row["payload_json"]),
        }
        mapping = {
            "skill": skill,
            "outcome": "ambiguous",
            "confidence": 1.0,
            "fact_ids": [row["id"]],
            "context": {},
            "observation_at": None,
        }
        scope = json.dumps(
            {"detector_version": detector_version, "fact_id": row["id"]}, sort_keys=True
        )
        groups[(row["position_id"], operation, scope)] = [{"report": report, "mapping": mapping}]
    return groups


def _record_group(
    db: Database,
    position_id: int,
    operation: str,
    scope_key: str,
    mapper_version: str,
    items: list[dict],
) -> None:
    ids = sorted(item["report"]["source_facts"][0] for item in items)
    record_mapping_run_in_transaction(
        db,
        position_id=position_id,
        producer="ontology",
        mapper_version=mapper_version,
        subject="unassigned",
        operation=operation,
        scope_key=scope_key,
        input_data={"source_fact_ids": ids},
        mappings=[item["mapping"] for item in items],
    )
