"""Recheck displayed deep results instead of trusting a stale completion flag."""

from .deep_execution_view_alternatives import alternatives_present


def result_is_presentable(result, board):
    if result is None:
        return False
    try:
        minimum = result["limits"]["min_depth"]
        alternatives = result["alternatives"]
        if not alternatives_present(result, board):
            return False
        lines = [result["best"], result["played"], *(item["line"] for item in alternatives)]
        if any(not _line_ok(line, minimum) for line in lines):
            return False
        return _work_ok(result["best_work"]) and _work_ok(result["played_work"])
    except (KeyError, TypeError, ValueError):
        return False


def _line_ok(line, minimum):
    return (
        line is not None
        and line["status"] == "limited"
        and line["score_bound"] == "exact"
        and type(line["score_value"]) is int
        and type(line["depth"]) is int
        and type(minimum) is int
        and line["depth"] >= minimum
    )


def _work_ok(work):
    return isinstance(work, dict) and type(work.get("nodes")) is int and work["nodes"] > 0
