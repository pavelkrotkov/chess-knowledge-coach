"""Automatic fork-defense facts retain source lineage and stay ineligible."""

import sys
from datetime import UTC, datetime

import chess
import chess.engine
import chess.pgn
import httpx
import pytest

from chess_coach.db import Database
from chess_coach.evidence_review import inspect_evidence, review_evidence
from chess_coach.fork_defense_detector import process_decision
from chess_coach.ingest import ingest_pgn
from chess_coach.mastery_eligibility import eligible_contexts
from chess_coach.pipeline import process_pipeline
from chess_coach.pipeline_config import PipelineConfig
from chess_coach.pipeline_inputs import engine_identity, game_input
from chess_coach.pipeline_work import run_analysis
from chess_coach.web import create_app
from tests.test_fork_defense import mirror

LEARNER = "fixture_learner"


class Engine:
    def __init__(self, best, actual):
        self.id = {"name": "fixture"}
        self.options = {}
        self.best = best
        self.actual = actual

    def configure(self, settings):
        pass

    def analyse(self, board, limit, multipv, root_moves=None):
        if not board.move_stack:
            moves = self.actual if root_moves else self.best
            score = 0 if root_moves and self.actual[0] != self.best[0] else 500
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


def make_game(path, monkeypatch, *, black=False, failure=False):
    board = chess.Board("7k/6p1/8/8/1n6/8/7P/R3K3 w - - 0 1")
    best = ["a1b1", "h8g8", "e1f1", "g7g6"]
    actual = ["h2h3", "b4c2", "e1f1", "c2a1"] if failure else best[:]
    if black:
        board = board.mirror()
        best, actual = [list(map(mirror, moves)) for moves in (best, actual)]
    game = chess.pgn.Game()
    game.setup(board)
    game.headers["White"] = "fixture_opponent" if black else LEARNER
    game.headers["Black"] = LEARNER if black else "fixture_opponent"
    game.headers["Result"] = "*"
    game.headers["UTCDate"] = "2026.01.01"
    game.headers["UTCTime"] = "12:00:00"
    node = game.add_variation(board.parse_uci(actual[0]))
    board.push_uci(actual[0])
    node.add_variation(board.parse_uci(actual[1]))
    db = Database(path)
    db.initialize()
    ingest_pgn(db, str(game))
    monkeypatch.setattr(chess.engine.SimpleEngine, "popen_uci", lambda _: Engine(best, actual))
    config = PipelineConfig(
        learner=LEARNER,
        engine_path=sys.executable,
        nodes=100,
        deep_enabled=False,
        material_max_decisions=1,
    )
    assert (
        run_analysis(db, 1, game_input(db, 1), config, engine_identity(sys.executable))["status"]
        == "complete"
    )
    return db, config


