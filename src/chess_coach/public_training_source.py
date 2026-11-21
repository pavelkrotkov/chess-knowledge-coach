"""Resolve a licensed immutable public task into a practice snapshot."""

import json

from .objective_promotion_source import decorate
from .public_mate_contract import BINDING, OBJECTIVE
from .public_training_license import validate_manifest
from .public_training_query import task as public_task
from .public_training_validate import validate_task


def resolve(db, version, key, *, verify=True):
    from .unified_sources import _snapshot

    row = public_task(db, version, key)
    if row is None:
        raise ValueError("practice source is unavailable")
    candidate = {
        "id": key,
        "fen": row["prompt_fen"],
        "objective": row["objective"],
        "lines": row["lines"],
    }
    if verify:
        candidate = validate_task(candidate)
    fields = (
        "source_url",
        "source_revision",
        "source_sha256",
        "content_sha256",
        "license",
        "attribution",
        "license_notice",
    )
    provenance = {field: row[field] for field in fields}
    provenance.update(_binding(db, row))
    decorate(provenance, row, candidate, version, key)
    return _snapshot(candidate["fen"], candidate["objective"], candidate["lines"], provenance)


def _binding(db, row):
    if row["objective"] != OBJECTIVE:
        return {}
    fields = (
        "version",
        "source_url",
        "source_revision",
        "source_sha256",
        "content_sha256",
        "license",
        "attribution",
        "license_notice",
    )
    content_format = db.connection.execute(
        "SELECT content_format FROM public_collections WHERE version=? AND state='ready'",
        (row["version"],),
    ).fetchone()
    if content_format is None:
        raise ValueError("public mate collection unavailable")
    validate_manifest(
        {field: row[field] for field in fields} | {"content_format": content_format[0]}
    )
    return {"public_mate": dict(BINDING)}


def mate(row):
    from .unified_public_outcome import direct

    return (
        row["source_type"] == "public"
        and row["objective"] == OBJECTIVE
        and json.loads(row["provenance_json"]).get("public_mate") == BINDING
        and direct(row)
    )
