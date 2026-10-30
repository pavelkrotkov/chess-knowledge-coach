"""Compare diagnostic effects and synthetic engine evidence."""

from chess_coach.purpose_view import show
from tests.test_deep_selection import LEARNER


def snapshot_learning_tables(db):
    tables = (
        "analysis_runs",
        "engine_outputs",
        "decision_analysis_lines",
        "deep_selection_current",
        "deep_analysis_current",
        "evidence_mappings",
        "evidence_review_events",
        "mastery_states",
        "training_items",
    )
    return {
        name: [tuple(row) for row in db.connection.execute(f"SELECT * FROM {name}")]
        for name in tables
    }


def assert_candidate_search(engine, db, request_id):
    assert engine.closed and len(engine.calls) == 2
    scout, final = engine.calls
    assert scout[2:] == (2, None)
    assert final[2] == 2 and len(final[3]) == 2 and final[3][0].uci() == "e2e4"
    assert scout[1].nodes == 50000 and final[1].nodes == 200000
    view = show(db, request_id, LEARNER)
    assert view["source_state"] == "current" and "not a global-best" in view["scope"]
    assert view["attempts"][0]["final"]["work"]["node_limit_exceeded"]
    assert all(line["status"] == "limited" for line in view["attempts"][0]["final"]["lines"])
