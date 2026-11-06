"""Verify a nominated opening decision and independent game identity."""

from .mastery_game_lookup import decisions_for_game
from .opening_decision_budget import classification
from .opening_decision_catalog import catalog
from .opening_decision_source import _history
from .opening_explore_guard import require_bounded
from .opening_storage import position_key
from .style_history_lines import history_safe


def verify(db, learner, key, candidate, budget, cache):
    game_id, position_id = candidate["game_id"], candidate["position_id"]
    if game_id not in cache:
        with budget.scope(snapshot=True):
            require_bounded(db, game_id)
            opening = classification(db, game_id)
        with budget.scope(snapshot=True):
            require_bounded(db, game_id)
            identities = decisions_for_game(db, game_id, learner)
        cache[game_id] = opening, identities
    opening, identities = cache[game_id]
    if not identities or position_id not in identities:
        raise ValueError("game identity unavailable")
    with budget.scope(snapshot=True):
        require_bounded(db, game_id)
        context, board = _history(db, game_id, position_id, learner, opening)
        if not history_safe(board) or (context["learner_color"], position_key(board)) != key:
            raise ValueError("opening decision differs")
        identity = identities[position_id]
        if (
            identity["pre_move_fen"] != board.fen()
            or identity["played_move"] != context["played_move"]
        ):
            raise ValueError("game history differs")
        played = board.parse_uci(context["played_move"])
        choices = catalog(db, opening["dataset_id"], board, context["played_move"])
    return {
        **candidate,
        "game_key": identity["game_key"],
        "played": board.san(played),
        "played_uci": context["played_move"],
        "catalog": choices,
    }
