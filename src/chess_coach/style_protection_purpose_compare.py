"""Validate the stored final candidate set for a protection observation."""

from .style_compare import candidates
from .style_history_lines import history_safe, lines_safe
from .style_purpose_validate import matches_context


def comparison(context, snapshot, view):
    board = snapshot["board"]
    if not _history_valid(snapshot, context):
        return "history_unavailable", None
    if board.is_check():
        return "outside_protection_scope", None
    if board.legal_moves.count() <= 1:
        return "forced_move", None
    final = view["attempts"][-1]["final"]
    alternatives = [{"rank": item["rank"], "line": item} for item in final["lines"]]
    result = candidates(
        board,
        context["played_move"],
        {"status": "complete", "result": {"alternatives": alternatives}},
    )
    if result["status"] != "comparable":
        return result["status"], None
    lines = [result["played"], *(pair["alternative_line"] for pair in result["pairs"])]
    if not lines_safe(board, lines):
        return "history_or_promotion_unsupported", None
    return "current", result


def _history_valid(snapshot, context):
    return matches_context(snapshot, context) and history_safe(snapshot["board"])
