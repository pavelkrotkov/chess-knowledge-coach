"""Synthetic material evidence retains current provenance and review boundaries."""

import sys
from datetime import UTC, datetime

import chess
import chess.engine
import chess.pgn
import pytest

from chess_coach.db import Database
from chess_coach.evidence_review import inspect_evidence, review_evidence
from chess_coach.ingest import ingest_pgn
from chess_coach.mastery_eligibility import eligible_contexts
from chess_coach.material_detector import process_decision
from chess_coach.material_observation import material_observation
from chess_coach.material_publish import publish
from chess_coach.material_source import prepare
from chess_coach.pipeline_config import PipelineConfig
from chess_coach.pipeline_inputs import engine_identity, game_input
from chess_coach.pipeline_work import run_analysis

LEARNER = "fixture_learner"


class Engine:
    def __init__(self):
        self.id = {"name": "Synthetic"}
        self.options = {}

    def configure(self, settings):
        pass

    def analyse(self, board, limit, multipv, root_moves=None):
        if not board.move_stack:
            root = root_moves[0] if root_moves else chess.Move.from_uci("d1d4")
            continuation = board.copy()
            continuation.push(root)
            reply = chess.Move.from_uci("e8f8")
            assert reply in continuation.legal_moves
            score = 0 if root_moves else 500
            moves = [root, reply]
        else:
            moves = [root_moves[0] if root_moves else next(iter(board.legal_moves))]
            score = 0
        return [
            {
                "score": chess.engine.PovScore(chess.engine.Cp(score), board.turn),
                "pv": moves,
                "nodes": 100,
                "depth": 5,
            }
        ]

    def quit(self):
        pass


def make_game(path, monkeypatch, *, timed=True, played="e1f1"):
    board = chess.Board("4k3/8/8/8/3q4/8/8/3RK3 w - - 0 1")
    game = chess.pgn.Game()
    game.setup(board)
    game.headers["White"] = LEARNER
    game.headers["Black"] = "fixture_opponent"
    game.headers["Result"] = "*"
    if timed:
        game.headers["UTCDate"] = "2026.01.01"
        game.headers["UTCTime"] = "12:00:00"
    node = game.add_variation(board.parse_uci(played))
    board.push_uci(played)
    node.add_variation(board.parse_uci("e8f8"))
    db = Database(path)
    db.initialize()
    ingest_pgn(db, str(game))
    monkeypatch.setattr(chess.engine.SimpleEngine, "popen_uci", lambda _: Engine())
    config = PipelineConfig(learner=LEARNER, engine_path=sys.executable, nodes=100)
    result = run_analysis(db, 1, game_input(db, 1), config, engine_identity(sys.executable))
    assert result["status"] == "complete"
    return db


def test_unreviewed_observation_replays_and_never_enters_mastery(tmp_path, monkeypatch):
    db = make_game(tmp_path / "material.sqlite", monkeypatch)
    before = db.connection.execute("SELECT COUNT(*) FROM engine_outputs").fetchone()[0]
    result = process_decision(db, 1, LEARNER)
    assert result["outcome"] == "failure" and len(result["evidence_ids"]) == 1
    evidence_id = result["evidence_ids"][0]
    evidence = inspect_evidence(db, evidence_id)
    assert evidence["review_status"] == "unreviewed" and evidence["skill"] == "hanging_piece"
    assert evidence["context"]["material_observation"]["best"]["san"] == ["Rxd4", "Kf8"]
    review_evidence(db, evidence_id, decision="accept", actor="fixture_reviewer")
    replay = process_decision(db, 1, LEARNER)
    assert replay["replayed"] and replay["evidence_ids"] == [evidence_id]
    assert inspect_evidence(db, evidence_id)["review_status"] == "accepted"
    eligible, excluded = eligible_contexts(
        db, LEARNER, "hanging_piece", "execute", datetime.now(UTC)
    )
    assert len(eligible) == 1 and eligible[0]["outcome"] == "failure"
    assert not excluded
    assert db.connection.execute("SELECT COUNT(*) FROM engine_outputs").fetchone()[0] == before


