"""Synthetic purpose comparisons bound to separately current original proof."""

import sys
import time

import chess
import chess.engine
import pytest

from chess_coach.pipeline_config import PipelineConfig
from chess_coach.style_report import style_report
from chess_coach.style_schedule_worker import process_schedule
from tests.test_style_protection_schedule import force_control
from tests.test_style_protection_source import fixture
from tests.test_style_schedule import SyntheticEngine


@pytest.mark.parametrize("black", [False, True])
def test_current_source_and_purpose_comparison_contribute_one_protection_vote(
    tmp_path, monkeypatch, capsys, black
):
    import chess_coach.style_purpose_collect as collector

    db, learner, position, evidence = fixture(tmp_path / "report.sqlite", monkeypatch, black=black)
    force_control(monkeypatch, position, False)
    played, other = ("c6a5", "b8b5") if black else ("c3a4", "b1b4")

    class ScriptedEngine(SyntheticEngine):
        def analyse(self, board, _limit, multipv, root_moves=None):
            roots = root_moves or [board.parse_uci(played), board.parse_uci(other)]
            return super().analyse(board, _limit, multipv, roots)

    monkeypatch.setattr(chess.engine.SimpleEngine, "popen_uci", lambda *_a, **_k: ScriptedEngine())
    scheduled = process_schedule(
        db,
        PipelineConfig(learner=learner, engine_path=sys.executable),
        deadline=time.monotonic() + 25,
    )
    assert scheduled["processed"][0]["status"] == "complete"
    original_selection = collector.selection
    second = process_schedule(
        db,
        PipelineConfig(learner=learner, engine_path=sys.executable),
        deadline=time.monotonic() + 25,
    )
    assert second["processed"][0]["request_id"] == scheduled["processed"][0]["request_id"]
    monkeypatch.setattr(collector, "selection", lambda *_args: None)
    monkeypatch.setattr(
        chess.engine.SimpleEngine, "popen_uci", lambda *_a, **_k: pytest.fail("report searched")
    )
    import chess_coach.preview_history as preview_module

    original_replay = preview_module.decision_context_boards
    replays = []

    def count_replay(*args, **kwargs):
        replays.append(True)
        return original_replay(*args, **kwargs)

    monkeypatch.setattr(preview_module, "decision_context_boards", count_replay)
    report = style_report(db, learner)
    assert replays == [True]
    observations = [item for item in report["observations"] if item["position_id"] == position]
    assert len(observations) == 1
    item = observations[0]
    assert item["provenance"] == "purpose_candidate_set_and_original_proof"
    assert item["choices"]["protect_move_target"] == "moved_target"
    assert item["pairs"][0]["played"]["protection"]["evidence_id"] == evidence
    assert item["pairs"][0]["played"]["protection"]["source"]["review_status"] == "unreviewed"
    assert report["dimensions"]["protect_move_target"]["opportunities"] == 1
    assert report["protection_coverage"]["used"] <= 20
    assert report["purpose_schedule"]["protection"]["source_state"] == "current"
    assert report["purpose_coverage"]["counts"]["protection_duplicate"] == 1
    assert db.connection.execute("SELECT COUNT(*) FROM mastery_states").fetchone()[0] == 0
    if not black:
        import importlib
        import json

        from chess_coach.cli import main
        from chess_coach.evidence_review import review_evidence
        from tests.purpose_browser_fixtures import app, browser_get

        monkeypatch.setattr(
            sys,
            "argv",
            [
                "chess-coach",
                "--db",
                str(tmp_path / "report.sqlite"),
                "style-choices",
                "--learner",
                learner,
            ],
        )
        main()
        cli = json.loads(capsys.readouterr().out)
        assert cli["dimensions"]["protect_move_target"]["opportunities"] == 1
        response = browser_get(
            app(tmp_path / "report.sqlite", subject=learner).test_client(), "/style-choices"
        )
        assert response.status_code == 200
        assert b"original evidence" in response.data
        assert b"review unreviewed" in response.data
        assert b"not a global-best ranking" in response.data

        request_id = scheduled["processed"][0]["request_id"]
        attempt = db.connection.execute(
            "SELECT result_json FROM purpose_analysis_attempts WHERE request_id=?", (request_id,)
        ).fetchone()
        result = json.loads(attempt["result_json"])
        result["final"]["roots"] = ["a2a3", "a2a4"]
        db.connection.execute("SAVEPOINT synthetic_tamper")
        db.connection.execute("DROP TRIGGER purpose_attempts_no_update")
        db.connection.execute(
            "UPDATE purpose_analysis_attempts SET result_json=? WHERE request_id=?",
            (json.dumps(result), request_id),
        )
        substituted = style_report(db, learner)
        assert substituted["dimensions"]["protect_move_target"]["opportunities"] == 0
        db.connection.execute("ROLLBACK TO synthetic_tamper")
        db.connection.execute("RELEASE synthetic_tamper")

        module = importlib.import_module("chess_coach.style_report")
        monkeypatch.setattr(module, "PROTECTION_WORK_LIMIT", 0)
        limited = style_report(db, learner)
        assert limited["dimensions"]["protect_move_target"]["opportunities"] == 0
        assert limited["protection_coverage"]["skipped_decisions"] > 0
        assert limited["purpose_schedule"]["protection"]["state"] == "unknown"
        monkeypatch.setattr(module, "PROTECTION_WORK_LIMIT", 20)
        monkeypatch.setattr(collector, "selection", original_selection)
        ordinary = style_report(db, learner)
        assert ordinary["dimensions"]["protect_move_target"]["opportunities"] == 1
        assert (
            sum(
                item["provenance"] == "purpose_candidate_set_and_original_proof"
                for item in ordinary["observations"]
            )
            == 0
        )
        monkeypatch.setattr(collector, "selection", lambda *_args: None)
        import chess_coach.style_protection_purpose_source as source_module
        from chess_coach.db import Database

        db.connection.commit()
        db.connection.execute("PRAGMA journal_mode=WAL")
        writer = Database(tmp_path / "report.sqlite")
        original_reference = source_module.reference
        written = []

        def concurrent_rejection(*args):
            if not written:
                review_evidence(writer, evidence, decision="reject", actor="fixture_reviewer")
                written.append(True)
            return original_reference(*args)

        monkeypatch.setattr(source_module, "reference", concurrent_rejection)
        during = style_report(db, learner)
        assert written == [True]
        assert during["dimensions"]["protect_move_target"]["opportunities"] == 1
        changed = db.connection.total_changes
        revoked = style_report(db, learner)
        assert revoked["dimensions"]["protect_move_target"]["opportunities"] == 0
        assert revoked["purpose_schedule"]["protection"]["state"] == "unknown"
        assert db.connection.total_changes == changed
        writer.close()
    db.close()


