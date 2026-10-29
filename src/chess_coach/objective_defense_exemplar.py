"""Select one source-proven defense and confirm the exact objective."""

import time

from .back_rank_practice_lines import lines
from .objective_defense_judge import judge


def choose(board, payload):
    choices = lines(board, payload, "prevent")
    if not choices:
        raise ValueError("defense exemplar unavailable")
    text = min(choices)
    move = board.parse_uci(text)
    if judge(board, move, time.monotonic, time.monotonic(), 5.0, {})["status"] != "correct":
        raise ValueError("defense exemplar unavailable")
    return text
