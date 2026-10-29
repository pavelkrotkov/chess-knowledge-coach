"""Drive synthetic pawn result outcomes for continuation tests."""

from chess_coach.objective_publication import cancel
from chess_coach.objective_worker import process
from tests.test_objective_pawn import SUBJECT


def finish_request(db, monkeypatch, outcome, move):
    from chess_coach import objective_pawn_judge

    if outcome == "cancel":
        assert cancel(db, SUBJECT, "pawn", "second")["reason"] == "cancelled"
        return "unresolved"
    else:
        low, high = {"correct": (1, 1), "incorrect": (0, 0), "unresolved": (0, 1)}[outcome]
        report = {
            "status": "complete",
            "lower": 1,
            "upper": 1,
            "nodes": 1,
            "alternatives": [{"move": {"uci": move}, "lower": low, "upper": high}],
        }
        monkeypatch.setattr(objective_pawn_judge, "inspect", lambda *args, **kwargs: report)
        assert process(db, SUBJECT)["outcomes"] == {outcome: 1}
        return outcome
