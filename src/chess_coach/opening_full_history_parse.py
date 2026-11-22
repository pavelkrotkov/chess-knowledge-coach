"""Retain admitted public histories and count unvalidated over-limit records."""

from .opening_recent_context import record as recent_record
from .opening_reference_play import MAX_GAME_PLIES


def parser(check, rejected):
    def parse(game, raw, number):
        check()
        moves = []
        for move in game.mainline_moves():
            moves.append(move.uci())
            if len(moves) > MAX_GAME_PLIES:
                rejected[0] += 1
                return None
        result = recent_record(game, raw, number, check=check)
        check()
        return (*result, moves) if result is not None else None

    return parse
