"""Configuration freshness checks for completed diagnostics."""

from chess_coach.purpose_view import show
from chess_coach.purpose_worker import run
from tests.purpose_ui_assertions import assert_stale_browser
from tests.test_deep_selection import LEARNER


def change_config(monkeypatch, policy, binary, changed):
    if changed == "binary":
        binary.write_text("synthetic version two")
    elif changed == "final_limit":
        monkeypatch.setattr(policy, "FINAL_NODES", policy.FINAL_NODES + 1)
    else:
        monkeypatch.setattr(policy, "SCOUT_NODES", policy.SCOUT_NODES + 1)


def assert_completed_stale(db, request_id, engine):
    result = show(db, request_id, LEARNER)
    assert result["source_state"] == "stale"
    assert result["attempts"] == [{"number": 1, "status": "complete", "detail": "comparable"}]
    assert run(db, request_id, LEARNER)["status"] == "stale"
    assert len(engine.calls) == 2
    assert (
        db.connection.execute("SELECT COUNT(*) FROM purpose_analysis_attempts").fetchone()[0] == 1
    )
    assert_stale_browser(db.path, request_id)


def change_after_search(original):
    checks = []

    def changed(db, game_id, path):
        binary, config = original(db, game_id, path)
        checks.append(True)
        if len(checks) > 1:
            config = {**config, "engine_sha256": "changed-synthetic-binary"}
        return binary, config

    return changed
