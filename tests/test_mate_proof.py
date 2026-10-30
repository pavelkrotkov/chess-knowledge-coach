"""Bounded proofs are legal, history-aware and separate from skill evidence."""

import json
import os
import sys

import chess
import chess.engine
import pytest

from chess_coach.cli import main
from chess_coach.db import Database
from chess_coach.ingest import ingest_pgn
from chess_coach.mate_inspection import inspect_mate
from chess_coach.mate_proof import immediate_mates, prove_short_mates
from chess_coach.pipeline_config import PipelineConfig
from chess_coach.pipeline_inputs import engine_identity, game_input
from chess_coach.pipeline_work import run_analysis
from chess_coach.web import create_app

FEN = "7k/8/5KQ1/8/8/8/8/8 w - - 0 1"
BLACK_FEN = "8/8/8/8/8/5kq1/8/7K b - - 0 1"


class Engine:
    def __init__(self):
        self.id = {"name": "fixture"}
        self.options = {}

    def configure(self, settings):
        pass

    def analyse(self, board, limit, multipv, root_moves=None):
        move = root_moves[0] if root_moves else next(iter(board.legal_moves))
        return [
            {
                "score": chess.engine.PovScore(chess.engine.Cp(0), board.turn),
                "pv": [move],
                "nodes": 10,
                "depth": 1,
            }
        ]

    def quit(self):
        pass


def owned_game(path, monkeypatch, fen=FEN, move="Qg1"):
    pgn = f'''[Event "Synthetic"]
[White "fixture_a"]
[Black "fixture_b"]
[SetUp "1"]
[FEN "{fen}"]
[Result "*"]

1. {move} *
'''
    db = Database(path)
    db.initialize()
    ingest_pgn(db, pgn)
    monkeypatch.setattr(chess.engine.SimpleEngine, "popen_uci", lambda _: Engine())
    config = PipelineConfig(learner="fixture_a", engine_path=sys.executable, nodes=100)
    result = run_analysis(db, 1, game_input(db, 1), config, engine_identity(sys.executable))
    assert result["status"] == "complete"
    return db


@pytest.mark.parametrize("fen", [FEN, BLACK_FEN])
def test_proofs_cover_every_defense_and_are_legal(fen):
    board = chess.Board(fen)
    result = prove_short_mates(board)
    assert result["status"] == "proved"
    assert immediate_mates(board)
    longer = [
        root
        for root in result["alternatives"]
        if root["status"] == "proved" and root["distance_plies"] == 3
    ]
    assert longer
    for root in longer:
        board.push_uci(root["move"]["uci"])
        assert {move.uci() for move in board.legal_moves} == {
            line["defense"]["uci"] for line in root["defenses"]
        }
        for line in root["defenses"]:
            board.push_uci(line["defense"]["uci"])
            board.push_uci(line["mate"]["uci"])
            assert board.is_checkmate()
            board.pop()
            board.pop()
        board.pop()
    assert board.fen() == fen


def test_budget_unknown_and_nonmate_disproof():
    board = chess.Board("7k/8/8/8/8/8/8/KR6 w - - 0 1")
    complete = prove_short_mates(board)
    assert complete["status"] == "disproved"
    limited = prove_short_mates(board, node_limit=1)
    assert limited["status"] == "unknown" and limited["nodes"] == 1
    assert any(root["status"] == "unknown" for root in limited["alternatives"])
    with pytest.raises(ValueError):
        prove_short_mates(board, node_limit=0)


def test_private_pipeline_facts_cli_browser_and_stale(tmp_path, monkeypatch, capsys):
    path = tmp_path / "mate.sqlite"
    db = owned_game(path, monkeypatch)
    before = db.connection.total_changes
    report = inspect_mate(db, 1, learner="fixture_a")
    assert report["status"] == "current" and report["immediate_mate_not_played"]
    assert not report["played_checkmate"] and not report["played_stalemate"]
    assert report["played"]["san"] == "Qg1" and report["immediate_mates"][0]["san"] == "Qg7#"
    assert db.connection.total_changes == before
    assert inspect_mate(db, 1, learner="fixture_b")["status"] == "unavailable"
    assert inspect_mate(db, 1, learner="other")["status"] == "unavailable"
    assert inspect_mate(db, 1, learner="fixture_a", expected_fingerprint="old")["status"] == "stale"
    monkeypatch.setenv("LICHESS_USERNAME", "fixture_a")
    monkeypatch.setattr(sys, "argv", ["chess-coach", "--db", str(path), "inspect-mate", "1"])
    main()
    assert json.loads(capsys.readouterr().out)["proof"]["status"] == "proved"
    app = create_app(
        db_path=path,
        subject="fixture_a",
        actor="operator",
        corpus="test",
        login="fixture",
        origin="https://coach.invalid",
    )
    client = app.test_client()
    assert client.get("/decisions/1/mate", base_url="https://coach.invalid").status_code == 403
    headers = {"Tailscale-User-Login": "fixture"}
    page = client.get("/decisions/1/mate", base_url="https://coach.invalid", headers=headers)
    assert page.status_code == 200 and b"Qg7#" in page.data and b"not a skill" in page.data
    stale = client.get(
        "/decisions/1/mate?source=old", base_url="https://coach.invalid", headers=headers
    )
    assert b"stale" in stale.data and b"Qg7#" not in stale.data
    assert db.connection.execute("SELECT COUNT(*) FROM evidence_mappings").fetchone()[0] == 0


@pytest.mark.skipif(not os.access("/usr/games/stockfish", os.X_OK), reason="Stockfish unavailable")
def test_real_engine_pipeline_mate_inspection(tmp_path):
    pgn = f'''[Event "Synthetic"]
[White "fixture_a"]
[Black "fixture_b"]
[SetUp "1"]
[FEN "{FEN}"]
[Result "*"]

1. Qg1 *
'''
    db = Database(tmp_path / "real.sqlite")
    db.initialize()
    ingest_pgn(db, pgn)
    config = PipelineConfig(
        learner="fixture_a", engine_path="/usr/games/stockfish", nodes=100, seconds_per_position=1
    )
    result = run_analysis(db, 1, game_input(db, 1), config, engine_identity(config.engine_path))
    assert result["status"] == "complete"
    report = inspect_mate(db, 1, learner="fixture_a")
    assert report["status"] == "current" and report["immediate_mate_not_played"]
    assert report["proof"]["status"] == "proved"
