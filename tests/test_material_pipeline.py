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


def make_game(path, monkeypatch):
    board = chess.Board("4k3/8/8/8/3q4/8/8/3RK3 w - - 0 1")
    game = chess.pgn.Game()
    game.setup(board)
    game.headers["White"] = LEARNER
    game.headers["Black"] = "fixture_opponent"
    game.headers["Result"] = "*"
    game.headers["UTCDate"] = "2026.01.01"
    game.headers["UTCTime"] = "12:00:00"
    node = game.add_variation(board.parse_uci("e1f1"))
    board.push_uci("e1f1")
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
    assert eligible == [] and excluded["material_family_unvalidated"] == 1
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


def test_current_checkpoint_ignores_newer_unrelated_legacy_run(tmp_path, monkeypatch):
    db = make_game(tmp_path / "legacy.sqlite", monkeypatch)
    db.connection.execute(
        "INSERT INTO analysis_runs(game_id,engine,engine_version,config_json) VALUES(1,?,?,?)",
        ("legacy synthetic", "legacy synthetic", "{}"),
    )
    db.connection.commit()
    prepared = prepare(db, 1, LEARNER)
    assert prepared["provenance"]["kind"] == "cheap"
    assert prepared["provenance"]["run_id"] == prepared["cheap_run_id"] == 1
    assert process_decision(db, 1, LEARNER)["outcome"] == "failure"


def test_deep_current_attempt_replaces_cheap_provenance(tmp_path, monkeypatch):
    from chess_coach.deep_execution_config import DeepOptions
    from chess_coach.deep_execution_worker import run_deep
    from chess_coach.deep_selection import select_deep

    db = make_game(tmp_path / "deep.sqlite", monkeypatch)
    first = process_decision(db, 1, LEARNER)
    selected = select_deep(db, [1], learner=LEARNER, per_game=1, total=1)
    selection_id = selected["games"][0]["selection_id"]

    class Deep(Engine):
        def analyse(self, board, limit, multipv, root_moves=None):
            best = chess.Move.from_uci("d1d4")
            moves = root_moves or [best, *[m for m in board.legal_moves if m != best][:2]]
            result = []
            for move in moves:
                after = board.copy()
                after.push(move)
                reply = chess.Move.from_uci("e8f8")
                if reply not in after.legal_moves:
                    reply = next(iter(after.legal_moves))
                score = 0 if root_moves else 500
                result.append(
                    {
                        "score": chess.engine.PovScore(chess.engine.Cp(score), board.turn),
                        "pv": [move, reply],
                        "nodes": 100,
                        "depth": 5,
                        "time": 0.01,
                    }
                )
            return result

    monkeypatch.setattr(chess.engine.SimpleEngine, "popen_uci", lambda _, timeout: Deep())
    options = DeepOptions(engine_path=sys.executable, nodes=1000, seconds=0.5, max_jobs=1)
    result = run_deep(db, selection_id, learner=LEARNER, options=options)
    assert result["processed"][0]["status"] == "complete"
    prepared = prepare(db, 1, LEARNER)
    assert prepared["provenance"]["kind"] == "deep"
    second = process_decision(db, 1, LEARNER)
    assert second["outcome"] == "failure" and second["evidence_ids"] != first["evidence_ids"]
    evidence = inspect_evidence(db, second["evidence_ids"][0])
    assert evidence["context"]["provenance"]["run_id"] == prepared["provenance"]["run_id"]
    assert inspect_evidence(db, first["evidence_ids"][0])["lifecycle_status"] == "superseded"


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
    assert b"Rxd4" in page.data and b"awaiting independent validation" in page.data
    assert b"Pawn captures" in page.data and b"en passant" in page.data
    assert inspect_evidence(db, evidence_id)["review_status"] == "unreviewed"
    process_pipeline(db, config, transport=network)
    replay = process_pipeline(db, config, transport=network)
    assert replay["material"]["replayed"] == 1 and len(calls) == 1


