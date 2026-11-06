"""Recheck a stored score pair and its complete legal variations."""

from .opening_decision_line_safety import lines_safe
from .opening_queue_line import line
from .purpose_config import FINAL_NODES
from .style_score import score_ok


def complete(outcome, source, board):
    lines = outcome.get("lines")
    if outcome.get("status") != "complete" or not _work(outcome.get("work")):
        return False
    if not _pair(lines, source):
        return False
    return all(line(item, board) for item in lines) and lines_safe(board, lines)


def _work(work):
    if not isinstance(work, dict) or type(work.get("nodes")) is not int:
        return False
    return 0 <= work["nodes"] <= FINAL_NODES and work.get("node_limit_exceeded") is False


def _pair(lines, source):
    if not isinstance(lines, list) or len(lines) != 2:
        return False
    if not all(isinstance(line, dict) and score_ok(line) for line in lines):
        return False
    if lines[0]["depth"] != lines[1]["depth"]:
        return False
    return {line.get("root_move") for line in lines} == {source["played"], source["alternative"]}
