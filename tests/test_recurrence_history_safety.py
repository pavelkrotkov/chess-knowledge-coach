"""Request-scoped lesson reuse preserves freshness, isolation, and cleanup."""

import re
import sys
from concurrent.futures import ThreadPoolExecutor

import chess.engine
import pytest

from chess_coach.db import Database
from chess_coach.evidence_review import review_evidence
from chess_coach.pipeline_config import PipelineConfig
from chess_coach.web import create_app
from tests.test_pin_lessons import LEARNER, _publish
from tests.test_pin_pipeline import Engine

QUERY = {
    "start": "2026-01-01T00:00:00+00:00",
    "end": "2026-02-01T00:00:00+00:00",
    "compare_start": "2025-12-01T00:00:00+00:00",
    "skill": "relative_pin",
    "operation": "prevent",
}
HEADERS = {"Tailscale-User-Login": "fixture-login"}


def fixture_db(path, monkeypatch):
    db = Database(path)
    db.initialize()
    monkeypatch.setattr(chess.engine.SimpleEngine, "popen_uci", lambda _: Engine())
    config = PipelineConfig(
        learner=LEARNER, engine_path=sys.executable, nodes=100, deep_enabled=False
    )
    fen = "7k/5p2/8/8/8/4r3/4R2K/4Q3 w - - 0 1"
    entries = [_publish(db, config, fen, "e2f2", day, "prevent") for day in (1, 2, 3)]
    return db, entries


def application(path, subject=LEARNER):
    return create_app(
        db_path=path,
        subject=subject,
        actor="fixture",
        corpus="test",
        login="fixture-login",
        origin="https://coach.invalid",
    )


def page(app):
    with app.test_client() as client:
        response = client.get(
            "/recurrence", base_url="https://coach.invalid", headers=HEADERS, query_string=QUERY
        )
    assert response.status_code == 200
    return re.sub(rb'(name="csrf" value=")[^"]+', rb"\1[nonce]", response.data)


def test_next_get_rechecks_review_and_source_without_learning_writes(tmp_path, monkeypatch):
    path = tmp_path / "fresh.sqlite"
    db, entries = fixture_db(path, monkeypatch)
    app = application(path)
    assert b"3 recorded candidate positions across 3 independent games" in page(app)
    assert db.connection.execute("SELECT COUNT(*) FROM evidence_review_events").fetchone()[0] == 0
    assert db.connection.execute("SELECT COUNT(*) FROM lesson_versions").fetchone()[0] == 0
    first = entries[0][1]["evidence_ids"][0]
    review_evidence(db, first, decision="reject", actor="fixture")
    assert b"2 recorded candidate positions across 2 independent games" in page(app)
    db.connection.execute(
        "UPDATE decision_analysis_lines SET score_value=score_value+1 WHERE position_id=?",
        (entries[1][0],),
    )
    db.connection.commit()
    assert b"1 recorded candidate positions across 1 independent games" in page(app)
    assert db.connection.execute("SELECT COUNT(*) FROM evidence_review_events").fetchone()[0] == 1
    assert db.connection.execute("SELECT COUNT(*) FROM lesson_versions").fetchone()[0] == 0
    db.close()


def test_concurrent_requests_do_not_share_history_or_subject(tmp_path, monkeypatch):
    path = tmp_path / "concurrent.sqlite"
    db, _entries = fixture_db(path, monkeypatch)
    db.close()
    owned, other = application(path), application(path, subject="fixture_other")
    uppercase = application(path, subject=LEARNER.upper())
    with ThreadPoolExecutor(max_workers=4) as pool:
        first, second, outsider, folded = [
            future.result()
            for future in (
                pool.submit(page, owned),
                pool.submit(page, owned),
                pool.submit(page, other),
                pool.submit(page, uppercase),
            )
        ]
    assert first == second == folded
    assert b"3 recorded candidate positions across 3 independent games" in first
    assert b"3 recorded candidate positions across 3 independent games" not in outsider
    assert b"No candidates within this bounded sample" in outsider


