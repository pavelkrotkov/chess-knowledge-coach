"""Bind one catalog selection to a current owned opening decision."""

from . import opening_decision_budget
from .opening_decision_catalog import catalog
from .opening_decision_source import source as opening_source
from .purpose_source import source as owned_source


def selection(db, game_id, position_id, learner, alternative):
    opening, context, board = opening_source(db, game_id, position_id, learner)
    owned = owned_source(db, position_id, learner)
    if owned["game_id"] != game_id or owned["board"].fen() != board.fen():
        raise ValueError("opening decision history differs")
    played = context["played_move"]
    if played != owned["position"]["uci"]:
        raise ValueError("opening decision move differs")
    choices = catalog(db, opening["dataset_id"], board, played)
    choice = next((item for item in choices["items"] if item["uci"] == alternative), None)
    if choice is None:
        raise ValueError("catalog alternative unavailable")
    binding = {
        "game_id": game_id,
        "position_id": position_id,
        "learner_key": owned["learner_key"],
        "history_fingerprint": owned["fingerprint"],
        "decision_fen": board.fen(),
        "played": played,
        "alternative": alternative,
        "parent": choices["parent"],
        "child": choice["child"],
        "graph_sha256": opening_decision_budget.GRAPH_SHA256,
        "graph_version": opening["version"],
        "graph_source": opening["source_url"],
        "classifier_version": opening["classifier_version"],
        "content_revision": opening["content_revision"],
    }
    return binding, owned
