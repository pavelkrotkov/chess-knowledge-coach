"""Synthetic tests of legal king-safety observations and source lifecycle."""

import sys
from dataclasses import replace
from datetime import UTC, datetime

import chess
import chess.engine
import chess.pgn

from chess_coach.db import Database
from chess_coach.evidence_review import inspect_evidence, review_evidence
from chess_coach.ingest import ingest_pgn
from chess_coach.king_safety_probe import state
from chess_coach.king_safety_publish import publish
from chess_coach.king_safety_source import prepare_lesson
from chess_coach.king_safety_worker import process_king_safety_lessons
from chess_coach.lesson_decision import lessons
from chess_coach.mastery_eligibility import eligible_contexts
from chess_coach.pipeline_config import PipelineConfig
from chess_coach.pipeline_inputs import engine_identity, game_input
from chess_coach.pipeline_work import run_analysis

CASTLE = "r3k2r/8/8/8/8/8/5PPP/R3K2R w KQkq - 0 1"


class Engine:
    def __init__(self):
        self.id = {"name": "Synthetic"}
        self.options = {}

    def configure(self, settings):
        pass

    def analyse(self, board, limit, multipv, root_moves=None):
        root = root_moves[0] if root_moves else next(iter(board.legal_moves))
        after = board.copy()
        after.push(root)
        moves = [root]
        if not after.is_game_over():
            moves.append(next(iter(after.legal_moves)))
        return [
            {
                "score": chess.engine.PovScore(chess.engine.Cp(0), board.turn),
                "pv": moves,
                "nodes": 100,
                "depth": 5,
            }
        ]

    def quit(self):
        pass


def test_worker_replay_review_lessons_and_mastery_gate(tmp_path, monkeypatch):
    board = chess.Board(CASTLE)
    game = chess.pgn.Game()
    game.setup(board)
    game.headers.update(
        {
            "White": "fixture_learner",
            "Black": "fixture_opponent",
            "UTCDate": "2026.01.01",
            "UTCTime": "12:00:00",
        }
    )
    game.add_variation(board.parse_uci("e1g1"))
    db = Database(tmp_path / "fixture.sqlite")
    db.initialize()
    ingest_pgn(db, str(game))
    monkeypatch.setattr(chess.engine.SimpleEngine, "popen_uci", lambda _: Engine())
    config = PipelineConfig(learner="fixture_learner", engine_path=sys.executable, nodes=100)
    assert (
        run_analysis(db, 1, game_input(db, 1), config, engine_identity(sys.executable))["status"]
        == "complete"
    )
    pending = process_king_safety_lessons(db, replace(config, material_max_decisions=0))
    assert pending["pending"] and pending["attempted"] == 0 and not pending["scan_limited"]
    prepared, fact = prepare_lesson(db, 1, "fixture_learner")
    first = publish(db, prepared, fact)
    evidence_id = first["mapping"]["evidence_ids"][0]
    assert state(db, 1, "fixture_learner") == "current"
    assert inspect_evidence(db, evidence_id)["king_safety_currentness"] == "current"
    assert process_king_safety_lessons(db, config)["replayed"] == 1
    assert publish(db, prepared, fact)["mapping"]["evidence_ids"] == [evidence_id]
    saved = db.connection.execute(
        "SELECT payload_json FROM detector_facts WHERE id=?", (first["fact_ids"][0],)
    ).fetchone()[0]
    db.connection.execute(
        "UPDATE detector_facts SET payload_json=? WHERE id=?", ("{}", first["fact_ids"][0])
    )
    db.connection.commit()
    assert state(db, 1, "fixture_learner") == "needed"
    assert inspect_evidence(db, evidence_id)["king_safety_currentness"] == "stale"
    db.connection.execute(
        "UPDATE detector_facts SET payload_json=? WHERE id=?", (saved, first["fact_ids"][0])
    )
    db.connection.commit()
    review_evidence(db, evidence_id, decision="accept", actor="fixture")
    eligible, excluded = eligible_contexts(
        db, "fixture_learner", "king_safety", "evaluate", datetime(2026, 2, 1, tzinfo=UTC)
    )
    assert not eligible and excluded
    rendered = lessons(db, "fixture_learner", 1)
    item = next(item for item in rendered if item["family"] == "king-safety-lesson-mapper")
    assert item["examples"][0]["played"] == "O-O"
    assert any("legal alternative" in text.lower() for text in item["examples"][0]["facts"])
