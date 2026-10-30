"""Owned diagnostic isolation and candidate-set engine provenance."""

import io
import json
import sqlite3
import sys

import chess
import chess.engine
import chess.pgn
import pytest

from chess_coach.cli import main
from chess_coach.deep_selection import select_deep
from chess_coach.evidence_review import review_evidence
from chess_coach.purpose_claim import claim
from chess_coach.purpose_request import create
from chess_coach.purpose_view import show
from chess_coach.purpose_worker import run
from chess_coach.web import create_app
from tests.test_deep_selection import LEARNER, OPPONENT, PGN, setup_game


class CandidateEngine:
    def __init__(self, db, mode="normal", change=None):
        self.id = {"name": "Synthetic"}
        self.options = {}
        self.db = db
        self.mode = mode
        self.change = change
        self.calls = []
        self.closed = False

    def configure(self, settings):
        assert self.db is None or not self.db.connection.in_transaction
        self.settings = settings

    def analyse(self, board, limit, multipv, root_moves=None):
        assert self.db is None or not self.db.connection.in_transaction
        self.calls.append((board.copy(), limit, multipv, root_moves))
        if self.mode == "timeout":
            raise TimeoutError("synthetic")
        game = chess.pgn.read_game(io.StringIO(PGN))
        played = list(game.mainline_moves())[len(board.move_stack)]
        roots = root_moves or [played, next(move for move in board.legal_moves if move != played)]
        lines = []
        for index, move in enumerate(roots):
            replay = board.copy()
            pv = [move]
            replay.push(move)
            for _ in range(3):
                follow = next(iter(replay.legal_moves))
                pv.append(follow)
                replay.push(follow)
            if self.mode == "short" and root_moves is not None:
                pv = pv[:1]
            score = chess.engine.Mate(2) if self.mode == "mate" else chess.engine.Cp(index * 10)
            line = {
                "score": chess.engine.PovScore(score, board.turn),
                "pv": pv,
                "nodes": 210000 if root_moves else 51000,
                "depth": 5 + (index if self.mode == "depth" else 0),
                "time": 0.1,
            }
            if self.mode == "bound":
                line["lowerbound"] = True
            lines.append(line)
        if self.mode == "missing" and root_moves is not None:
            lines = lines[:1]
        if self.change is not None and root_moves is not None:
            self.change()
        return lines

    def quit(self):
        self.closed = True

    def close(self):
        self.closed = True


def configure(monkeypatch, db, mode="normal", change=None):
    engine = CandidateEngine(db, mode, change)
    monkeypatch.setattr(chess.engine.SimpleEngine, "popen_uci", lambda _binary, timeout: engine)
    return engine


def request(db, position=1, learner=LEARNER):
    return create(db, position, learner, engine_path=sys.executable)["request_id"]


def app(path, subject=LEARNER):
    return create_app(
        db_path=path,
        subject=subject,
        actor="reviewer",
        corpus="test",
        login="login",
        origin="https://coach.invalid",
    )


def browser_get(client, path, *, login="login"):
    return client.get(
        path, base_url="https://coach.invalid", headers={"Tailscale-User-Login": login}
    )


def test_owned_candidate_search_is_separate_and_browser_read_only(tmp_path, monkeypatch):
    path = tmp_path / "purpose.sqlite"
    db = setup_game(path, monkeypatch)
    select_deep(db, [1], learner=LEARNER, per_game=2, total=2)
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
    before = {
        name: [tuple(row) for row in db.connection.execute(f"SELECT * FROM {name}")]
        for name in tables
    }
    request_id = request(db)
    assert request(db) == request_id
    engine = configure(monkeypatch, db)
    result = run(db, request_id, LEARNER)
    assert result["status"] == "complete" and result["detail"] == "comparable"
    assert engine.closed and len(engine.calls) == 2
    scout, final = engine.calls
    assert scout[2:] == (2, None)
    assert final[2] == 2 and len(final[3]) == 2 and final[3][0].uci() == "e2e4"
    assert scout[1].nodes == 50000 and final[1].nodes == 200000
    view = show(db, request_id, LEARNER)
    assert view["source_state"] == "current" and "not a global-best" in view["scope"]
    assert view["attempts"][0]["final"]["work"]["node_limit_exceeded"]
    assert all(line["status"] == "limited" for line in view["attempts"][0]["final"]["lines"])
    assert before == {
        name: [tuple(row) for row in db.connection.execute(f"SELECT * FROM {name}")]
        for name in tables
    }
    with pytest.raises(sqlite3.IntegrityError):
        db.connection.execute("UPDATE purpose_analysis_attempts SET detail=?", ("changed",))
    db.connection.rollback()
    client = app(path).test_client()
    page = browser_get(client, f"/purpose-analysis/{request_id}")
    assert page.status_code == 200 and b"not a global-best ranking" in page.data
    assert b"no evidence, review, mastery or defense qualification" in page.data
    assert browser_get(client, "/purpose-analysis").status_code == 200
    assert browser_get(client, f"/purpose-analysis/{request_id}", login="wrong").status_code == 403
    assert (
        browser_get(
            app(path, OPPONENT).test_client(), f"/purpose-analysis/{request_id}"
        ).status_code
        == 404
    )
    assert before == {
        name: [tuple(row) for row in db.connection.execute(f"SELECT * FROM {name}")]
        for name in tables
    }


