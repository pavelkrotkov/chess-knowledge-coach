"""Recheck one exact owned later-opening branch and game identity."""

import chess

from .mastery_game_lookup import decisions_for_game
from .opening_storage import position_key
from .style_time_candidates import verified
from .style_time_query import load_game


def branch(db, learner, decision, game_id):
    game = load_game(db.connection, game_id)
    if verified(game, learner) != decision["color"]:
        return None
    contexts = decisions_for_game(db, game_id, learner)
    if not contexts:
        return None
    for context in contexts.values():
        if context["ply"] != decision["ply"] or not context["subject"]:
            continue
        if position_key(chess.Board(context["pre_move_fen"])) != decision["catalog"]["parent"]:
            return None
        return context["played_move"], context["game_key"], game
    return None
