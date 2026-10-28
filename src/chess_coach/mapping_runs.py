"""Immutable, scoped mapping runs composable in a caller-owned transaction."""

from .db import Database
from .fact_fingerprint import canonical, digest
from .mapping_inputs import mapping_batch
from .mapping_run_storage import append_run
from .mapping_storage import validate_sources


def record_mapping_run_in_transaction(
    db: Database,
    *,
    position_id: int,
    producer: str,
    mapper_version: str,
    subject: str,
    operation: str,
    scope_key: str,
    input_data: dict,
    mappings: list[dict],
) -> dict:
    """Validate and append a mapping run without committing the caller transaction."""
    if not db.connection.in_transaction:
        raise RuntimeError("mapping output requires a transaction")
    for value in (producer, mapper_version, subject, operation, scope_key):
        if not isinstance(value, str) or not value.strip():
            raise ValueError("mapping scope and version must be nonempty strings")
    if not isinstance(input_data, dict):
        raise ValueError("mapping input must be an object")
    items, output_hash = mapping_batch(mappings)
    input_json = canonical(input_data)
    scope = (producer, position_id, subject, operation, scope_key)
    prior = db.connection.execute(
        """SELECT * FROM mapping_runs WHERE producer = ? AND position_id = ?
        AND subject = ? AND operation = ? AND scope_key = ?
        AND mapper_version = ? AND input_hash = ?""",
        (*scope, mapper_version, digest(input_json)),
    ).fetchone()
    if prior is not None:
        return _replay(db, prior, input_json, output_hash)
    validate_sources(db, position_id, items)
    return append_run(db, scope, mapper_version, input_json, output_hash, items)


def _replay(db: Database, prior, input_json: str, output_hash: str) -> dict:
    if prior["input_json"] != input_json or prior["output_hash"] != output_hash:
        raise ValueError("mapping input/version already has different output")
    ids = [
        row["id"]
        for row in db.connection.execute(
            "SELECT id FROM evidence_mappings WHERE mapping_run_id = ? ORDER BY id", (prior["id"],)
        )
    ]
    return {"run_id": prior["id"], "evidence_ids": ids, "status": prior["status"], "replayed": True}