@pytest.mark.parametrize("mode", ["timeout", "short", "mate", "depth", "bound", "missing"])
def test_unusable_native_output_never_qualifies(tmp_path, monkeypatch, mode):
    db = setup_game(tmp_path / "unknown.sqlite", monkeypatch)
    request_id = request(db)
    engine = configure(monkeypatch, db, mode)
    outcome = run(db, request_id, LEARNER)
    assert outcome["status"] == "insufficient" and engine.closed
    assert len(engine.calls) <= 2
    assert show(db, request_id, LEARNER)["attempts"][0]["status"] == "insufficient"


def test_black_owned_decision_and_foreign_subject(tmp_path, monkeypatch):
    db = setup_game(tmp_path / "black.sqlite", monkeypatch)
    with pytest.raises(ValueError):
        request(db, 1, OPPONENT)
    request_id = request(db, 2, OPPONENT)
    engine = configure(monkeypatch, db)
    assert run(db, request_id, OPPONENT)["status"] == "complete"
    assert engine.calls[1][3][0].uci() == "e7e5"
    with pytest.raises(ValueError):
        show(db, request_id, LEARNER)


def test_interrupted_attempt_is_recorded_and_retry_is_bounded(tmp_path, monkeypatch):
    db = setup_game(tmp_path / "retry.sqlite", monkeypatch)
    request_id = request(db)
    claimed, state = claim(db, request_id, LEARNER, retry=False)
    assert claimed and state is None
    assert run(db, request_id, LEARNER)["status"] == "interrupted"
    assert run(db, request_id, LEARNER)["status"] == "retry_required_or_exhausted"
    configure(monkeypatch, db)
    assert run(db, request_id, LEARNER, retry=True)["status"] == "complete"
    assert [item["status"] for item in show(db, request_id, LEARNER)["attempts"]] == [
        "interrupted",
        "complete",
    ]


def test_source_change_during_search_cannot_publish_current_result(tmp_path, monkeypatch):
    db = setup_game(tmp_path / "stale.sqlite", monkeypatch)
    request_id = request(db)

    def change():
        db.connection.execute("UPDATE games SET pgn=pgn || ? WHERE id=1", (" ",))
        db.connection.commit()

    configure(monkeypatch, db, change=change)
    outcome = run(db, request_id, LEARNER)
    assert outcome["status"] == "stale"
    result = show(db, request_id, LEARNER)
    assert result["source_state"] == "stale" and result["attempts"] == []


def test_unrelated_review_does_not_turn_diagnostic_into_learning(tmp_path, monkeypatch):
    db = setup_game(tmp_path / "review.sqlite", monkeypatch)
    request_id = request(db)
    configure(monkeypatch, db)
    assert run(db, request_id, LEARNER)["status"] == "complete"
    before = show(db, request_id, LEARNER)
    cursor = db.connection.execute(
        "INSERT INTO evidence_mappings(position_id,skill,operation,outcome,confidence) VALUES(?,?,?,?,?)",
        (1, "synthetic", "observe", "ambiguous", 0.5),
    )
    db.connection.commit()
    review_evidence(db, cursor.lastrowid, decision="accept", actor="synthetic")
    assert show(db, request_id, LEARNER) == before
    assert db.connection.execute("SELECT COUNT(*) FROM mastery_states").fetchone()[0] == 0
    assert "no evidence" in before["boundary"]


