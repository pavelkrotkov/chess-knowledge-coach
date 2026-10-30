"""Share one game-history replay between ordinary and purpose observations."""

from .style_history import selected_boards
from .style_observations import game_observations
from .style_purpose_evaluate import evaluate
from .style_purpose_prepare import required_ids
from .style_purpose_sources import sources
from .style_selection import selection


def collect_game(db, learner, game, budget, state):
    game_id = game["game_id"]
    selected = selection(db, game_id, learner)
    rows = state["grouped"].get(game_id, [])
    ids = required_ids(selected, rows)
    boards = selected_boards(db, game_id, ids)
    counts, allocations, ordinary = game_observations(
        db, learner, game, selected, budget, boards=boards
    )
    if selected is None:
        counts["games_without_selection"] += 1
    if not rows:
        return counts, allocations, ordinary
    game_sources = sources(db, game_id, learner, rows, boards)
    seen = {(item["game_id"], item["position_id"]) for item in ordinary}
    contexts = state["contexts"][game_id]
    for row in rows:
        evaluate(
            db,
            learner,
            row,
            contexts[row["position_id"]],
            game_sources.get(row["position_id"]),
            state,
            seen,
        )
    return counts, allocations, ordinary
