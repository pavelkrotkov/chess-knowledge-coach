"""Match the same proved protection action, not just the same piece roles."""

import chess
import pytest

from chess_coach.related_protection_features import protection_features
from chess_coach.related_protection_match import scorer
from tests.test_objective_protection import oriented


@pytest.mark.parametrize("black", [False, True])
@pytest.mark.parametrize(
    ("source_move", "other_move"),
    [("d4d3", "a5c5"), ("a5c5", "d4d3")],
)
def test_transfer_requires_same_proved_defense_mechanism(black, source_move, other_move):
    board = chess.Board("4k3/8/8/R1b5/3R4/8/P7/7K w - - 0 1")
    if black:
        board = board.mirror()
    source = protection_features(board.fen(), [oriented(source_move, black)])
    other = protection_features(board.fen(), [oriented(other_move, black)])
    assert source is not None and other is not None
    assert (source["mover"], source["target"]) == (other["mover"], other["target"])
    assert source["mechanism"] != other["mechanism"]

    item = {
        "type": "public",
        "version": "fixture",
        "key": "defense",
        "fen": board.fen(),
        "lines": [oriented(other_move, black)],
    }
    budget = {"checked": 0, "limit": 2, "truncated": False}
    score = scorer(budget)
    assert score(item, source, set(), 1200) is None
    item["lines"] = [oriented(source_move, black)]
    accepted = score(item, source, set(), 1200)
    assert accepted is not None and accepted["matching_line_indices"] == [0]
    assert budget["checked"] == 2
