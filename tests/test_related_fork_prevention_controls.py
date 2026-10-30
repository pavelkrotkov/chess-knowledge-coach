"""Source, history, policy and unsupported-case controls for fork prevention."""

import sys

import chess
import chess.engine
import chess.pgn
import pytest

from chess_coach.db import Database
from chess_coach.evidence_review import review_evidence
from chess_coach.fork_defense_detector import process_decision
from chess_coach.ingest import ingest_pgn
from chess_coach.pipeline_config import PipelineConfig
from chess_coach.pipeline_inputs import engine_identity, game_input
from chess_coach.pipeline_work import run_analysis
from chess_coach.puzzle_session_validate import legal_move, validate_line
from chess_coach.related_fork_prevention import preview
from chess_coach.related_fork_prevention_budget import create
from chess_coach.related_fork_prevention_features import features
from chess_coach.related_fork_prevention_source import source_for_evidence
from chess_coach.related_fork_prevention_start import start_related
from chess_coach.unified_session_events import show
from tests.test_fork_defense import mirror
from tests.test_fork_defense_pipeline import LEARNER, Engine
from tests.test_related_fork_prevention import PRE, source_and_corpus


@pytest.mark.parametrize("black", [False, True])
def test_created_by_played_move_source_is_rejected(tmp_path, monkeypatch, black):
    board = chess.Board("7k/6p1/8/8/1n6/8/7P/1R2K3 w - - 0 1")
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
    db = Database(tmp_path / "created.sqlite")
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
    with pytest.raises(ValueError, match="created-by-play"):
        source_for_evidence(db, LEARNER, evidence)
    db.close()


def test_wrong_operation_malformed_history_and_work_exhaustion_are_unknown(tmp_path, monkeypatch):
    db, evidence = source_and_corpus(tmp_path / "controls.sqlite", monkeypatch)
    source = source_for_evidence(db, LEARNER, evidence)["features"]
    prompt = validate_line(PRE, "g6g5 a1b1 h8g8 e1f1")
    wrong = ["h2h3", "b4c2", "e1f1", "c2a1"]
    assert features(prompt, wrong, source, create()) is None
    assert features(PRE, ["g6g5", "a1b1"], source, create()) is None
    assert features(prompt, ["a1b1", "h8h1"], source, create()) is None
    unknown_history = prompt.replace(" 0 2", " 3 2")
    assert features(unknown_history, ["a1b1", "h8g8"], source, create()) is None
    budget = create()
    budget["anchor_limit"] = 0
    assert features(prompt, ["a1b1", "h8g8"], source, budget) is None
    assert budget["truncated"] and budget["anchors"] == 0
    db.close()


def test_setup_preserves_castling_rights_and_ep_is_not_guessed(tmp_path, monkeypatch):
    fen = "r3k2r/7p/8/8/8/8/7P/R3K2R b KQkq - 0 1"
    prompt = validate_line(fen, "h7h6 e1g1")
    board = chess.Board(prompt)
    assert board.turn == chess.WHITE and board.has_kingside_castling_rights(chess.WHITE)
    assert legal_move(board, "e1g1") in board.legal_moves
    db, evidence = source_and_corpus(tmp_path / "ep.sqlite", monkeypatch)
    source = source_for_evidence(db, LEARNER, evidence)["features"]
    ep = "7k/8/8/3pP3/8/8/8/7K w - d6 0 1"
    assert features(ep, ["e5e6", "h8g8"], source, create()) is None
    db.close()


def test_review_foreign_source_and_active_session_revalidate(tmp_path, monkeypatch):
    db, evidence = source_and_corpus(tmp_path / "revoked.sqlite", monkeypatch)
    with pytest.raises(ValueError):
        preview(db, "fixture_other", evidence, "test")
    item = preview(db, LEARNER, evidence, "test")["items"][0]
    start_related(
        db,
        attempt_id="session",
        subject=LEARNER,
        evidence_id=evidence,
        corpus_version="test",
        reference=item["reference"],
    )
    review_evidence(db, evidence, decision="reject", actor="fixture_reviewer")
    with pytest.raises(ValueError):
        preview(db, LEARNER, evidence, "test")
    with pytest.raises(ValueError, match="stale"):
        show(db, "session", LEARNER)
    with pytest.raises(ValueError):
        start_related(
            db,
            attempt_id="stale",
            subject=LEARNER,
            evidence_id=evidence,
            corpus_version="test",
            reference=item["reference"],
        )
    db.close()


def test_policy_change_invalidates_opaque_reference(tmp_path, monkeypatch):
    import chess_coach.related_fork_prevention_budget as budget

    db, evidence = source_and_corpus(tmp_path / "policy.sqlite", monkeypatch)
    item = preview(db, LEARNER, evidence, "test")["items"][0]
    monkeypatch.setattr(budget, "LINE_LIMIT", budget.LINE_LIMIT + 1)
    with pytest.raises(ValueError):
        start_related(
            db,
            attempt_id="stale-policy",
            subject=LEARNER,
            evidence_id=evidence,
            corpus_version="test",
            reference=item["reference"],
        )
    assert db.connection.execute("SELECT COUNT(*) FROM unified_sessions").fetchone()[0] == 0
    db.close()


