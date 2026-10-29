"""Gate one source-backed comparison and preserve coverage counts."""

from .deep_execution_views import deep_for_position
from .style_compare import candidates
from .style_history_lines import history_safe, lines_safe


def compare(db, learner, context, item, board):
    if board is None or board.fen() != context["pre_move_fen"]:
        return "history_unavailable", None, None, False, False
    deep = deep_for_position(db, context["position_id"], learner, board, context["played_move"])
    compared = candidates(board, context["played_move"], deep)
    status = compared["status"] if deep else item["status"]
    covered, completed = _coverage(deep, context["played_move"])
    if not history_safe(board):
        return "history_unsupported", compared, deep, covered, completed
    if status != "comparable":
        return status, compared, deep, covered, completed
    lines = [compared["played"], *(pair["alternative_line"] for pair in compared["pairs"])]
    if not lines_safe(board, lines):
        return "history_or_promotion_unsupported", compared, deep, covered, completed
    return status, compared, deep, covered, completed


def _coverage(deep, played):
    if not deep:
        return False, False
    result = deep.get("result")
    covered = bool(
        result and any(item["line"]["root_move"] == played for item in result["alternatives"])
    )
    return covered, deep["status"] == "complete"
