"""Validate and normalize ranked native engine continuations."""

from .analysis_comparison import comparison_line


def alternatives(position, board, lines):
    result, bad = [], False
    for rank, raw in enumerate(lines, 1):
        item, invalid = line(position, board, "best", raw)
        bad |= invalid
        if item is not None:
            result.append({"rank": rank, "line": item})
    return result, bad


def line(position, board, role, line):
    try:
        return comparison_line(position, board, role, line), False
    except (ValueError, TypeError, AttributeError):
        return None, True


def first(alternatives, position, board):
    for item in alternatives:
        if item["rank"] == 1:
            return item["line"]
    return comparison_line(position, board, "best", {})


def problem(best_error, played_error, bad, played_bad):
    if best_error:
        return best_error
    if played_error:
        return played_error
    if bad or played_bad:
        return "invalid_line"
    return None
