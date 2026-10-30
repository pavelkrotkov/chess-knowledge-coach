"""Describe a qualified purpose comparison in the check-response family only."""

from .style_compare import candidates
from .style_context import describe_context
from .style_defense_choices import NAMES, annotate, classify
from .style_dimensions import dimensions
from .style_history_lines import lines_safe
from .style_opening import current_opening
from .style_purpose_validate import matches_context


def observation(db, context, slot, snapshot, view):
    board = snapshot["board"]
    if not matches_context(snapshot, context):
        return "history_unavailable", None
    if not board.is_check():
        return "outside_check", None
    if board.legal_moves.count() <= 1:
        return "forced_move", None
    attempt = view["attempts"][-1]
    final = attempt["final"]
    alternatives = [{"rank": item["rank"], "line": item} for item in final["lines"]]
    compared = candidates(
        board,
        context["played_move"],
        {"status": "complete", "result": {"alternatives": alternatives}},
    )
    if compared["status"] != "comparable":
        return compared["status"], None
    lines = [compared["played"], *(pair["alternative_line"] for pair in compared["pairs"])]
    if not lines_safe(board, lines):
        return "history_or_promotion_unsupported", None
    annotate(board, compared)
    choices = dimensions([])
    choices.update(classify(compared["pairs"][0]))
    return "comparable", {
        "game_id": context["game_id"],
        "position_id": context["position_id"],
        "ply": context["ply"],
        "played_move": context["played_move"],
        "game_outcome": context["game_outcome"],
        "context": describe_context(db, context, current_opening(db, context["game_id"])),
        "allocation": "purpose_" + slot["kind"],
        "provenance": "purpose_candidate_set",
        "request_id": slot["request_id"],
        "attempt_number": attempt["number"],
        "cycle": slot["sequence"],
        "eligible_dimensions": list(NAMES),
        "choices": choices,
        "pairs": compared["pairs"],
        "played_line": compared["played"],
        "limits": view["limits"],
        "legal_roots": board.legal_moves.count(),
        "ranked_roots": len(alternatives),
    }
