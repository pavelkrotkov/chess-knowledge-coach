"""Synthetic purpose diagnostic coverage."""

import json
import sys

import chess
import chess.engine
import pytest

from chess_coach.cli import main
from chess_coach.purpose_view import show
from chess_coach.purpose_worker import run
from tests.purpose_fixtures import CandidateEngine, configure, request
from tests.purpose_search_checks import assert_black_history
from tests.test_deep_selection import LEARNER, OPPONENT, setup_game


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


def test_black_owned_decision_and_foreign_subject(tmp_path, monkeypatch):
    db = setup_game(tmp_path / "black.sqlite", monkeypatch)
    with pytest.raises(ValueError):
        request(db, 1, OPPONENT)
    request_id = request(db, 2, OPPONENT)
    engine = configure(monkeypatch, db)
    assert run(db, request_id, OPPONENT)["status"] == "complete"
    assert_black_history(engine)
    with pytest.raises(ValueError):
        show(db, request_id, LEARNER)
