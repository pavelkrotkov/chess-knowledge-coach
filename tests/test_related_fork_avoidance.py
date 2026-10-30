"""Synthetic created-by-play fork avoidance through the existing session."""

import chess
import chess.engine
import chess.pgn
import pytest

from chess_coach.db import Database
from chess_coach.fork_defense_detector import process_decision
from chess_coach.ingest import ingest_pgn
from chess_coach.pipeline_config import PipelineConfig
from chess_coach.pipeline_inputs import engine_identity, game_input
from chess_coach.pipeline_work import run_analysis
from chess_coach.related_fork_avoidance import preview, selection
from chess_coach.related_fork_avoidance_start import start_related
from chess_coach.unified_session_events import submit
from tests.related_protection_support import learning_counts
from tests.test_fork_defense import mirror
from tests.test_fork_defense_pipeline import LEARNER, Engine
from tests.transfer_concealment_support import preview_text

SOURCE = "7k/6p1/8/8/1n6/8/7P/1R2K3 w - - 0 1"
PRE = "7k/6p1/8/8/1n6/8/P6P/1R2K3 b - - 0 1"


def created_fixture(path, monkeypatch, black=False):
    import sys

    board = chess.Board(SOURCE)
    best = ["b1b3", "h8g8", "e1f1", "g7g6"]
    played = ["b1a1", "b4c2", "e1f1", "c2a1"]
    if black:
        board = board.mirror()
        best, played = [list(map(mirror, line)) for line in (best, played)]
    game = chess.pgn.Game()
    game.setup(board)
    game.headers["White"] = "fixture_opponent" if black else LEARNER
    game.headers["Black"] = LEARNER if black else "fixture_opponent"
    game.headers["Result"] = "*"
    game.headers["UTCDate"] = "2026.01.01"
    game.headers["UTCTime"] = "12:00:00"
    node = game.add_variation(board.parse_uci(played[0]))
    board.push_uci(played[0])
    node.add_variation(board.parse_uci(played[1]))
    db = Database(path)
    db.initialize()
    ingest_pgn(db, str(game))
    monkeypatch.setattr(chess.engine.SimpleEngine, "popen_uci", lambda _: Engine(best, played))
    config = PipelineConfig(
        learner=LEARNER, engine_path=sys.executable, nodes=100, deep_enabled=False
    )
    assert (
        run_analysis(db, 1, game_input(db, 1), config, engine_identity(sys.executable))["status"]
        == "complete"
    )
    evidence = process_decision(db, 1, LEARNER)["evidence_ids"][0]
    candidate = chess.Board(PRE)
    line = ["g7g6", "b1b3", "h8g8", "e1f1"]
    if black:
        candidate = candidate.mirror()
        line = list(map(mirror, line))
    db.connection.execute(
        "INSERT INTO puzzle_corpora(version,source,checksum,state) VALUES('test','fixture','checksum','staging')"
    )
    corpus = db.connection.execute("SELECT id FROM puzzle_corpora WHERE version='test'").fetchone()[
        0
    ]
    db.connection.execute(
        """INSERT INTO puzzles(puzzle_id,corpus_id,fen,source,solution,rating,rating_deviation,themes_json,objective)
        VALUES('fixture',?,?,'https://example.invalid',?,1200,80,'["fork"]','unknown')""",
        (corpus, candidate.fen(), " ".join(line)),
    )
    db.connection.execute("INSERT INTO puzzle_themes VALUES(?,?,'fork',1200)", (corpus, "fixture"))
    db.connection.execute("UPDATE puzzle_corpora SET state='ready' WHERE id=?", (corpus,))
    db.connection.commit()
    return db, evidence


@pytest.mark.parametrize("black", [False, True])
def test_created_fork_reaches_playable_concealed_session(tmp_path, monkeypatch, black):
    db, evidence = created_fixture(tmp_path / "created.sqlite", monkeypatch, black)
    result = preview(db, LEARNER, evidence, "test")
    assert result["status"] == "available" and len(result["items"]) == 1
    item = result["items"][0]
    assert "created_witness" not in item
    move = mirror("b1b3") if black else "b1b3"
    assert move not in preview_text(result, selection(db, LEARNER, evidence, "test"))
    before = learning_counts(db)
    state = start_related(
        db,
        attempt_id="fixture",
        subject=LEARNER,
        evidence_id=evidence,
        corpus_version="test",
        reference=item["reference"],
    )
    assert state["related_fork_avoidance"] is True
    result = submit(db, "fixture", LEARNER, event_id="move", move=move)
    assert result["feedback"] == "line_match"
    assert learning_counts(db) == before
    db.close()
