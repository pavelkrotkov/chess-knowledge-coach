"""Classify a bounded replay endpoint, including terminal checkmate."""

from .opening_check_response_event import event
from .style_history_lines import history_safe


def finish(board, rows, first, color, result):
    if board.is_checkmate():
        if result["status"] != "ended":
            raise ValueError("terminal history differs")
        if board.turn == color:
            result["events"].append(event(board, rows, len(rows) + 1, None))
        return
    if not history_safe(board):
        result["status"] = "unsupported"
    elif board.turn == color and board.is_check() and len(rows) >= first:
        result["unanswered"] = True