def test_shared_history_stays_with_database_subject_and_family(tmp_path, monkeypatch):
    from chess_coach.fork_detector import process_decision
    from chess_coach.lesson_source import source
    from chess_coach.preview_snapshot import preview_history
    from tests.test_fork_pipeline import make_game

    path = tmp_path / "families.sqlite"
    db, _config = make_game(path, monkeypatch)
    fork_id = process_decision(db, 1, LEARNER)["evidence_ids"][0]
    monkeypatch.setattr(chess.engine.SimpleEngine, "popen_uci", lambda _: Engine())
    config = PipelineConfig(
        learner=LEARNER, engine_path=sys.executable, nodes=100, deep_enabled=False
    )
    pin_pos, pin = _publish(db, config, "7k/5p2/8/8/8/4r3/4R2K/4Q3 w - - 0 1", "e2f2", 2, "prevent")
    candidates = [
        {"id": fork_id, "position_id": 1},
        {"id": pin["evidence_ids"][0], "position_id": pin_pos},
    ]
    expected = [source(db, LEARNER, candidate) for candidate in candidates]
    assert all(expected)
    other_db = Database(path)
    with preview_history(db, LEARNER) as history:
        history.targets(item["position_id"] for item in candidates)
        assert [source(db, LEARNER, item, _history=history) for item in candidates] == expected
        assert source(other_db, LEARNER, candidates[0], _history=history) is None
        assert source(db, "fixture_other", candidates[0], _history=history) is None
        from chess_coach.recurrence_report import report

        with pytest.raises(ValueError, match="history scope"):
            report(
                other_db,
                LEARNER,
                QUERY["start"],
                QUERY["end"],
                QUERY["compare_start"],
                _history=history,
            )
        with pytest.raises(ValueError, match="history scope"):
            report(
                db,
                "fixture_other",
                QUERY["start"],
                QUERY["end"],
                QUERY["compare_start"],
                _history=history,
            )
    other_db.close()
    db.close()


def test_exception_clears_history_and_restores_outer_snapshot(tmp_path, monkeypatch):
    import chess_coach.web_recurrence as recurrence
    from chess_coach.preview_snapshot import preview_history
    from chess_coach.recurrence_snapshot import read_snapshot
    from chess_coach.web_db import database

    path = tmp_path / "cleanup.sqlite"
    db, _entries = fixture_db(path, monkeypatch)
    db.close()
    histories = []

    def fail(db, subject, group, *, _history):
        histories.append(_history)
        assert db.connection.execute("PRAGMA query_only").fetchone()[0] == 1
        raise RuntimeError("fixture failure")

    monkeypatch.setattr(recurrence, "build", fail)
    with application(path).app_context():
        db = database()
        with read_snapshot(db):
            with (
                pytest.raises(RuntimeError, match="fixture failure"),
                preview_history(db, LEARNER) as history,
            ):
                history.targets([1])
                recurrence._attach_lessons(
                    {"current": [{"lesson_examples": [{"position_id": 1}]}], "previous": []},
                    db,
                    LEARNER,
                    history,
                )
            assert db.connection.execute("PRAGMA query_only").fetchone()[0] == 0
            assert db.connection.in_transaction
            assert not histories[0].wanted and not histories[0].games
        assert not db.connection.in_transaction


def test_concurrent_review_change_is_visible_only_on_next_get(tmp_path, monkeypatch):
    import chess_coach.recurrence_report_helpers as helpers

    path = tmp_path / "snapshot.sqlite"
    db, entries = fixture_db(path, monkeypatch)
    db.connection.execute("PRAGMA journal_mode=WAL")
    db.close()
    writer = Database(path)
    original = helpers.evidence
    changed = []

    def change_after_snapshot(*args):
        result = original(*args)
        if not changed:
            review_evidence(
                writer, entries[0][1]["evidence_ids"][0], decision="reject", actor="fixture"
            )
            changed.append(True)
        return result

    monkeypatch.setattr(helpers, "evidence", change_after_snapshot)
    app = application(path)
    assert b"3 recorded candidate positions across 3 independent games" in page(app)
    assert changed
    assert b"2 recorded candidate positions across 2 independent games" in page(app)
    writer.close()
