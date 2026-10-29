"""Admit only an explicitly sourced task with an independently proved exemplar."""

import time

import chess

from .objective_promotion_contract import OBJECTIVES
from .objective_promotion_judge import judge


def admit(snapshot):
    if snapshot["objective"] not in OBJECTIVES:
        return
    board = chess.Board(snapshot["prompt_fen"])
    move = board.parse_uci(snapshot["lines"][0].split()[0])
    start = time.monotonic()
    result = judge(board, move, snapshot["objective"], time.monotonic, start, 5.0, {})
    if result["status"] != "correct":
        raise ValueError("promotion exemplar unavailable")
