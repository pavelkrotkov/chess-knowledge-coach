"""Derive the existing game identity from bounded advisory rows."""

import chess

from .learner_identity import normalize_identity
from .learner_time import observation_time
from .mastery_game_identity import game_identity
from .mastery_position import position_key
from .style_schedule_clock import reached
from .style_schedule_early_priority import pair


def identity(db, game, rows):
    started = observation_time(game["pgn"])
    white, black = normalize_identity(game["white"]), normalize_identity(game["black"])
    if not all((started, white, black, white != black)):
        return None
    decisions = []
    for row in rows:
        if reached():
            raise ValueError("incomplete position metadata")
        move = chess.Move.from_uci(row[3])
        if move.uci() != row[3]:
            raise ValueError("invalid position metadata")
        decisions.append({"played_move": row[3]})
    decisions[0].update(prompt_fen=position_key(chess.Board()), observation_at=started)
    return game_identity(db, game["id"], decisions)


def reserve(ordered, nominations, identities, reserved):
    if not reserved:
        return ordered, False
    if identities is not None:
        identities.update({ordered[index][0]["id"]: key for index, _, _, _, key in nominations})
    prioritized = pair(ordered, nominations)
    return (prioritized, True) if prioritized else (ordered, False)
