"""Present safe material objective and lineage fields."""

from .material_policy import fact_allowed


def build_view(evidence, fact, source):
    payload = fact["payload"]
    context = evidence["context"]
    return {
        "subject": evidence["subject"],
        "position_id": evidence["position_id"],
        "game_id": evidence["game_id"],
        "ply": evidence["ply"],
        "decision_fen": context.get("pre_move_fen"),
        "learner_color": None,
        "objective": {
            "kind": payload.get("kind"),
            "target": payload.get("target"),
            "target_piece": payload.get("target_piece"),
        },
        "outcome": evidence["outcome"],
        "review_status": evidence["review_status"],
        "currentness": "stale",
        "witness_lines": {"best": payload.get("best"), "played": payload.get("played")},
        "objective_witness": None,
        "eligible_for_exercise_candidate": False,
        "exercise_qualification": "unavailable",
        "family_validated": fact_allowed(
            fact,
            skill=evidence["skill"],
            operation=evidence["operation"],
            outcome=evidence["outcome"],
        ),
        "source_fingerprint": source.get("source_marker"),
        "lineage": {
            "fact_id": fact["id"],
            "detector_run_id": fact["detector_run_id"],
            "detector_version": fact["detector_version"],
            "mapping_run_id": evidence["mapping_run_id"],
            "analysis": source.get("provenance"),
        },
    }
