"""Synthetic decisions test plans, bounded consequences and review lineage."""

import json
import sys
from datetime import UTC, datetime

import chess
import chess.engine
import chess.pgn
import pytest

from chess_coach.cli import main
from chess_coach.db import Database
from chess_coach.evidence_review import inspect_evidence, review_evidence
from chess_coach.ingest import ingest_pgn
from chess_coach.mastery_eligibility import eligible_contexts
from chess_coach.pawn_structure_lesson import lesson
from chess_coach.pawn_structure_publish import publish
from chess_coach.pawn_structure_source import prepare_lesson
from chess_coach.pawn_structure_worker import process_structure_lessons
from chess_coach.pipeline_config import PipelineConfig
from chess_coach.pipeline_inputs import engine_identity, game_input
from chess_coach.pipeline_work import run_analysis
from chess_coach.web import create_app

FEN = "3r3k/8/8/8/3P4/8/8/1N5K w - - 0 1"


def line(pv):
    return {"status": "limited", "score_kind": "cp", "score_bound": "exact", "pv": pv}


def test_defense_continuations_are_possibilities_and_never_skill_failures():
    board = chess.Board(FEN)
    result = lesson(board, "b1c3", line("d4d5 h8g7"), line("b1c3 d8d4"))
    assert result["targets"][0]["role"] == "defend"
    assert result["targets"][0]["controlled_squares"] == ["c5", "e5"]
    assert result["targets"][0]["legal_advance"] == "d5"
    assert result["lines"]["played"]["captures"][0]["square"] == "d4"
    assert result["lines"]["best"]["captures"] == []
    assert result["lines"]["best"]["immediate"][0]["after_square"] == "d5"
    assert result["lines"]["played"]["immediate"][0]["captures"][0]["gain"] == 1
    assert result["mastery_eligible"] is False
    assert "not a forced outcome" in result["consequence"]
    assert "compensation" in result["uncertainty"]


def test_verified_immediate_defensive_alternative():
    board = chess.Board("3r3k/8/8/8/3P4/8/7N/2B4K w - - 0 1")
    result = lesson(board, "h2f1", line("h2f3 h8g7"), line("h2f1 d8d4"))
    best = result["lines"]["best"]["immediate"][0]
    played = result["lines"]["played"]["immediate"][0]
    assert best["captures"] == [{"san": "Rxd4", "gain": -4}]
    assert played["captures"] == [{"san": "Rxd4", "gain": 1}]
    assert result["mastery_eligible"] is False


def test_color_mirror_attacks_and_unavailable_or_illegal_lines():
    board = chess.Board(FEN).mirror()
    result = lesson(board, "b8c6", line("d5d4 h1g2"), line("b8c6 d1d5"))
    assert result["targets"][0]["color"] == "black"
    assert result["targets"][0]["role"] == "defend"
    assert result["lines"]["played"]["captures"][0]["square"] == "d5"
    board.turn = chess.WHITE
    result = lesson(board, "d1d5", None, line("d1d5 h8g8"))
    assert result["targets"][0]["role"] == "attack"
    assert result["lines"]["best"] is None
    assert lesson(chess.Board(), "e2e4", None, None) is None
    result = lesson(chess.Board(FEN), "b1c3", None, line("b1c3 d8d3"))
    assert result["lines"]["played"] is None


def test_backward_geometry_and_activity_remain_descriptive():
    board = chess.Board("7k/8/3p4/2p1p3/5N2/8/8/7K b - - 0 1")
    result = lesson(board, "h8g7", None, None)
    target = next(t for t in result["targets"] if t["kind"] == "backward" and t["square"] == "d6")
    assert target["role"] == "defend"
    assert "activity" in target["plan"]
    assert all(value is None for value in result["lines"].values())


class Engine:
    def __init__(self):
        self.id = {"name": "Synthetic"}
        self.options = {}

    def configure(self, settings):
        pass

    def analyse(self, board, limit, multipv, root_moves=None):
        if not board.move_stack:
            root = root_moves[0] if root_moves else chess.Move.from_uci("d4d5")
            next_board = board.copy()
            next_board.push(root)
            reply = chess.Move.from_uci("d8d4" if root.uci() == "b1c3" else "h8g7")
            assert reply in next_board.legal_moves
            moves = [root, reply]
        else:
            moves = [root_moves[0] if root_moves else next(iter(board.legal_moves))]
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


