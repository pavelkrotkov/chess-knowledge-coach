"""Read current same-decision comparisons and conditional center observations."""

from .opening_fit import _owned_scope
from .opening_fit_later_index import locate
from .opening_fit_later_owned import collect
from .opening_fit_later_public import samples
from .opening_profile_owned_control import control
from .opening_queue_view import statuses
from .style_time_candidates import verified
from .style_time_query import load_game


def comparisons(db, root, learner, decision, budget):
    return statuses(db, root, learner, decision, deadline=budget.expires, budget=budget)


def center(db, root, learner, decision, moves, nominal, budget):
    index = locate(root, learner, "recent")
    with budget.scope(snapshot=False):
        game = load_game(db.connection, decision["game_id"])
        if verified(game, learner) != decision["color"] or control(game) != nominal:
            raise ValueError("opening context changed")
    with _owned_scope(db, budget):
        owned = collect(db, learner, decision, moves)
    public = samples(index, decision, moves, nominal, budget, "recent")
    budget.check()
    if locate(root, learner, "recent") != index:
        raise ValueError("public opening source changed")
    return owned, public
