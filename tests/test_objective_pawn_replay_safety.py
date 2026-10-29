"""Reject changed pawn moves and training replies when replaying proof."""

import copy
import json

import pytest

from chess_coach.objective_current import current
from chess_coach.objective_pawn_history import before_answer
from chess_coach.objective_pawn_play import play
from chess_coach.objective_worker import process
from chess_coach.unified_session_events import submit
from tests.test_objective_pawn import SUBJECT, begin, setup_game


@pytest.mark.parametrize("field", ["move", "answer_fen", "reply", "reply_fen", "reply_history"])
def test_pawn_replay_rejects_changed_event_or_proved_reply(tmp_path, monkeypatch, field):
    db, evidence = setup_game(tmp_path / "replay.sqlite", monkeypatch)
    begin(db, evidence, "pawn")
    submit(db, "pawn", SUBJECT, event_id="answer", move="e3f3")
    assert process(db, SUBJECT)["outcomes"] == {"correct": 1}
    request = db.connection.execute("SELECT * FROM objective_requests").fetchone()
    session, events = current(db, request)
    board, _ = before_answer(db, session, events)
    event = dict(events[-1])
    detail = json.loads(event["response_json"])
    result = json.loads(
        db.connection.execute("SELECT result_json FROM objective_results").fetchone()[0]
    )
    assert play(board.copy(stack=True), event, detail, result)
    changed = copy.deepcopy(result)
    if field == "move":
        changed["move"] = "e3e4"
    elif field == "answer_fen":
        detail["fen"] = "changed"
    elif field == "reply":
        changed["continuation"]["reply"] = "a1a2"
    elif field == "reply_fen":
        changed["continuation"]["fen"] = "changed"
    else:
        changed["continuation"]["history_hash"] = "changed"
    with pytest.raises(ValueError):
        play(board.copy(stack=True), event, detail, changed)
