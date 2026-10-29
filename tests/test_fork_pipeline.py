"""Fork processing preserves review and narrowly qualified eligibility."""

import sys
from datetime import UTC, datetime

import chess
import chess.engine
import chess.pgn
import httpx
import pytest

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


def test_fork_publication_rejects_changed_source_atomically(tmp_path, monkeypatch):
    import pytest

    from chess_coach.fork_observation import observe
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
        publish(db, prepared, fact)
    assert (
        db.connection.execute(
            "SELECT COUNT(*) FROM detector_runs WHERE producer=?", ("fork-opportunity",)
        ).fetchone()[0]
        == 0
    )
    assert not db.connection.in_transaction


def test_fork_source_gate_cannot_be_bypassed_by_another_mapper(tmp_path, monkeypatch):
    from chess_coach.mapping_runs import record_mapping_run_in_transaction
    from chess_coach.mapping_transaction import mapping_transaction

    db, _ = make_game(tmp_path / "spoof.sqlite", monkeypatch)
    original = process_decision(db, 1, LEARNER)
    item = {
        "skill": "hanging_piece",
        "outcome": "failure",
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
    assert not eligible and excluded["fork_family_unvalidated"] == 1


def test_fork_explanation_uses_source_fact_and_reconstructed_board(tmp_path, monkeypatch):
    import json

    db, _ = make_game(tmp_path / "context.sqlite", monkeypatch)
    result = process_decision(db, 1, LEARNER)
    evidence_id = result["evidence_ids"][0]
    context = json.loads(
        db.connection.execute(
            "SELECT context_json FROM evidence_mappings WHERE id=?", (evidence_id,)
        ).fetchone()[0]
    )
    context["pre_move_fen"] = chess.STARTING_FEN
    context["fork_observation"]["proof"]["san"] = "fabricated"
    db.connection.execute(
        "UPDATE evidence_mappings SET context_json=? WHERE id=?", (json.dumps(context), evidence_id)
    )
    db.connection.commit()
    view = inspect_evidence(db, evidence_id)
    assert view["fork_source_currentness"] == "current"
    assert view["fork_explanation"]["move"] == "Nc7+"
    assert view["decision_fen"] == "r3k3/7p/8/1N6/8/8/6P1/7K w - - 0 1"


def test_prior_no_opportunity_version_is_recomputed(tmp_path, monkeypatch):
    from chess_coach import fork_detector

    db, _ = make_game(tmp_path / "version.sqlite", monkeypatch)
    original = fork_detector.observe
    monkeypatch.setattr(fork_detector, "observe", lambda *args: None)
    prior = process_decision(db, 1, LEARNER)
    assert prior["outcome"] == "no_opportunity" and not prior["fact_ids"]
    db.connection.execute(
        "UPDATE detector_runs SET detector_version=? WHERE id=?",
        ("1.0.0", prior["detector_run_id"]),
    )
    db.connection.commit()
    monkeypatch.setattr(fork_detector, "observe", original)
    current = process_decision(db, 1, LEARNER)
    assert current["outcome"] == "failure" and current["fact_ids"]
    assert not current["replayed"] and current["detector_run_id"] != prior["detector_run_id"]


def test_reviewed_current_success_and_revocation(tmp_path, monkeypatch):
    db, _ = make_game(tmp_path / "success.sqlite", monkeypatch, played="b5c7")
    result = process_decision(db, 1, LEARNER)
    assert result["outcome"] == "success"
    evidence_id = result["evidence_ids"][0]
    eligible, excluded = eligible_contexts(db, LEARNER, "fork", "execute", datetime.now(UTC))
    assert not eligible and excluded["unreviewed_or_invalid_review"] == 1
    review_evidence(db, evidence_id, decision="accept", actor="fixture_reviewer")
    eligible, _ = eligible_contexts(db, LEARNER, "fork", "execute", datetime.now(UTC))
    assert len(eligible) == 1 and eligible[0]["outcome"] == "success"
    review_evidence(db, evidence_id, decision="revoke", actor="fixture_reviewer")
    eligible, excluded = eligible_contexts(db, LEARNER, "fork", "execute", datetime.now(UTC))
    assert not eligible and excluded["revoked"] == 1


@pytest.mark.parametrize(
    "change",
    [
        "UPDATE evidence_mappings SET mapper_version='1.0.0'",
        "UPDATE mapping_runs SET mapper_version='1.0.0' WHERE producer='fork-opportunity-mapper'",
        "UPDATE detector_facts SET detector_version='1.0.0' WHERE fact_type='fork_opportunity'",
        "UPDATE detector_runs SET detector_version='1.0.0' WHERE producer='fork-opportunity'",
        "UPDATE mapping_runs SET producer='spoof' WHERE producer='fork-opportunity-mapper'",
        "UPDATE detector_runs SET producer='spoof' WHERE producer='fork-opportunity'",
        "UPDATE detector_facts SET fact_type='spoof' WHERE fact_type='fork_opportunity'",
        "UPDATE evidence_mappings SET outcome='success' WHERE skill='fork'",
        "UPDATE detector_facts SET payload_json=json_set(payload_json, '$.proof.move', 'h1g1') WHERE fact_type='fork_opportunity'",
    ],
)
def test_fork_mastery_rejects_spoofed_source_or_version(tmp_path, monkeypatch, change):
    db, _ = make_game(tmp_path / "spoof-source.sqlite", monkeypatch)
    evidence_id = process_decision(db, 1, LEARNER)["evidence_ids"][0]
    review_evidence(db, evidence_id, decision="accept", actor="fixture_reviewer")
    eligible, _ = eligible_contexts(db, LEARNER, "fork", "execute", datetime.now(UTC))
    assert len(eligible) == 1
    db.connection.execute(change)
    db.connection.commit()
    eligible, excluded = eligible_contexts(db, LEARNER, "fork", "execute", datetime.now(UTC))
    assert not eligible and excluded["fork_family_unvalidated"] == 1


@pytest.mark.parametrize(
    ("fen", "move", "allowed"),
    [
        ("r3k3/7p/8/1N6/8/8/6P1/7K w - - 0 1", "b5c7", True),
        ("8/p6R/3r1k2/8/2N1P3/1B6/2B5/K7 w - - 0 1", "e4e5", True),
        ("8/7k/2p3b1/K7/8/1Q6/6r1/8 w - - 0 1", "b3h3", False),
        ("2k2N2/BN6/B1n1n2p/5B2/2K5/8/8/2R5 w - - 0 1", "c4d5", False),
        ("r3k3/2p4p/8/1N6/8/8/6P1/7K w - - 0 1", "b5c7", False),
        ("1r6/6Pk/8/8/8/8/8/K7 w - - 0 1", "g7g8q", False),
        ("7k/2r1r3/8/3pP3/8/8/8/K7 w - d6 0 1", "e5d6", False),
    ],
)
def test_fork_mastery_root_restrictions(fen, move, allowed):
    from chess_coach.fork_mastery_root import supported_root

    assert supported_root(fen, {"proof": {"move": move}}) is allowed


def test_renamed_game_fork_source_cannot_bypass_policy(tmp_path, monkeypatch):
    db, _ = make_game(tmp_path / "renamed.sqlite", monkeypatch)
    evidence_id = process_decision(db, 1, LEARNER)["evidence_ids"][0]
    review_evidence(db, evidence_id, decision="accept", actor="fixture_reviewer")
    db.connection.execute(
        "UPDATE mapping_runs SET producer='other' WHERE producer='fork-opportunity-mapper'"
    )
    db.connection.execute(
        "UPDATE detector_runs SET producer='other' WHERE producer='fork-opportunity'"
    )
    db.connection.execute(
        "UPDATE detector_facts SET fact_type='other' WHERE fact_type='fork_opportunity'"
    )
    db.connection.commit()
    eligible, excluded = eligible_contexts(db, LEARNER, "fork", "execute", datetime.now(UTC))
    assert not eligible and excluded["fork_family_unvalidated"] == 1
