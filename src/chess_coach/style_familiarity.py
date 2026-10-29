"""Keep familiarity unknown when only game-start timestamps are available."""

from collections import defaultdict

import chess

from .opening_storage import position_key


def _key(context):
    return context["learner_color"], position_key(chess.Board(context["pre_move_fen"]))


def _known_positions(contexts):
    known = defaultdict(set)
    for context in contexts:
        if context["observation_at"]:
            known[_key(context)].add((context["observation_at"], context["game_id"]))
    return known


def familiarity(contexts, incomplete):
    """Count earlier game starts only; those positions may have occurred later."""
    known = _known_positions(contexts)
    for context in contexts:
        when = context["observation_at"]
        earlier = {
            game
            for date, game in known[_key(context)]
            if when and date < when and game != context["game_id"]
        }
        context["earlier_started_games_with_position"] = (
            len(earlier) if when and not incomplete else None
        )
        context["familiarity"] = "unknown"
