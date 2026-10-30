"""Synthetic purpose diagnostic coverage."""

import pytest

from chess_coach.purpose_view import show
from chess_coach.purpose_worker import run
from tests.purpose_config_checks import assert_completed_stale, change_after_search, change_config
from tests.purpose_fixtures import configure, request
from tests.test_deep_selection import LEARNER, setup_game


def test_engine_change_after_search_cannot_publish_current_result(tmp_path, monkeypatch):
    import chess_coach.purpose_execute as execution

    db = setup_game(tmp_path / "engine-change.sqlite", monkeypatch)
    request_id = request(db)
    monkeypatch.setattr(execution, "configuration", change_after_search(execution.configuration))
    engine = configure(monkeypatch, db)
    result = run(db, request_id, LEARNER)
    assert result["status"] == "insufficient" and result["detail"] == "engine_configuration_changed"
    assert engine.closed and len(engine.calls) == 2
    attempt = show(db, request_id, LEARNER)["attempts"][0]
    assert attempt["status"] == "insufficient" and attempt["final"] is not None


@pytest.mark.parametrize("changed", ["binary", "final_limit", "scout_limit"])
def test_completed_request_rechecks_engine_and_policy(tmp_path, monkeypatch, changed):
    import chess_coach.purpose_config as policy
    from chess_coach.purpose_request import create

    db = setup_game(tmp_path / "configuration.sqlite", monkeypatch)
    binary = tmp_path / "synthetic-engine"
    binary.write_text("synthetic version one")
    binary.chmod(0o700)
    request_id = create(db, 1, LEARNER, engine_path=str(binary))["request_id"]
    engine = configure(monkeypatch, db)
    assert run(db, request_id, LEARNER)["status"] == "complete"
    assert show(db, request_id, LEARNER)["attempts"][0]["final"] is not None
    change_config(monkeypatch, policy, binary, changed)
    assert_completed_stale(db, request_id, engine)