def test_review_replay_supersession_and_mastery_gate(tmp_path, monkeypatch, capsys):
    board = chess.Board(FEN)
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
    game.add_variation(board.parse_uci("b1c3"))
    db = Database(tmp_path / "fixture.sqlite")
    db.initialize()
    ingest_pgn(db, str(game))
    monkeypatch.setattr(chess.engine.SimpleEngine, "popen_uci", lambda _: Engine())
    config = PipelineConfig(learner="fixture_learner", engine_path=sys.executable, nodes=100)
    assert (
        run_analysis(db, 1, game_input(db, 1), config, engine_identity(sys.executable))["status"]
        == "complete"
    )
    prepared, fact = prepare_lesson(db, 1, "fixture_learner")
    first = publish(db, prepared, fact)
    evidence_id = first["mapping"]["evidence_ids"][0]
    assert inspect_evidence(db, evidence_id)["pawn_structure_currentness"] == "current"
    worker = process_structure_lessons(db, config)
    assert worker["replayed"] == 1 and worker["examined"] <= config.material_max_decisions
    monkeypatch.setenv("LICHESS_USERNAME", "fixture_learner")
    monkeypatch.setattr(
        sys,
        "argv",
        ["chess-coach", "--db", str(tmp_path / "fixture.sqlite"), "inspect-decision", "1"],
    )
    main()
    assert (
        json.loads(capsys.readouterr().out)["pawn_structure_lesson"]["targets"][0]["square"] == "d4"
    )
    app = create_app(
        db_path=tmp_path / "fixture.sqlite",
        subject="fixture_learner",
        actor="fixture",
        corpus="fixture",
        login="fixture",
        origin="https://coach.invalid",
    )
    client = app.test_client()
    headers = {"Tailscale-User-Login": "fixture"}
    page = client.get("/decisions/1", base_url="https://coach.invalid", headers=headers)
    assert b"Pawn-structure plans" in page.data and b"not a forced outcome" in page.data
    page = client.get(f"/evidence/{evidence_id}", base_url="https://coach.invalid", headers=headers)
    assert b"Pawn-structure lesson source: current" in page.data
    review_evidence(db, evidence_id, decision="accept", actor="fixture_reviewer")
    replay = publish(db, prepared, fact)
    assert replay["mapping"]["evidence_ids"] == [evidence_id]
    eligible, reasons = eligible_contexts(
        db, "fixture_learner", "pawn_structure", "evaluate", datetime.now(UTC)
    )
    assert not eligible and reasons["pawn_family_unvalidated"] == 1
    db.connection.execute(
        "UPDATE decision_analysis_lines SET score_value=score_value+1 WHERE position_id=1 AND role='best'"
    )
    db.connection.commit()
    assert inspect_evidence(db, evidence_id)["pawn_structure_currentness"] == "stale"
    with pytest.raises(ValueError, match="source changed"):
        publish(db, prepared, fact)
    changed, fresh = prepare_lesson(db, 1, "fixture_learner")
    second = publish(db, changed, fresh)
    assert second["mapping"]["evidence_ids"] != [evidence_id]
    assert inspect_evidence(db, evidence_id)["review_status"] == "accepted"
    assert inspect_evidence(db, evidence_id)["lifecycle_status"] == "superseded"
    db.connection.execute(
        "UPDATE decision_analysis_lines SET score_value=score_value-1 WHERE position_id=1 AND role='best'"
    )
    db.connection.commit()
    restored, restored_fact = prepare_lesson(db, 1, "fixture_learner")
    new_run = publish(db, restored, restored_fact)
    new_id = new_run["mapping"]["evidence_ids"][0]
    assert new_id != evidence_id
    assert inspect_evidence(db, new_id)["review_status"] == "unreviewed"
    assert inspect_evidence(db, new_id)["pawn_structure_currentness"] == "current"
    assert publish(db, restored, restored_fact)["mapping"]["evidence_ids"] == [new_id]


def test_activity_from_isolated_pawn_is_not_a_failure():
    board = chess.Board("3r3k/8/8/4N3/3P4/8/8/7K w - - 0 1")
    result = lesson(board, "e5f7", None, None)
    target = next(t for t in result["targets"] if t["square"] == "d4")
    assert "e5" in target["controlled_squares"]
    assert board.piece_at(chess.E5) == chess.Piece(chess.KNIGHT, chess.WHITE)
    assert board.gives_check(board.parse_uci("e5f7"))
    assert result["mastery_eligible"] is False
    assert "compensation" in result["uncertainty"]


def test_backward_pawn_attack_has_a_bounded_legal_capture_witness():
    board = chess.Board("7k/8/3p4/2p1p3/5N2/8/8/3R3K w - - 0 1")
    result = lesson(board, "d1d6", line("d1d6 h8g7"), line("d1d6 h8g7"))
    target = next(t for t in result["targets"] if t["square"] == "d6")
    assert target["kind"] == "backward" and target["role"] == "attack"
    capture = result["lines"]["played"]["captures"][0]
    assert capture["square"] == "d6" and capture["exchange_gain"] == 1


def test_worker_counts_replayed_and_unavailable_against_budget(monkeypatch):
    from chess_coach import pawn_structure_worker as worker_module

    rows = [{"id": n} for n in range(1, 6)]
    visited = []
    monkeypatch.setattr(worker_module, "_scan", lambda db, learner, limit: ("key", rows))
    monkeypatch.setattr(
        worker_module, "save_cursor", lambda db, key, value, policy: visited.append(value)
    )

    def unavailable(db, position, learner, report, outcomes):
        report["unavailable"] += 1

    monkeypatch.setattr(worker_module, "process_item", unavailable)
    config = PipelineConfig(
        learner="fixture_learner", material_max_scan=5, material_max_decisions=2
    )
    result = worker_module.process_structure_lessons(None, config)
    assert visited == [1, 2]
    assert result["examined"] == result["unavailable"] == 2
    assert result["capped"] and result["status"] == "partial"
