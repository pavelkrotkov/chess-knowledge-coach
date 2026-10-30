"""Require an explicit public promotion line to match its horizon."""

import chess

from .objective_promotion_contract import FORCE, NOW


def validate(moves, objective):
    if objective == NOW and not _immediate(moves):
        raise ValueError("invalid immediate promotion line")
    if objective == FORCE and not _forced(moves):
        raise ValueError("invalid forced promotion line")


def _immediate(moves):
    return len(moves) == 1 and bool(chess.Move.from_uci(moves[0]).promotion)


def _forced(moves):
    if len(moves) not in {1, 3} or not chess.Move.from_uci(moves[-1]).promotion:
        return False
    return len(moves) == 1 or not chess.Move.from_uci(moves[0]).promotion
