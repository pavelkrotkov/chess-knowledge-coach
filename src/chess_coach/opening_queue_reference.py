"""Recheck a bounded, source-bound all-legal-root opening measurement."""

from .deep_execution_work import _valid
from .opening_decision_line_safety import lines_safe
from .opening_queue_line import line
from .purpose_config import FINAL_SECONDS
from .style_score import score_ok


def complete(outcome, lines, source, board):
    if outcome.get("policy") != "all-legal-roots-v2" or not isinstance(lines, list):
        return False
    roots = {move.uci() for move in board.legal_moves}
    if not _coverage(outcome, lines, roots, source):
        return False
    return _qualified(outcome, lines, roots, board)


def _coverage(outcome, lines, roots, source):
    # A comparable reference requires every legal root, not merely a sample.
    return (
        _all_roots(outcome, lines, roots)
        and {
            source["played"],
            source["alternative"],
        }
        <= roots
    )


def _all_roots(outcome, lines, roots):
    return (
        all(isinstance(item, dict) and score_ok(item) for item in lines)
        and _count(outcome, lines, roots)
        and {item.get("root_move") for item in lines} == roots
    )


def public(outcome, selected, board):
    from .opening_queue_proof import _work as bounded_work

    lines = outcome.get("lines")
    if outcome.get("status") != "complete" or not bounded_work(outcome.get("work")):
        return False
    if outcome.get("policy") != "all-legal-roots-v2" or not isinstance(lines, list):
        return False
    roots = {move.uci() for move in board.legal_moves}
    return (
        selected in roots
        and _all_roots(outcome, lines, roots)
        and _qualified(outcome, lines, roots, board)
    )


def _qualified(outcome, lines, roots, board):
    return _scores(outcome, lines) and _work(outcome, len(roots)) and _safe(lines, board)


def _count(outcome, lines, roots):
    count = len(roots)
    return (
        count >= 2
        and len(lines) == count
        and outcome.get("effective_multipv") == count
        and [item.get("rank") for item in lines] == list(range(1, count + 1))
    )


def _safe(lines, board):
    # Replaying each compact PV prefix retains the original history checks.
    return all(line(item, board) for item in lines) and lines_safe(board, lines)


def _scores(outcome, lines):
    # Only one exact common depth supports a meaningful score comparison.
    if len({item["depth"] for item in lines}) != 1:
        return False
    if lines[0]["depth"] != outcome.get("retained_depth"):
        return False
    return lines[0]["score_value"] == max(item["score_value"] for item in lines)


def _work(outcome, count):
    # The persisted limits describe the entire shared native search.
    maximum, seconds = outcome.get("multipv_max"), outcome["work"].get("time_seconds")
    return (
        type(maximum) is int
        and maximum >= count
        and _valid(seconds, False)
        and seconds <= FINAL_SECONDS
    )
