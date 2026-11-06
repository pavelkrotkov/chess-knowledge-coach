"""Compare only validated roots from one current, exact-depth MultiPV search."""

from .deep_execution_views import deep_for_position
from .opening_decision_line_safety import lines_safe
from .style_history_lines import history_safe
from .style_score import chosen


def comparison(db, learner, context, board, items):
    if not history_safe(board):
        return {"status": "history unavailable"}
    deep = deep_for_position(db, context["position_id"], learner, board, context["played_move"])
    if deep is None or deep["status"] != "complete":
        return {"status": "current analysis unavailable"}
    result = deep["result"]
    lines = [item["line"] for item in result["alternatives"]]
    played, _ = chosen(lines, context["played_move"])
    if played is None:
        return {"status": "played move not covered by an exact score"}
    attached = 0
    for item in items:
        attached += _attach(board, played, lines, item)
    if not attached:
        return {"status": "no catalog alternative has a qualified same-search comparison"}
    return {
        "status": "available",
        "engine": result["engine"],
        "engine_version": result["engine_version"],
        "limits": result["limits"],
        "run_id": result["run_id"],
    }


def _attach(board, played, lines, item):
    line, _ = chosen(lines, item["uci"])
    if line is None or line["depth"] != played["depth"] or not lines_safe(board, [played, line]):
        return 0
    item["analysis"] = {
        "played": played["score_value"],
        "alternative": line["score_value"],
        "depth": line["depth"],
        "line": line["san"],
    }
    return 1
