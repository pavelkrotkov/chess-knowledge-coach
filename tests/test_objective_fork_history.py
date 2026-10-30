"""Owned fork proof replays the actual pre-decision move history."""

from chess_coach.objective_current import current
from chess_coach.objective_history import before_answer
from chess_coach.objective_worker import process
from chess_coach.unified_session_events import hint, submit
from tests.objective_fork_support import SUBJECT, begin, owned_fork


def test_nonempty_source_history_and_assisted_event_prefix(tmp_path, monkeypatch):
    db, evidence = owned_fork(tmp_path / "history.sqlite", monkeypatch, "f6g5", with_history=True)
    begin(db, evidence)
    hint(db, "fork", SUBJECT, event_id="hint")
    submit(db, "fork", SUBJECT, event_id="answer", move="b5d6")
    request = db.connection.execute("SELECT * FROM objective_requests").fetchone()
    session, events = current(db, request)
    board, move = before_answer(db, session, events)
    assert [item.uci() for item in board.move_stack] == ["d7e8"]
    assert board.halfmove_clock == 1 and move.uci() == "b5d6"
    assert process(db, SUBJECT)["outcomes"] == {"correct": 1}
    import json

    result = json.loads(
        db.connection.execute("SELECT result_json FROM objective_results").fetchone()[0]
    )
    assert result["assistance"] == "hinted" and result["learning_eligible"] is False
