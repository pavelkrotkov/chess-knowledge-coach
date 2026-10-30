"""Share one game-history replay between ordinary and purpose observations."""

from .preview_snapshot import preview_history
from .style_observations import game_observations
from .style_protection_purpose_evaluate import evaluate as evaluate_protection
from .style_purpose_evaluate import evaluate
from .style_purpose_prepare import required_ids
from .style_purpose_sources import sources
from .style_report_history import boards as game_boards
from .style_selection import selection


def collect_game(db, learner, game, budget, state):
    game_id = game["game_id"]
    selected = selection(db, game_id, learner)
    rows = state["grouped"].get(game_id, [])
    ids = required_ids(selected, rows)
    ids &= {context["position_id"] for context in game["contexts"]}
    with preview_history(db, learner) as history:
        boards = game_boards(db, game_id, ids, history)
        return _collect(db, learner, game, selected, rows, boards, budget, state, history)


def _collect(db, learner, game, selected, rows, boards, budget, state, history):
    game_id = game["game_id"]
    counts, allocations, ordinary = game_observations(
        db, learner, game, selected, budget, boards=boards, history=history
    )
    if selected is None:
        counts["games_without_selection"] += 1
    if not rows:
        return counts, allocations, ordinary
    game_sources = sources(db, game_id, learner, rows, boards)
    ordinary_by_id = {(item["game_id"], item["position_id"]): item for item in ordinary}
    seen = set(ordinary_by_id)
    contexts = state["contexts"][game_id]
    for row in rows:
        context = contexts[row["position_id"]]
        source = game_sources.get(row["position_id"])
        if row["kind"] == "protection":
            evaluate_protection(
                db,
                learner,
                row,
                context,
                source,
                state,
                ordinary_by_id,
                budget["protection"],
                history,
            )
        else:
            evaluate(db, learner, row, context, source, state, seen)
    return counts, allocations, ordinary
