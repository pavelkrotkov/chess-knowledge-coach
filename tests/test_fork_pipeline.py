"""Fork processing preserves review and narrowly qualified eligibility."""

import sys
from datetime import UTC, datetime

import chess
import chess.engine
import chess.pgn
import httpx

from chess_coach.db import Database
from chess_coach.evidence_review import inspect_evidence, review_evidence
from chess_coach.fork_detector import process_decision
from chess_coach.ingest import ingest_pgn
from chess_coach.mastery_eligibility import eligible_contexts
from chess_coach.pipeline import process_pipeline
from chess_coach.pipeline_config import PipelineConfig
from chess_coach.pipeline_inputs import engine_identity, game_input
from chess_coach.pipeline_work import run_analysis
from chess_coach.web import create_app

LEARNER = "fixture_learner"


class Engine:
    def __init__(self):
        self.id = {"name": "synthetic"}
        self.options = {}

    def configure(self, settings):
        pass

    def analyse(self, board, limit, multipv, root_moves=None):
        if not board.move_stack:
            missed = root_moves and root_moves[0].uci() == "h1g1"
            moves = ["h1g1", "e8f8", "b5c7", "h7h6"] if missed else ["b5c7", "e8f8", "c7a8", "h7h6"]
            score = 0 if missed else 600
            pv = [chess.Move.from_uci(move) for move in moves]
        else:
            pv = [root_moves[0] if root_moves else next(iter(board.legal_moves))]
            score = 0
        return [
            {
                "score": chess.engine.PovScore(chess.engine.Cp(score), board.turn),
                "pv": pv,
                "nodes": 100,
                "depth": 5,
            }
        ]

    def quit(self):
        pass


def make_game(path, monkeypatch, played="h1g1"):
    board = chess.Board("r3k3/7p/8/1N6/8/8/6P1/7K w - - 0 1")
    game = chess.pgn.Game()
    game.setup(board)
    game.headers["White"] = LEARNER
    game.headers["Black"] = "fixture_opponent"
    game.headers["Result"] = "*"
    game.headers["UTCDate"] = "2026.01.01"
    game.headers["UTCTime"] = "12:00:00"
    node = game.add_variation(board.parse_uci(played))
    board.push_uci(played)
    node.add_variation(board.parse_uci("e8f8"))
    db = Database(path)
    db.initialize()
    ingest_pgn(db, str(game))
    monkeypatch.setattr(chess.engine.SimpleEngine, "popen_uci", lambda _: Engine())
    config = PipelineConfig(
        learner=LEARNER, engine_path=sys.executable, nodes=100, deep_enabled=False
    )
    result = run_analysis(db, 1, game_input(db, 1), config, engine_identity(sys.executable))
    assert result["status"] == "complete"
    return db, config


def test_fork_source_replay_review_and_eligibility(tmp_path, monkeypatch):
    db, _ = make_game(tmp_path / "fork.sqlite", monkeypatch)
    first = process_decision(db, 1, LEARNER)
    assert first["outcome"] == "failure"
    evidence_id = first["evidence_ids"][0]
    evidence = inspect_evidence(db, evidence_id)
    assert (
        evidence["review_status"] == "unreviewed"
        and evidence["fork_source_currentness"] == "current"
    )
    review_evidence(db, evidence_id, decision="accept", actor="fixture_reviewer")
    from chess_coach import fork_detector

    original = fork_detector.observe
    monkeypatch.setattr(
        fork_detector, "observe", lambda *args: (_ for _ in ()).throw(AssertionError("proof reran"))
    )
    replay = process_decision(db, 1, LEARNER)
    monkeypatch.setattr(fork_detector, "observe", original)
    assert replay["replayed"] and replay["evidence_ids"] == [evidence_id]
    eligible, excluded = eligible_contexts(db, LEARNER, "fork", "execute", datetime.now(UTC))
    assert len(eligible) == 1 and eligible[0]["outcome"] == "failure" and not excluded
    db.connection.execute(
        "UPDATE decision_analysis_lines SET score_value=score_value+1 WHERE position_id=1 AND role=?",
        ("best",),
    )
    db.connection.commit()
    assert inspect_evidence(db, evidence_id)["fork_source_currentness"] == "stale"
    eligible, excluded = eligible_contexts(db, LEARNER, "fork", "execute", datetime.now(UTC))
    assert not eligible and excluded["fork_family_unvalidated"] == 1
    second = process_decision(db, 1, LEARNER)
    assert second["evidence_ids"] != [evidence_id]
    assert inspect_evidence(db, evidence_id)["review_status"] == "accepted"
    assert inspect_evidence(db, evidence_id)["lifecycle_status"] == "superseded"


def test_automatic_worker_and_private_browser_show_source_fork(tmp_path, monkeypatch):
    path = tmp_path / "worker.sqlite"
    db, config = make_game(path, monkeypatch)
    report = process_pipeline(
        db, config, transport=httpx.MockTransport(lambda request: httpx.Response(200))
    )
    assert report["forks"]["outcomes"]["failure"] == 1
    row = db.connection.execute(
        "SELECT id FROM evidence_mappings WHERE skill=?", ("fork",)
    ).fetchone()
    app = create_app(
        db_path=path,
        subject=LEARNER,
        actor="fixture_reviewer",
        corpus="test",
        login="fixture-login",
        origin="https://coach.invalid",
    )
    page = app.test_client().get(
        f"/evidence/{row['id']}",
        base_url="https://coach.invalid",
        headers={"Tailscale-User-Login": "fixture-login"},
    )
    assert page.status_code == 200
    assert b"Fork source: current" in page.data and b"Nc7+" in page.data
    assert b"Provisional bounded observation" in page.data and b"Source position" in page.data