def test_cli_request_run_and_show(tmp_path, monkeypatch, capsys):
    path = tmp_path / "cli.sqlite"
    db = setup_game(path, monkeypatch)
    db.close()
    monkeypatch.setenv("LICHESS_USERNAME", LEARNER)
    monkeypatch.setattr(
        sys,
        "argv",
        ["chess-coach", "--db", str(path), "request-purpose", "1", "--engine-path", sys.executable],
    )
    main()
    request_id = json.loads(capsys.readouterr().out)["request_id"]
    monkeypatch.setattr(
        chess.engine.SimpleEngine, "popen_uci", lambda _binary, timeout: CandidateEngine(None)
    )
    monkeypatch.setattr(
        sys, "argv", ["chess-coach", "--db", str(path), "run-purpose", str(request_id)]
    )
    main()
    assert json.loads(capsys.readouterr().out)["status"] == "complete"
    monkeypatch.setattr(
        sys, "argv", ["chess-coach", "--db", str(path), "show-purpose", str(request_id)]
    )
    main()
    shown = json.loads(capsys.readouterr().out)
    assert shown["source_state"] == "current" and shown["status"] == "complete"


def test_lock_excludes_other_deep_workers_and_deadline_starts_no_search(tmp_path, monkeypatch):
    from chess_coach.deep_execution_lock import deep_lock
    from chess_coach.purpose_search import search

    db = setup_game(tmp_path / "lock.sqlite", monkeypatch)
    request_id = request(db)
    engine = configure(monkeypatch, db)
    with deep_lock(db.path), pytest.raises(RuntimeError, match="already running"):
        run(db, request_id, LEARNER)
    assert not engine.calls
    result, issue = search(engine, chess.Board(), {"id": 1, "uci": "e2e4"}, 0)
    assert issue == "worker_deadline" and not engine.calls
    assert result["global_best"] == "unknown"


def test_explicit_retry_cannot_exceed_two_attempts(tmp_path, monkeypatch):
    db = setup_game(tmp_path / "retry-limit.sqlite", monkeypatch)
    request_id = request(db)
    first = configure(monkeypatch, db, mode="timeout")
    assert run(db, request_id, LEARNER)["detail"] == "engine_timeout"
    assert first.closed
    second = configure(monkeypatch, db, mode="timeout")
    assert run(db, request_id, LEARNER, retry=True)["detail"] == "engine_timeout"
    assert second.closed
    third = configure(monkeypatch, db)
    assert run(db, request_id, LEARNER, retry=True)["status"] == "retry_required_or_exhausted"
    assert not third.calls
    assert len(show(db, request_id, LEARNER)["attempts"]) == 2


def test_repeated_history_is_rejected_before_engine(tmp_path, monkeypatch):
    import tests.test_deep_selection as fixture

    repeated = PGN.replace(
        "1. e4 e5 2. Nf3 Nc6 3. Bc4 Nf6 4. d3 d6 5. c3 Be7 6. O-O O-O *",
        "1. Nf3 Nf6 2. Ng1 Ng8 3. Nf3 Nf6 4. Ng1 Ng8 *",
    )
    monkeypatch.setattr(fixture, "PGN", repeated)
    db = setup_game(tmp_path / "repeat.sqlite", monkeypatch)
    with pytest.raises(ValueError, match="draw-sensitive"):
        request(db, 5)
    assert (
        db.connection.execute("SELECT COUNT(*) FROM purpose_analysis_requests").fetchone()[0] == 0
    )


def test_engine_change_after_search_cannot_publish_current_result(tmp_path, monkeypatch):
    import chess_coach.purpose_execute as execution

    db = setup_game(tmp_path / "engine-change.sqlite", monkeypatch)
    request_id = request(db)
    original = execution.configuration
    checks = []

    def changed(db, game_id, path):
        binary, config = original(db, game_id, path)
        checks.append(True)
        if len(checks) > 1:
            config = {**config, "engine_sha256": "changed-synthetic-binary"}
        return binary, config

    monkeypatch.setattr(execution, "configuration", changed)
    engine = configure(monkeypatch, db)
    result = run(db, request_id, LEARNER)
    assert result["status"] == "insufficient" and result["detail"] == "engine_configuration_changed"
    assert engine.closed and len(engine.calls) == 2
    attempt = show(db, request_id, LEARNER)["attempts"][0]
    assert attempt["status"] == "insufficient" and attempt["final"] is not None
