"""Describe only independently proved protection contrasts."""

from .style_context import describe_context
from .style_dimensions import dimensions
from .style_opening import current_opening
from .style_protection_choices import NAMES
from .style_protection_purpose_compare import comparison
from .style_protection_purpose_source import inspect
from .style_protection_schedule_status_fields import provenance


def observation(db, learner, context, slot, snapshot, view, budget, history):
    state, compared = comparison(context, snapshot, view)
    if compared is None:
        return state, None, False
    before = budget["skipped"]
    budget["considered"] += 1
    proofs, state = inspect(
        db, learner, context, snapshot["board"], compared, slot, budget, history
    )
    if budget["skipped"] > before:
        budget["skipped_decisions"] += 1
    if not proofs or any(item["status"] != "supported" for item in proofs.values()):
        budget["unsupported"] += 1
        return state if state != "current" else "unsupported", None, state == "current"
    budget["completed"] += 1
    for pair in compared["pairs"]:
        pair["played"]["protection"] = proofs[compared["played"]["root_move"]]
        pair["alternative"]["protection"] = proofs[pair["alternative_line"]["root_move"]]
    return "comparable", _item(db, context, slot, snapshot, view, compared), True


def _item(db, context, slot, snapshot, view, compared):
    return {
        "game_id": context["game_id"],
        "position_id": context["position_id"],
        "ply": context["ply"],
        "played_move": context["played_move"],
        "game_outcome": context["game_outcome"],
        "context": describe_context(db, context, current_opening(db, context["game_id"])),
        "allocation": "purpose_protection",
        "provenance": "purpose_candidate_set_and_original_proof",
        "request_id": slot["request_id"],
        "attempt_number": view["attempts"][-1]["number"],
        "cycle": slot["sequence"],
        "original_protection": provenance(slot),
        "purpose_policy": view["policy"],
        "eligible_dimensions": list(NAMES),
        "choices": dimensions(compared["pairs"]),
        "pairs": compared["pairs"],
        "played_line": compared["played"],
        "limits": view["limits"],
        "legal_roots": snapshot["board"].legal_moves.count(),
        "ranked_roots": len(view["attempts"][-1]["final"]["lines"]),
    }
