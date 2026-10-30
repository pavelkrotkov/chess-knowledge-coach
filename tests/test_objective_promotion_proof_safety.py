"""Adversarial checks for promotion proof binding and continuation."""

import json

import pytest

from chess_coach.objective_current import current
from chess_coach.objective_promotion_history import before_answer
from chess_coach.objective_promotion_proof_binding import binding
from chess_coach.objective_worker import process
from chess_coach.unified_session_events import submit
from tests.test_objective_promotion import SUBJECT, begin, setup_db


def proved_source(tmp_path):
    db = setup_db(tmp_path / "promotion-proof.sqlite")
    begin(db, "forced-white", "proof")
    submit(db, "proof", SUBJECT, event_id="root", move="a6a7")
    assert process(db, SUBJECT)["outcomes"] == {"correct": 1}
    request = db.connection.execute("SELECT * FROM objective_requests").fetchone()
    session, events = current(db, request)
    board, move = before_answer(db, session, events)
    result = json.loads(
        db.connection.execute("SELECT result_json FROM objective_results").fetchone()[0]
    )
    return db, request, board, move, result


@pytest.mark.parametrize(
    "field",
    [
        "objective_version",
        "history_mode",
        "snapshot_hash",
        "event_prefix_hash",
        "source_hash",
        "verifier",
        "history_hash",
        "move",
    ],
)
def test_promotion_proof_rejects_tampered_binding(tmp_path, field):
    _, request, board, move, result = proved_source(tmp_path)
    binding(request, result, board, move)
    changed = dict(result) | {field: "tampered"}
    with pytest.raises(ValueError, match="promotion proof"):
        binding(request, changed, board, move)
