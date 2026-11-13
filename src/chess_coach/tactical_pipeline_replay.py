"""Reprocess superseded tactical provenance with a stable pipeline generation."""

import json

from .fact_fingerprint import canonical, digest
from .fact_runs import record_fact_run_in_transaction
from .mapping_invalidation import supersede_mapping
from .tactical_mapping import PRODUCER as MAPPER
from .tactical_mapping import SCOPE, _mapping_context, map_decision
from .tactical_report import MAPPER_VERSION

EMPTY_OUTPUT = digest(canonical([]))


def fact_run(db, context, producer, version, facts, generation):
    inputs = {"pre_move_fen": context["pre_move_fen"], "played_move": context["played_move"]}
    run = record_fact_run_in_transaction(
        db,
        position_id=context["position_id"],
        producer=producer,
        detector_version=version,
        input_data=inputs,
        facts=facts,
    )
    if run["status"] != "active" and generation is not None:
        run = record_fact_run_in_transaction(
            db,
            position_id=context["position_id"],
            producer=producer,
            detector_version=version,
            input_data={**inputs, "pipeline_generation": generation},
            facts=facts,
        )
    return run


def mapping_run(db, context, run, fact, ontology_version, generation):
    result = map_decision(db, context, run, fact, ontology_version)
    if result["mapping_status"] == "superseded" and generation is not None:
        result = map_decision(db, context, run, fact, ontology_version, generation)
    if generation is not None and result["mapping_status"] != "active":
        raise RuntimeError("tactical mapping is not current")
    return result


def retire_mapping(db, context, run, ontology_version, generation):
    """Keep an exact legacy empty scope; retire any other current scope."""
    row = db.connection.execute(
        """SELECT id,mapper_version,input_json,output_hash FROM mapping_runs_read
        WHERE producer=? AND position_id=? AND subject=? AND operation='execute'
        AND scope_key=? AND status='active'""",
        (MAPPER, context["position_id"], context["subject"], SCOPE),
    ).fetchone()
    if row is not None and not _same_empty(row, context, run, ontology_version, generation):
        supersede_mapping(db, row["id"])


def _same_empty(row, context, run, ontology_version, generation):
    # An old empty row is reusable only under the same mapper and empty result.
    if row["mapper_version"] != MAPPER_VERSION or row["output_hash"] != EMPTY_OUTPUT:
        return False
    try:
        data = json.loads(row["input_json"])
        # Generation-less legacy rows are reusable; another generation is not.
        prior_generation = data.pop("pipeline_generation", None)
        expected = {
            "context": _mapping_context(context, run, None, ontology_version, None),
            "assessment": None,
            "observation_at": context["observation_at"],
        }
        return prior_generation in (None, generation) and data == expected
    except (ValueError, TypeError, KeyError, AttributeError):
        return False