def test_old_source_reactivation_creates_new_lineage_then_replays(tmp_path, monkeypatch):
    db = make_game(tmp_path / "reactivate.sqlite", monkeypatch)
    first = process_decision(db, 1, LEARNER)
    review_evidence(db, first["evidence_ids"][0], decision="accept", actor="fixture_reviewer")
    db.connection.execute(
        "UPDATE decision_analysis_lines SET score_value=score_value+1 WHERE position_id=1 AND role=?",
        ("best",),
    )
    db.connection.commit()
    process_decision(db, 1, LEARNER)
    db.connection.execute(
        "UPDATE decision_analysis_lines SET score_value=score_value-1 WHERE position_id=1 AND role=?",
        ("best",),
    )
    db.connection.commit()
    restored = process_decision(db, 1, LEARNER)
    assert restored["evidence_ids"] != first["evidence_ids"]
    replay = process_decision(db, 1, LEARNER)
    assert replay["replayed"] and replay["evidence_ids"] == restored["evidence_ids"]
    assert inspect_evidence(db, first["evidence_ids"][0])["review_status"] == "accepted"
    assert inspect_evidence(db, restored["evidence_ids"][0])["review_status"] == "unreviewed"


def test_automatic_worker_attributes_black_learner_decision(tmp_path, monkeypatch):
    import httpx

    from chess_coach.pipeline import process_pipeline

    board = chess.Board("3rk3/8/8/3Q4/8/8/8/4K3 b - - 0 1")
    game = chess.pgn.Game()
    game.setup(board)
    game.headers["White"] = "fixture_opponent"
    game.headers["Black"] = LEARNER
    game.headers["Result"] = "*"
    node = game.add_variation(board.parse_uci("e8f8"))
    board.push_uci("e8f8")
    node.add_variation(board.parse_uci("e1f1"))
    db = Database(tmp_path / "black.sqlite")
    db.initialize()
    ingest_pgn(db, str(game))

    class BlackEngine(Engine):
        def analyse(self, board, limit, multipv, root_moves=None):
            if not board.move_stack:
                root = root_moves[0] if root_moves else chess.Move.from_uci("d8d5")
                score = 0 if root_moves else 500
                moves = [root, chess.Move.from_uci("e1f1")]
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

    monkeypatch.setattr(chess.engine.SimpleEngine, "popen_uci", lambda _: BlackEngine())
    config = PipelineConfig(
        learner=LEARNER,
        engine_path=sys.executable,
        nodes=100,
        deep_enabled=False,
        material_max_decisions=1,
    )
    network = httpx.MockTransport(lambda request: httpx.Response(200, text=""))
    result = process_pipeline(db, config, transport=network)
    assert result["material"]["outcomes"] == {"failure": 1}
    evidence = db.connection.execute(
        "SELECT position_id,subject FROM evidence_mappings WHERE skill=?", ("hanging_piece",)
    ).fetchone()
    assert evidence["position_id"] == 1 and evidence["subject"] == LEARNER


def test_private_opportunity_contract_rechecks_owner_source_and_witness(tmp_path, monkeypatch):
    from chess_coach import material_opportunities, material_opportunity_view

    db = make_game(tmp_path / "contract.sqlite", monkeypatch)
    created = process_decision(db, 1, LEARNER)
    evidence_id = created["evidence_ids"][0]
    detail = material_opportunities.inspect_material_opportunity(db, evidence_id, learner=LEARNER)
    assert detail["currentness"] == "current" and detail["learner_color"] == "white"
    assert detail["objective"] == {
        "kind": "material_capture",
        "target": "d4",
        "target_piece": "queen",
    }
    assert detail["objective_witness"]["uci"][0] == "d1d4"
    assert detail["lineage"]["fact_id"] == created["fact_ids"][0]
    assert detail["lineage"]["analysis"]["kind"] == "cheap"
    assert not detail["eligible_for_exercise_candidate"] and not detail["family_validated"]
    monkeypatch.setattr(
        material_opportunity_view, "MASTERY_ELIGIBLE_VERSIONS", frozenset({"1.0.0"})
    )
    eligible = material_opportunities.inspect_material_opportunity(db, evidence_id, learner=LEARNER)
    assert eligible["eligible_for_exercise_candidate"]
    review_evidence(db, evidence_id, decision="reject", actor="fixture_reviewer")
    rejected = material_opportunities.inspect_material_opportunity(db, evidence_id, learner=LEARNER)
    assert (
        rejected["review_status"] == "rejected" and not rejected["eligible_for_exercise_candidate"]
    )
    with pytest.raises(ValueError, match="unavailable"):
        material_opportunities.inspect_material_opportunity(
            db, evidence_id, learner="fixture_opponent"
        )
    db.connection.execute(
        "UPDATE decision_analysis_lines SET score_value=score_value+1 WHERE position_id=1 AND role=?",
        ("best",),
    )
    db.connection.commit()
    stale = material_opportunities.inspect_material_opportunity(db, evidence_id, learner=LEARNER)
    assert stale["currentness"] == "stale" and not stale["eligible_for_exercise_candidate"]