def test_source_change_supersedes_without_deleting_review(tmp_path, monkeypatch):
    db = make_game(tmp_path / "changed.sqlite", monkeypatch)
    first = process_decision(db, 1, LEARNER)
    old = first["evidence_ids"][0]
    review_evidence(db, old, decision="accept", actor="fixture_reviewer")
    db.connection.execute(
        "UPDATE decision_analysis_lines SET score_value=score_value+1 WHERE position_id=1 AND role=?",
        ("best",),
    )
    db.connection.commit()
    second = process_decision(db, 1, LEARNER)
    assert second["evidence_ids"] != [old]
    assert inspect_evidence(db, old)["lifecycle_status"] == "superseded"
    assert inspect_evidence(db, old)["review_status"] == "accepted"
    assert inspect_evidence(db, second["evidence_ids"][0])["review_status"] == "unreviewed"


def test_atomic_publication_rejects_changed_source(tmp_path, monkeypatch):
    db = make_game(tmp_path / "race.sqlite", monkeypatch)
    prepared = prepare(db, 1, LEARNER)
    fact = material_observation(
        prepared["board"], prepared["context"]["played_move"], prepared["best"], prepared["played"]
    )
    db.connection.execute(
        "UPDATE decision_analysis_lines SET score_value=score_value+1 WHERE position_id=1 AND role=?",
        ("best",),
    )
    db.connection.commit()
    with pytest.raises(ValueError, match="source changed"):
        publish(db, prepared, fact)
    assert (
        db.connection.execute(
            "SELECT COUNT(*) FROM detector_runs WHERE producer=?", ("material-opportunity",)
        ).fetchone()[0]
        == 0
    )
    assert not db.connection.in_transaction


def test_automatic_worker_records_provisional_material_and_browser_explains(tmp_path, monkeypatch):
    import httpx

    from chess_coach import material_detector
    from chess_coach.pipeline import process_pipeline
    from chess_coach.web import create_app

    path = tmp_path / "worker.sqlite"
    db = make_game(path, monkeypatch)
    original = material_detector.material_observation
    calls = []

    def observe(*args):
        assert not db.connection.in_transaction
        calls.append(True)
        return original(*args)

    monkeypatch.setattr(material_detector, "material_observation", observe)
    config = PipelineConfig(
        learner=LEARNER,
        engine_path=sys.executable,
        nodes=100,
        deep_enabled=False,
        material_max_decisions=1,
    )
    network = httpx.MockTransport(lambda request: httpx.Response(200, text=""))
    result = process_pipeline(db, config, transport=network)
    assert calls and result["material"]["processed"] == 1
    assert result["material"]["outcomes"]["failure"] == 1
    row = db.connection.execute(
        "SELECT id FROM evidence_mappings WHERE mapper_version=?", ("1.0.0",)
    ).fetchone()
    evidence_id = row["id"]
    app = create_app(
        db_path=path,
        subject=LEARNER,
        actor="fixture_reviewer",
        corpus="test",
        login="fixture-login",
        origin="https://coach.invalid",
    )
    client = app.test_client()
    page = client.get(
        f"/evidence/{evidence_id}",
        base_url="https://coach.invalid",
        headers={"Tailscale-User-Login": "fixture-login"},
    )
    assert page.status_code == 200
    assert b"tested best continuation captures material" in page.data
    assert b"Rxd4" in page.data and b"capture version 1.1.0" in page.data
    assert b"pawn-capture claims" in page.data and b"en passant" in page.data
    assert b"Material source: current" in page.data
    assert inspect_evidence(db, evidence_id)["review_status"] == "unreviewed"
    process_pipeline(db, config, transport=network)
    replay = process_pipeline(db, config, transport=network)
    assert replay["material"]["replayed"] == 1 and len(calls) == 1