def test_unsupported_ordinary_protection_cannot_suppress_purpose_or_other_families():
    from collections import Counter

    from chess_coach.style_dimensions import dimensions
    from chess_coach.style_protection_purpose_merge import merge

    choices = dimensions([])
    choices["protect_move_target"] = "ambiguous"
    choices["defense_king"] = "king_move"
    ordinary = {
        "choices": choices,
        "pairs": [
            {
                "played": {"protection": {"status": "unknown"}},
                "alternative": {"protection": {"status": "unknown"}},
            }
        ],
    }
    purpose = {"eligible_dimensions": ["protect_move_target", "protect_capture_attacker"]}
    state = {"counts": Counter(), "observations": []}
    merge((1, 2), purpose, {(1, 2): ordinary}, state)
    assert "defense_king" in ordinary["eligible_dimensions"]
    assert "protect_move_target" not in ordinary["eligible_dimensions"]
    assert state["observations"] == [purpose]


def test_cycle_window_is_bounded_to_three_hundred_allocation_labels():
    from chess_coach.db import Database
    from chess_coach.deep_selection_source import learner_key
    from chess_coach.style_purpose_slots import slots

    db = Database(":memory:")
    db.initialize()
    key = learner_key("fixture_learner")
    for sequence in range(101):
        cycle = db.connection.execute(
            "INSERT INTO style_schedule_cycles(learner_key,sequence,coverage_json) VALUES(?,?,?)",
            (key, sequence, "{}"),
        ).lastrowid
        for kind in ("target", "control"):
            db.connection.execute(
                "INSERT INTO style_schedule_slots(cycle_id,kind,status,detail) VALUES(?,?,?,?)",
                (cycle, kind, "unknown", "synthetic"),
            )
        db.connection.execute(
            "INSERT INTO style_protection_allocations(cycle_id,status,detail) VALUES(?,?,?)",
            (cycle, "unknown", "synthetic"),
        )
    rows, coverage = slots(db, "fixture_learner")
    assert len(rows) == 300
    assert coverage["examined_cycles"] == 100
    assert coverage["allocation_labels_examined"] == coverage["allocation_label_limit"] == 300
    assert coverage["older_cycles_unknown"] is True
    assert sum(row["kind"] == "protection" for row in rows) == 100
    db.close()


def test_current_original_proof_remains_separate_from_unsupported_comparison(monkeypatch):
    from collections import Counter

    import chess_coach.style_protection_purpose_evaluate as evaluator

    monkeypatch.setattr(evaluator, "_admit", lambda *_args: (None, {}))
    monkeypatch.setattr(evaluator, "observation", lambda *_args: ("unsupported", None, True))
    monkeypatch.setattr(evaluator, "provenance", lambda _slot: {"source_state": "current"})
    state = {
        "counts": Counter(),
        "protection_checks": {},
        "protection_seen": set(),
        "observations": [],
    }
    evaluator.evaluate(None, "synthetic", {"id": 3}, {}, {}, state, {}, {}, None)
    assert state["protection_checks"][3]["source_state"] == "current"
    assert state["protection_checks"][3]["comparison_state"] == "unsupported"
    assert state["counts"]["protection_unsupported"] == 1
    assert not state["observations"]


def test_ambiguous_dimension_does_not_override_supported_ordinary_dimension():
    from collections import Counter

    from chess_coach.style_dimensions import dimensions
    from chess_coach.style_protection_purpose_merge import merge

    choices = dimensions([])
    choices["protect_move_target"] = "ambiguous"
    choices["protect_capture_attacker"] = "captured_attacker"
    endpoint = {"protection": {"status": "supported"}}
    ordinary = {"choices": choices, "pairs": [{"played": endpoint, "alternative": endpoint}]}
    purpose = {"eligible_dimensions": ["protect_move_target", "protect_capture_attacker"]}
    state = {"counts": Counter(), "observations": []}
    merge((1, 2), purpose, {(1, 2): ordinary}, state)
    assert "protect_capture_attacker" in ordinary["eligible_dimensions"]
    assert "protect_move_target" not in ordinary["eligible_dimensions"]
    assert purpose["eligible_dimensions"] == ["protect_move_target"]
    assert state["observations"] == [purpose]
