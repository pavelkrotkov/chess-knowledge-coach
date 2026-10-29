"""Chronology-safe exact-position familiarity in a bounded sample."""

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
    known = _known_positions(contexts)
    for context in contexts:
        when = context["observation_at"]
        prior = {
            game
            for date, game in known[_key(context)]
            if when and date < when and game != context["game_id"]
        }
        context["prior_observed_games"] = len(prior) if when else None
        context["familiarity"] = _familiarity_bucket(prior, when, incomplete)


def _familiarity_bucket(prior, when, incomplete):
    if not when or incomplete:
        return "unknown"
    if len(prior) == 0:
        return "no prior observed game"
    return "1-2 prior observed games" if len(prior) < 3 else "3+ prior observed games"