@pytest.mark.skipif(
    not __import__("pathlib").Path("/usr/games/stockfish").is_file(),
    reason="Stockfish not installed",
)
def test_real_stockfish_bounded_worker_records_nonmate_observation(tmp_path):
    import httpx

    from chess_coach.pipeline import process_pipeline

    board = chess.Board("4k3/7p/8/8/3q4/8/P7/3RK3 w - - 0 1")
    game = chess.pgn.Game()
    game.setup(board)
    game.headers["White"] = LEARNER
    game.headers["Black"] = "fixture_opponent"
    game.headers["Result"] = "*"
    node = game.add_variation(board.parse_uci("e1f1"))
    board.push_uci("e1f1")
    node.add_variation(board.parse_uci("e8f8"))
    db = Database(tmp_path / "real.sqlite")
    db.initialize()
    ingest_pgn(db, str(game))
    config = PipelineConfig(
        learner=LEARNER,
        engine_path="/usr/games/stockfish",
        nodes=10000,
        seconds_per_position=1.0,
        deep_enabled=False,
        material_max_decisions=1,
    )
    result = process_pipeline(
        db, config, transport=httpx.MockTransport(lambda request: httpx.Response(200, text=""))
    )
    assert result["material"]["processed"] == 1
    row = db.connection.execute(
        "SELECT payload_json FROM detector_facts WHERE fact_type=?", ("material_opportunity",)
    ).fetchone()
    assert row is not None
    import json

    observation = json.loads(row["payload_json"])
    assert observation["kind"] in {"material_capture", "material_protection"}
    assert observation["outcome"] in {"success", "failure", "ambiguous"}


def make_protection_game(path, monkeypatch, *, timed=True, played="a2a3", color="white"):
    board = chess.Board("4k3/8/8/2b5/3R4/8/P7/7K w - - 0 1")

    def orient(uci):
        move = chess.Move.from_uci(uci)
        if color == "black":
            move = chess.Move(
                chess.square_mirror(move.from_square), chess.square_mirror(move.to_square)
            )
        return move.uci()

    if color == "black":
        board = board.mirror()
    game = chess.pgn.Game()
    game.setup(board)
    game.headers["White"] = LEARNER if color == "white" else "fixture_opponent"
    game.headers["Black"] = LEARNER if color == "black" else "fixture_opponent"
    game.headers["Result"] = "*"
    if timed:
        game.headers["UTCDate"] = "2026.01.01"
        game.headers["UTCTime"] = "12:00:00"
    node = game.add_variation(board.parse_uci(orient(played)))
    board.push_uci(orient(played))
    reply = "c5d4" if played == "a2a3" else "e8f8"
    node.add_variation(board.parse_uci(orient(reply)))

    class ProtectionEngine(Engine):
        def analyse(self, board, limit, multipv, root_moves=None):
            if board.move_stack:
                return [
                    {
                        "score": chess.engine.PovScore(chess.engine.Cp(0), board.turn),
                        "pv": [root_moves[0] if root_moves else next(iter(board.legal_moves))],
                        "nodes": 100,
                        "depth": 5,
                    }
                ]
            move = root_moves[0] if root_moves else chess.Move.from_uci(orient("d4d5"))
            reply = chess.Move.from_uci(orient("c5d4" if move.uci() == orient("a2a3") else "e8f8"))
            score = 0 if root_moves else 500
            return [
                {
                    "score": chess.engine.PovScore(chess.engine.Cp(score), board.turn),
                    "pv": [move, reply],
                    "nodes": 100,
                    "depth": 5,
                }
            ]

    db = Database(path)
    db.initialize()
    ingest_pgn(db, str(game))
    monkeypatch.setattr(chess.engine.SimpleEngine, "popen_uci", lambda _: ProtectionEngine())
    config = PipelineConfig(learner=LEARNER, engine_path=sys.executable, nodes=100)
    result = run_analysis(db, 1, game_input(db, 1), config, engine_identity(sys.executable))
    assert result["status"] == "complete"
    return db
