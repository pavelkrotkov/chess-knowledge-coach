"""Qualify exact comparable scores for two selected opening roots."""

from .opening_decision_line_safety import lines_safe
from .purpose_lines import native, roots, valid_pair, viewed
from .style_score import score_ok


def grade(board, position, requested, raw, error):
    if error:
        return None, error
    if any(len(line.get("pv") or []) > 100 for line in raw):
        return None, "invalid_candidate_search"
    items, invalid = native(position, board, raw)
    if invalid:
        return None, "invalid_candidate_search"
    return selected(board, position, requested, items)


def selected(board, position, requested, items):
    if not valid_pair(items) or set(roots(items)) != set(requested):
        return None, "invalid_candidate_search"
    lines = [item["line"] for item in viewed(items, board, position["uci"])]
    return _qualify(board, lines)


def _qualify(board, lines):
    if not all(score_ok(line) for line in lines):
        return None, "exact_scores_unavailable"
    if lines[0]["depth"] != lines[1]["depth"] or not lines_safe(board, lines):
        return None, "incomparable_depth_or_history"
    return lines, None
