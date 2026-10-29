"""Versioned pin evidence preserves reviewed history across a detector correction."""

import sys
from dataclasses import replace

import chess
import chess.engine
import chess.pgn
import pytest

from chess_coach import pin_pipeline, pin_proof
from chess_coach.db import Database
from chess_coach.evidence_review import inspect_evidence, review_evidence
from chess_coach.fork_worker_cursor import scan
from chess_coach.ingest import ingest_pgn
from chess_coach.pin_worker import process_pins
from chess_coach.pipeline_config import PipelineConfig
from chess_coach.pipeline_cursor import save_cursor
from chess_coach.pipeline_inputs import engine_identity, game_input
from chess_coach.pipeline_work import run_analysis

FEN = "4r2k/b1p5/Bpnppppp/8/8/8/8/7K w - - 0 1"
CYCLE = ("h1g1", "h8g8", "g1h1", "g8h8")


def position(mirror, cycles):
    board = chess.Board(FEN)
    if mirror:
        board = board.mirror()
    for text in CYCLE * cycles:
        move = chess.Move.from_uci(text)
        if mirror:
            move = chess.Move(
                chess.square_mirror(move.from_square), chess.square_mirror(move.to_square)
            )
        board.push(move)
    move = chess.Move.from_uci("a6b5")
    if mirror:
        move = chess.Move(
            chess.square_mirror(move.from_square), chess.square_mirror(move.to_square)
        )
    return board, move


class Engine:
    def __init__(self):
        self.id = {"name": "synthetic"}
        self.options = {}

    def configure(self, settings):
        pass

    def analyse(self, board, limit, multipv, root_moves=None):
        move = root_moves[0] if root_moves else next(iter(board.legal_moves))
        return [
            {
                "score": chess.engine.PovScore(chess.engine.Cp(0), board.turn),
                "pv": [move],
                "nodes": 100,
                "depth": 5,
            }
        ]

    def quit(self):
        pass


def _game(board, move):
    initial = board.root()
    game = chess.pgn.Game()
    game.setup(initial)
    game.headers.update(
        {
            "White": "fixture_learner" if initial.turn == chess.WHITE else "fixture_opponent",
            "Black": "fixture_learner" if initial.turn == chess.BLACK else "fixture_opponent",
            "Result": "*",
            "UTCDate": "2026.01.01",
            "UTCTime": "12:00:00",
        }
    )
    node = game
    for step in [*board.move_stack, move]:
        node = node.add_variation(step)
    return game


@pytest.mark.parametrize("mirror", [False, True])
@pytest.mark.parametrize("cycles", [2, 4])
def test_old_accepted_repetition_evidence_is_stale_and_reprocessed(
    tmp_path, monkeypatch, mirror, cycles
):
    board, move = position(mirror, cycles)
    db = Database(tmp_path / "history.sqlite")
    db.initialize()
    ingest_pgn(db, str(_game(board, move)))
    monkeypatch.setattr(chess.engine.SimpleEngine, "popen_uci", lambda _: Engine())
    config = PipelineConfig(
        learner="fixture_learner", engine_path=sys.executable, nodes=100, deep_enabled=False
    )
    assert (
        run_analysis(db, 1, game_input(db, 1), config, engine_identity(sys.executable))["status"]
        == "complete"
    )
    row = db.connection.execute(
        "SELECT id FROM positions WHERE game_id=? AND ply=?", (1, len(board.move_stack) + 1)
    ).fetchone()
    position_id = row["id"]
    actual_eligible = pin_proof.eligible
    current_version = pin_pipeline.VERSION
    monkeypatch.setattr(pin_pipeline, "VERSION", "1.0.0")
    monkeypatch.setattr(
        pin_proof,
        "eligible",
        lambda source, played: (
            not (
                source.is_check()
                or source.ep_square is not None
                or source.gives_check(played)
                or source.is_capture(played)
                or played.promotion
            )
        ),
    )
    old = pin_pipeline.process_decision(db, position_id, "fixture_learner", "execute")
    assert old["outcome"] == "success"
    old_id = old["evidence_ids"][0]
    review_evidence(db, old_id, decision="accept", actor="fixture_reviewer")
    monkeypatch.setattr(pin_pipeline, "VERSION", current_version)
    monkeypatch.setattr(pin_proof, "eligible", actual_eligible)
    assert inspect_evidence(db, old_id)["pin_source_currentness"] == "stale"
    policy = "pin-execute-worker-v1"
    key, _ = scan(db, "fixture_learner", 1, namespace="pin-execute-cursor-v1:", policy=policy)
    save_cursor(db, key, position_id - 1, policy)
    report = process_pins(
        db, replace(config, material_max_scan=1, material_max_decisions=1), "execute"
    )
    assert report["processed"] == 1 and report["replayed"] == 0
    assert report["outcomes"] == {"ambiguous": 1}
    fresh = pin_pipeline.process_decision(db, position_id, "fixture_learner", "execute")
    assert fresh["replayed"] and fresh["outcome"] == "ambiguous"
    assert fresh["evidence_ids"] != old["evidence_ids"]
    historic = inspect_evidence(db, old_id)
    assert historic["review_status"] == "accepted" and historic["lifecycle_status"] == "superseded"
    assert historic["facts"][0]["detector_version"] == "1.0.0"
    current = inspect_evidence(db, fresh["evidence_ids"][0])
    assert (
        current["review_status"] == "unreviewed" and current["pin_source_currentness"] == "current"
    )
    assert current["mapper_version"] == current_version
    assert current["facts"][0]["detector_version"] == current_version
    assert pin_pipeline.process_decision(db, position_id, "fixture_learner", "execute")["replayed"]
