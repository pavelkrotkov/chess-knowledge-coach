"""Check direct prompts and declared line objectives without inventing setup moves."""

import chess

from .public_training_line import validate_line


def validate_task(task):
    task_id, fen, objective, lines = (task.get(key) for key in ("id", "fen", "objective", "lines"))
    _task_id(task_id)
    if objective not in {"legal_line", "checkmate", "promotion"}:
        raise ValueError("unsupported objective")
    if not isinstance(lines, list) or not 1 <= len(lines) <= 16:
        raise ValueError("invalid solution lines")
    board = chess.Board(fen)
    if not board.is_valid():
        raise ValueError("invalid prompt position")
    normalized = [validate_line(board, line, objective) for line in lines]
    if len(set(normalized)) != len(normalized):
        raise ValueError("duplicate solution line")
    return {"id": task_id, "fen": board.fen(), "objective": objective, "lines": normalized}


def _task_id(task_id):
    if not isinstance(task_id, str) or not task_id.strip() or len(task_id) > 256:
        raise ValueError("invalid task identifier")