@pytest.mark.parametrize("black", [False, True])
@pytest.mark.parametrize("failure", [False, True])
def test_worker_source_review_replay_and_private_explanation(tmp_path, monkeypatch, black, failure):
    path = tmp_path / "fork-defense.sqlite"
    db, config = make_game(path, monkeypatch, black=black, failure=failure)
    report = process_pipeline(
        db, config, transport=httpx.MockTransport(lambda request: httpx.Response(200))
    )
    outcome = "failure" if failure else "success"
    assert report["fork_defenses"]["outcomes"] == {outcome: 1}
    row = db.connection.execute(
        "SELECT id FROM evidence_mappings WHERE skill=? AND operation=?", ("fork", "prevent")
    ).fetchone()
    evidence_id = row["id"]
    evidence = inspect_evidence(db, evidence_id)
    assert (
        evidence["fork_defense_currentness"] == "current"
        and evidence["review_status"] == "unreviewed"
    )
    assert evidence["context"]["provenance"]["kind"] == "cheap"
    review_evidence(db, evidence_id, decision="accept", actor="fixture_reviewer")
    replay = process_decision(db, 1, LEARNER)
    assert replay["replayed"] and replay["evidence_ids"] == [evidence_id]
    eligible, excluded = eligible_contexts(db, LEARNER, "fork", "prevent", datetime.now(UTC))
    assert not eligible and excluded["fork_defense_family_unvalidated"] == 1
    from chess_coach.unified_own_game import VERSION
    from chess_coach.unified_sessions import start

    with pytest.raises(ValueError):
        start(
            db,
            attempt_id="closed",
            subject=LEARNER,
            source_type="own-game",
            version=VERSION,
            key=f"1:fork_defense:{evidence_id}",
        )
    app = create_app(
        db_path=path,
        subject=LEARNER,
        actor="fixture_reviewer",
        corpus="test",
        login="fixture-login",
        origin="https://coach.invalid",
    )
    page = app.test_client().get(
        f"/evidence/{evidence_id}",
        base_url="https://coach.invalid",
        headers={"Tailscale-User-Login": "fixture-login"},
    )
    assert page.status_code == 200 and b"Fork-defense source: current" in page.data
    assert b"standstill threat probe is positional" in page.data
    if failure:
        assert b"recorded fork" in page.data
    else:
        assert b"counterfactual line" in page.data
    db.connection.execute(
        "UPDATE decision_analysis_lines SET score_value=score_value+1 WHERE position_id=1 AND role=?",
        ("best",),
    )
    db.connection.commit()
    assert inspect_evidence(db, evidence_id)["fork_defense_currentness"] == "stale"
    new = process_decision(db, 1, LEARNER)
    assert new["evidence_ids"] != [evidence_id]
    old = inspect_evidence(db, evidence_id)
    assert old["lifecycle_status"] == "superseded" and old["review_status"] == "accepted"


def test_defense_fact_cannot_be_promoted_by_another_mapper(tmp_path, monkeypatch):
    from chess_coach.mapping_runs import record_mapping_run_in_transaction
    from chess_coach.mapping_transaction import mapping_transaction

    db, _ = make_game(tmp_path / "spoof.sqlite", monkeypatch)
    original = process_decision(db, 1, LEARNER)
    item = {
        "skill": "hanging_piece",
        "outcome": "success",
        "confidence": 0.5,
        "fact_ids": original["fact_ids"],
        "context": {},
        "observation_at": "2026-01-01T12:00:00+00:00",
    }
    with mapping_transaction(db):
        fake = record_mapping_run_in_transaction(
            db,
            position_id=1,
            producer="fixture_other_mapper",
            mapper_version="v1",
            subject=LEARNER,
            operation="execute",
            scope_key="spoof",
            input_data={},
            mappings=[item],
        )
    review_evidence(db, fake["evidence_ids"][0], decision="accept", actor="fixture_reviewer")
    eligible, excluded = eligible_contexts(
        db, LEARNER, "hanging_piece", "execute", datetime.now(UTC)
    )
    assert not eligible and excluded["fork_defense_family_unvalidated"] == 1


def test_defense_source_change_before_publish_is_atomic(tmp_path, monkeypatch):
    from chess_coach.fork_defense_detector import _fact_run
    from chess_coach.fork_defense_mapping import mapping
    from chess_coach.fork_defense_observation import observe
    from chess_coach.fork_publish import publish
    from chess_coach.material_source import prepare

    db, _ = make_game(tmp_path / "race.sqlite", monkeypatch)
    prepared = prepare(db, 1, LEARNER)
    fact = observe(
        prepared["board"], prepared["context"]["played_move"], prepared["best"], prepared["played"]
    )
    db.connection.execute(
        "UPDATE decision_analysis_lines SET score_value=score_value+1 WHERE position_id=1 AND role=?",
        ("best",),
    )
    db.connection.commit()
    with pytest.raises(ValueError, match="source changed"):
        publish(db, prepared, fact, fact_writer=_fact_run, mapping_writer=mapping)
    assert (
        db.connection.execute(
            "SELECT COUNT(*) FROM detector_runs WHERE producer=?", ("fork-defense",)
        ).fetchone()[0]
        == 0
    )
    assert not db.connection.in_transaction