def test_material_gate_follows_detector_facts_across_mapper_scopes(tmp_path, monkeypatch):
    from chess_coach.mapping_runs import record_mapping_run_in_transaction
    from chess_coach.mapping_transaction import mapping_transaction

    db = make_game(tmp_path / "gate.sqlite", monkeypatch)
    created = process_decision(db, 1, LEARNER)
    fact_id = created["fact_ids"][0]
    item = {
        "skill": "hanging_piece",
        "outcome": "failure",
        "confidence": 0.5,
        "fact_ids": [fact_id],
        "context": {},
        "observation_at": "2026-01-01T12:00:00+00:00",
    }
    with mapping_transaction(db):
        remapped = record_mapping_run_in_transaction(
            db,
            position_id=1,
            producer="fixture_other_mapper",
            mapper_version="fixture",
            subject=LEARNER,
            operation="prevent",
            scope_key="fixture",
            input_data={},
            mappings=[item],
        )
    review_evidence(db, remapped["evidence_ids"][0], decision="accept", actor="fixture_reviewer")
    eligible, excluded = eligible_contexts(
        db, LEARNER, "hanging_piece", "prevent", datetime.now(UTC)
    )
    assert eligible == [] and excluded["material_family_unvalidated"] == 1


def test_even_approved_material_evidence_is_excluded_when_source_changes(tmp_path, monkeypatch):
    from chess_coach import material_policy
    from chess_coach.mastery_checks import basic_reason
    from chess_coach.mastery_sources import evidence_rows

    db = make_game(tmp_path / "currentness.sqlite", monkeypatch)
    created = process_decision(db, 1, LEARNER)
    review_evidence(db, created["evidence_ids"][0], decision="accept", actor="fixture_reviewer")
    monkeypatch.setattr(material_policy, "MASTERY_ELIGIBLE_VERSIONS", frozenset({"1.0.0"}))
    row = evidence_rows(db, LEARNER, "hanging_piece", "execute")[0]
    assert basic_reason(db, row, LEARNER) is None
    db.connection.execute(
        "UPDATE decision_analysis_lines SET score_value=score_value+1 WHERE position_id=1 AND role=?",
        ("best",),
    )
    db.connection.commit()
    row = evidence_rows(db, LEARNER, "hanging_piece", "execute")[0]
    assert basic_reason(db, row, LEARNER) == "material_source_stale"


def test_opportunity_accessor_fails_closed_when_source_changes_during_verification(
    tmp_path, monkeypatch
):
    from chess_coach import material_opportunity_current
    from chess_coach.material_opportunities import inspect_material_opportunity

    db = make_game(tmp_path / "read-race.sqlite", monkeypatch)
    result = process_decision(db, 1, LEARNER)
    original = material_opportunity_current.verified_witness

    def change_after(prepared, fact):
        witness = original(prepared, fact)
        db.connection.execute(
            "UPDATE decision_analysis_lines SET score_value=score_value+1 WHERE position_id=1 AND role=?",
            ("best",),
        )
        db.connection.commit()
        return witness

    monkeypatch.setattr(material_opportunity_current, "verified_witness", change_after)
    view = inspect_material_opportunity(db, result["evidence_ids"][0], learner=LEARNER)
    assert view["currentness"] == "stale" and not view["eligible_for_exercise_candidate"]


def test_material_history_limit_is_checked_before_reconstruction(tmp_path, monkeypatch):
    from chess_coach import material_source

    db = make_game(tmp_path / "history-limit.sqlite", monkeypatch)
    monkeypatch.setattr(material_source, "MAX_DECISIONS", 1)
    monkeypatch.setattr(
        material_source,
        "context_for_position",
        lambda *args: pytest.fail("history should not be reconstructed"),
    )
    with pytest.raises(ValueError, match="exceeds material"):
        material_source.prepare(db, 1, LEARNER)


def test_analysis_handoff_rejects_material_history_even_without_deep_selection(
    tmp_path, monkeypatch
):
    from chess_coach.analysis import merge_analysis_outputs

    source = make_game(tmp_path / "source.sqlite", monkeypatch)
    process_decision(source, 1, LEARNER)
    assert source.connection.execute("SELECT COUNT(*) FROM deep_selection_runs").fetchone()[0] == 0
    target = Database(tmp_path / "target.sqlite")
    target.initialize()
    with pytest.raises(ValueError, match="material history"):
        merge_analysis_outputs(target, source)
    assert target.connection.execute("SELECT COUNT(*) FROM analysis_runs").fetchone()[0] == 0


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
