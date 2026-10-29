"""Adversarial checks for pawn proof reuse and latest request outcomes."""

import copy
import json

import pytest

from chess_coach.objective_current import current
from chess_coach.objective_pawn_binding import binding
from chess_coach.objective_pawn_history import before_answer
from chess_coach.objective_worker import process
from chess_coach.unified_session_events import submit
from tests.test_objective_pawn import SUBJECT, begin, setup_game


@pytest.mark.parametrize(
    "field",
    [
        "verifier",
        "proof_version",
        "proof_manifest_sha256",
        "history_hash",
        "source_hash",
        "event_prefix_hash",
        "snapshot_hash",
        "history_mode",
        "objective_version",
        "goal",
        "lower",
        "reply_bounds",
    ],
)
def test_prior_certificate_tampering_is_rejected(tmp_path, monkeypatch, field):
    db, evidence = setup_game(tmp_path / "certificate.sqlite", monkeypatch)
    begin(db, evidence, "proof")
    submit(db, "proof", SUBJECT, event_id="answer", move="e3f3")
    assert process(db, SUBJECT)["outcomes"] == {"correct": 1}
    request = db.connection.execute("SELECT * FROM objective_requests").fetchone()
    session, events = current(db, request)
    board, _ = before_answer(db, session, events)
    result = json.loads(
        db.connection.execute("SELECT result_json FROM objective_results").fetchone()[0]
    )
    binding(request, result, board, session)
    changed = copy.deepcopy(result)
    if field == "reply_bounds":
        changed["continuation"]["opponent_bounds"] = [0, 0]
    else:
        changed[field] = {"goal": 0, "lower": -1}.get(field, "tampered")
    with pytest.raises(ValueError, match="pawn continuation"):
        binding(request, changed, board, session)
