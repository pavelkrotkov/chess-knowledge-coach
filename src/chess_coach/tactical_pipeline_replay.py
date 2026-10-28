"""Reprocess superseded tactical provenance with a stable pipeline generation."""

from .fact_runs import record_fact_run_in_transaction
from .tactical_mapping import map_decision


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
