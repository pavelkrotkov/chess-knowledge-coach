"""Compare same-position native score kinds after independent validation."""

from .decision_line_view import view_line
from .deep_execution_drift import score_drift


def compare_scores(cheap, result, board, played):
    if set(cheap) != {"best", "played"}:
        return False, False
    for role in ("best", "played"):
        deep = view_line(result[role], board, played)
        if not _role_comparable(cheap[role], deep):
            return False, False
    return True, any(score_drift(cheap[role], result[role]) for role in ("best", "played"))


def _role_comparable(old, deep):
    return (
        old["status"] == "limited"
        and deep["status"] == "limited"
        and old["score_bound"] == "exact"
        and deep["score_bound"] == "exact"
        and old["score_kind"] == deep["score_kind"]
        and type(old["score_value"]) is int
        and type(deep["score_value"]) is int
    )


def usable_line(line, board, played, min_depth):
    view = view_line(line, board, played)
    return (
        view["status"] == "limited"
        and line["score_bound"] == "exact"
        and type(line["depth"]) is int
        and line["depth"] >= min_depth
        and type(line["score_value"]) is int
    )
