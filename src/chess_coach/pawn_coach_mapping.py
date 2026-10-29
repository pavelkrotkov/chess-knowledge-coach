"""Map a verified pawn choice to an unreviewed scoped observation."""

from .mapping_runs import record_mapping_run_in_transaction
from .pawn_coach_contract import MAPPER, SCOPE, SKILL, VERSION


def operation(fact):
    return (
        "execute" if fact["root_wdl"] == 1 else "prevent" if fact["root_wdl"] == 0 else "evaluate"
    )


def mapping(db, prepared, run):
    fact = prepared["fact"]
    if fact is None:
        return None
    context, report = prepared["context"], prepared["report"]
    details = mapping_context(prepared)
    op = operation(fact)
    return record_mapping_run_in_transaction(
        db,
        position_id=report["position_id"],
        producer=MAPPER,
        mapper_version=VERSION,
        subject=context["subject"],
        operation=op,
        scope_key=SCOPE,
        input_data={"source": prepared["inputs"], "fact_run": run["run_id"], "context": details},
        mappings=[
            {
                "skill": SKILL,
                "outcome": fact["outcome"],
                "confidence": 0.5,
                "fact_ids": run["fact_ids"],
                "context": details,
                "observation_at": context["observation_at"],
            }
        ],
    )


def mapping_context(prepared):
    fact = prepared["fact"]
    context, report = prepared["context"], prepared["report"]
    return {
        "game_id": report["game_id"],
        "ply": report["ply"],
        "pre_move_fen": report["decision_fen"],
        "played_move": fact["played_uci"],
        "pawn_observation": fact,
        "source_fingerprint": report["source_fingerprint"],
        "time_control": context["time_control"],
        "clock_before_seconds": context["clock_before_seconds"],
        "clock_after_seconds": context["clock_after_seconds"],
    }
