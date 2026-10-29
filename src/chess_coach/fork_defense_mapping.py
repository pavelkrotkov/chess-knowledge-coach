"""Map a fork-defense fact to an unreviewed, closed-family observation."""

from .fork_defense_contract import MAPPER, SCOPE, VERSION
from .mapping_runs import record_mapping_run_in_transaction


def mapping(db, prepared, inputs, run, fact):
    if fact is None:
        return None
    context = prepared["context"]
    details = {
        "game_id": prepared["game_id"],
        "ply": context["ply"],
        "pre_move_fen": context["pre_move_fen"],
        "played_move": context["played_move"],
        "fork_defense_observation": fact,
        "provenance": prepared["provenance"],
        "qualification": "Provisional bounded observation; no intent or mastery inferred.",
    }
    item = {
        "skill": "fork",
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
        operation="prevent",
        scope_key=SCOPE,
        input_data={
            "source": inputs,
            "fact_run": run["run_id"],
            "context": details,
            "observation_at": context["observation_at"],
        },
        mappings=[item],
    )
