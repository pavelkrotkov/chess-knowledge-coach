"""Map a material fact to an unreviewed, scoped learner observation."""

from .mapping_runs import record_mapping_run_in_transaction
from .material_contract import SCOPE, VERSION
from .material_policy import MAPPER


def mapping(db, prepared, inputs, run, fact):
    if fact is None:
        return None
    context = prepared["context"]
    operation = "prevent" if fact["kind"] == "material_protection" else "execute"
    details = {
        "game_id": prepared["game_id"],
        "ply": context["ply"],
        "pre_move_fen": context["pre_move_fen"],
        "played_move": context["played_move"],
        "material_observation": fact,
        "provenance": prepared["provenance"],
        "qualification": "Provisional bounded observation; no intent or mastery inferred.",
    }
    item = {
        "skill": "hanging_piece",
        "outcome": fact["outcome"],
        "confidence": 0.5,
        "fact_ids": run["fact_ids"],
        "context": details,
        "observation_at": context["observation_at"],
    }
    return record_mapping_run_in_transaction(
        db,
        position_id=prepared["position_id"],
        producer=MAPPER,
        mapper_version=VERSION,
        subject=context["subject"],
        operation=operation,
        scope_key=SCOPE,
        input_data={
            "source": inputs,
            "fact_run": run["run_id"],
            "context": details,
            "observation_at": context["observation_at"],
        },
        mappings=[item],
    )