def test_familiar_synthetic_prompt_is_excluded(tmp_path, monkeypatch):
    db, evidence = source_and_corpus(tmp_path / "familiar.sqlite", monkeypatch)
    solution = "g6g5 a1b1 h8g8 e1f1"
    prompt = validate_line(PRE, solution)
    db.connection.execute(
        """INSERT INTO puzzle_sessions(attempt_id,corpus_version,corpus_checksum,puzzle_id,
        initial_fen,solution,current_fen,next_index,status,started_at)
        VALUES('prior','test','checksum','fixture',?,?,?,0,'active','2026-01-01')""",
        (PRE, solution, prompt),
    )
    db.connection.commit()
    result = preview(db, LEARNER, evidence, "test")
    assert result["items"] == []
    assert result["excluded"]["familiar"] == 1
    assert "insufficient" in result["status"]
    db.close()


def test_filter_version_change_stales_reference_and_active_session(tmp_path, monkeypatch):
    from chess_coach import related_fork_prevention_contract as contract

    db, evidence = source_and_corpus(tmp_path / "filter.sqlite", monkeypatch)
    item = preview(db, LEARNER, evidence, "test")["items"][0]
    start_related(
        db,
        attempt_id="filter",
        subject=LEARNER,
        evidence_id=evidence,
        corpus_version="test",
        reference=item["reference"],
    )
    monkeypatch.setattr(contract, "FILTER_VERSION", "future-filter")
    with pytest.raises(ValueError, match="stale"):
        show(db, "filter", LEARNER)
    with pytest.raises(ValueError):
        start_related(
            db,
            attempt_id="old-ref",
            subject=LEARNER,
            evidence_id=evidence,
            corpus_version="test",
            reference=item["reference"],
        )
    db.close()


def test_exhausted_preview_budget_discloses_unknown(tmp_path, monkeypatch):
    from chess_coach import related_fork_prevention_budget as limits

    db, evidence = source_and_corpus(tmp_path / "budget.sqlite", monkeypatch)
    monkeypatch.setattr(limits, "ANCHOR_LIMIT", 0)
    result = preview(db, LEARNER, evidence, "test")
    assert result["items"] == []
    assert result["prevention_scan"]["truncated"] is True
    assert result["prevention_scan"]["anchors"] == 0
    assert "source-specific currentness" in result["source_verification"]
    db.close()


def test_anchor_rejects_above_existing_move_cap(tmp_path, monkeypatch):
    from chess_coach import related_fork_prevention_anchor as implementation

    db, evidence = source_and_corpus(tmp_path / "anchor-cap.sqlite", monkeypatch)
    source = source_for_evidence(db, LEARNER, evidence)["features"]
    prompt = chess.Board(validate_line(PRE, "g6g5 a1b1 h8g8 e1f1"))
    monkeypatch.setattr(implementation, "MAX_ANCHOR_MOVES", 0)
    budget = create()
    assert implementation.anchor(prompt, source, budget) is None
    assert budget["truncated"] and budget["proofs"] == 0
    db.close()


def test_public_license_change_invalidates_source_bound_session(tmp_path, monkeypatch):
    import json
    import sqlite3

    db, evidence = source_and_corpus(tmp_path / "public.sqlite", monkeypatch)
    db.connection.execute("""INSERT INTO public_collections(version,source_url,source_revision,source_sha256,
        content_sha256,content_format,license,attribution,license_notice,accepted,excluded,state)
        VALUES('public-fixture','https://example.invalid','v1','a','b','fen_csv','CC0-1.0','fixture','notice',1,0,'staging')""")
    collection = db.connection.execute(
        "SELECT id FROM public_collections WHERE version='public-fixture'"
    ).fetchone()[0]
    pre = PRE.replace("7P", "P6P")
    prompt = validate_line(pre, "g6g5 a1b1 h8g8 e1f1")
    lines = ["a1b1 h8g8 e1f1", "h2h3 b4c2 e1f1 c2a1"]
    db.connection.execute(
        "INSERT INTO public_tasks VALUES(?,?,?,?,?)",
        (collection, "fixture", prompt, "legal_line", json.dumps(lines)),
    )
    db.connection.execute("UPDATE public_collections SET state='ready' WHERE id=?", (collection,))
    db.connection.commit()
    item = next(
        item for item in preview(db, LEARNER, evidence, "test")["items"] if item["type"] == "public"
    )
    start_related(
        db,
        attempt_id="public",
        subject=LEARNER,
        evidence_id=evidence,
        corpus_version="test",
        reference=item["reference"],
    )
    with pytest.raises(sqlite3.IntegrityError, match="immutable"):
        db.connection.execute(
            "UPDATE public_collections SET license='changed' WHERE id=?", (collection,)
        )
    db.connection.rollback()
    db.connection.execute("DROP TRIGGER immutable_update_public_collections")
    db.connection.execute(
        "UPDATE public_collections SET license='changed' WHERE id=?", (collection,)
    )
    db.connection.commit()
    with pytest.raises(ValueError, match=r"stale|unavailable"):
        show(db, "public", LEARNER)
    with pytest.raises(ValueError):
        start_related(
            db,
            attempt_id="stale-public",
            subject=LEARNER,
            evidence_id=evidence,
            corpus_version="test",
            reference=item["reference"],
        )
    db.close()
