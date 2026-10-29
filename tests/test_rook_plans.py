"""Synthetic rook choices preserve legal boundaries and descriptive provenance."""

import sys
from datetime import UTC, datetime

import chess
import chess.engine
import chess.pgn
import pytest

from chess_coach.db import Database
from chess_coach.evidence_review import inspect_evidence, review_evidence
from chess_coach.ingest import ingest_pgn
from chess_coach.lesson_narrative import build
from chess_coach.mastery_eligibility import eligible_contexts
from chess_coach.pipeline_config import PipelineConfig
from chess_coach.pipeline_inputs import engine_identity, game_input
from chess_coach.pipeline_work import run_analysis
from chess_coach.recurrence_report import report
from chess_coach.rook_plan_lesson import lesson
from chess_coach.rook_plan_probe import state
from chess_coach.rook_plan_worker import process_rook_plans
from chess_coach.web import create_app

FEN = "r6k/8/8/8/8/8/8/R6K w - - 0 1"


def line(pv):
    return {"status": "limited", "score_kind": "cp", "score_bound": "exact", "pv": pv}


@pytest.mark.parametrize("mirror", [False, True])
def test_legal_file_entry_tactical_capture_and_alternative(mirror):
    board = chess.Board(FEN)
    if mirror:
        board = board.mirror()
        best, played, take, quiet = "a8a4", "h8g8", "a1a4", "h1g2"
    else:
        best, played, take, quiet = "a1a5", "h1g1", "a8a5", "h8g7"
    result = lesson(board, played, line(f"{best} {take}"), line(f"{played} {quiet}"))
    assert result["file_kind"] == "open"
    assert result["color"] == ("black" if mirror else "white")
    assert any(entry["square"] == ("a4" if mirror else "a5") for entry in result["entries"])
    assert result["roots"]["best"]["captures"]["captures"][0]["gain"] == 5
    assert result["plan_status"] == "immediate_capture_found"
    assert ("Rxa4" if mirror else "Rxa5") in result["counterplan"]
    assert "gain of 5 material units" in result["plan"]
    assert result["roots"]["played"]["square"] == ("a8" if mirror else "a1")
    assert result["mastery_eligible"] is False


@pytest.mark.parametrize("mirror", [False, True])
def test_pinned_attacker_is_not_a_legal_rook_capture(mirror):
    board = chess.Board("1k6/8/1b6/8/8/8/8/RR5K w - - 0 1")
    if mirror:
        board = board.mirror()
        best, played, reply = "a8a4", "b8b7", "b1c2"
    else:
        best, played, reply = "a1a5", "b1b2", "b8c7"
    result = lesson(board, played, line(f"{best} {reply}"), line(f"{played} {reply}"))
    assert result["roots"]["best"]["captures"] == {"status": "checked", "captures": []}


@pytest.mark.parametrize("mirror", [False, True])
def test_half_open_file_and_controlled_entry(mirror):
    board = chess.Board("r6k/p7/8/8/8/8/8/R6K w - - 0 1")
    if mirror:
        board = board.mirror()
        best, played, advance, quiet, target = "a8a4", "h8g8", "a2a3", "h1g2", "a4"
    else:
        best, played, advance, quiet, target = "a1a5", "h1g1", "a7a6", "h8g7", "a5"
    result = lesson(board, played, line(f"{best} {advance}"), line(f"{played} {quiet}"))
    assert result["file_kind"] == "half-open"
    entry = next(item for item in result["entries"] if item["square"] == target)
    assert entry["captures"] == {"status": "checked", "captures": []}


@pytest.mark.parametrize("mirror", [False, True])
def test_file_occupation_without_entry_and_active_alternative(mirror):
    board = chess.Board("r6k/8/8/8/8/8/8/RR5K w - - 0 1")
    if mirror:
        board = board.mirror()
        best, played, take, quiet = "a8a7", "b8b4", "a1a7", "h1g2"
    else:
        best, played, take, quiet = "a1a2", "b1b5", "a8a2", "h8g7"
    result = lesson(board, played, line(f"{best} {take}"), line(f"{played} {quiet}"))
    assert result["roots"]["best"]["captures"]["captures"][0]["gain"] == 5
    assert "file occupation" in result["plan"]
    assert ("Rb4" if mirror else "Rb5") in result["plan"]
    assert ("Rxa7" if mirror else "Rxa2") in result["counterplan"]
    assert result["lines"]["played"]["uci"][0] == played
    assert result["roots"]["played"]["square"] == ("a8" if mirror else "a1")
    assert (
        result["roots"]["best"]["rook_attacks_enemy_half"]
        != result["roots"]["played"]["rook_attacks_enemy_half"]
    )


@pytest.mark.parametrize("mirror", [False, True])
def test_pinned_pawn_cannot_recapture_the_attacker(mirror):
    board = chess.Board("rr5k/8/8/8/1P6/8/8/RK6 w - - 0 1")
    if mirror:
        board = board.mirror()
        best, played, take, quiet = "a8a4", "b8c8", "a1a4", "h1g2"
    else:
        best, played, take, quiet = "a1a5", "b1c1", "a8a5", "h8g7"
    result = lesson(board, played, line(f"{best} {take}"), line(f"{played} {quiet}"))
    assert result["roots"]["best"]["captures"]["captures"][0]["gain"] == 5


@pytest.mark.parametrize("mirror", [False, True])
def test_conditional_entry_and_unresolved_checking_capture(mirror):
    for bishop in (False, True):
        board = chess.Board(
            "7k/8/4b3/8/8/8/8/3R3K w - - 0 1" if bishop else "7k/8/8/8/8/8/8/3R3K w - - 0 1"
        )
        if mirror:
            board = board.mirror()
            best, played, reply, entry = "d8d4", "h8g8", "h1g2", "Rd4"
        else:
            best, played, reply, entry = "d1d5", "h1g1", "h8g7", "Rd5"
        result = lesson(board, played, line(f"{best} {reply}"), line(f"{played} {reply}"))
        assert entry in result["plan"]
        assert ("Kg8" if mirror else "Kg1") in result["plan"]
        if bishop:
            assert result["plan_status"] == "unsupported"
            assert "unresolved" in result["plan"] and "unresolved" in result["counterplan"]
            assert "inconclusive" in result["next"]
        else:
            assert result["plan_status"] == "immediate_capture_absent"
            assert "enemy-half entry" in result["plan"]
            assert "no immediate legal capture" in result["plan"]
            assert "unverified" in result["counterplan"]


@pytest.mark.parametrize("mirror", [False, True])
def test_played_rook_root_uses_correct_recorded_alternative(mirror):
    board = chess.Board(FEN)
    if mirror:
        board = board.mirror()
        rook, king, take, reply = "a8a4", "h8g8", "a1a4", "h1g2"
    else:
        rook, king, take, reply = "a1a5", "h1g1", "a8a5", "h8g7"
    result = lesson(board, rook, line(f"{king} {reply}"), line(f"{rook} {take}"))
    assert ("Ra4" if mirror else "Ra5") in result["plan"]
    assert ("Kg8" if mirror else "Kg1") in result["plan"]
    assert ("Rxa4" if mirror else "Rxa5") in result["counterplan"]


@pytest.mark.parametrize("mirror", [False, True])
def test_entry_with_favorable_bounded_recapture_is_not_called_safe(mirror):
    board = chess.Board("3q3k/8/8/8/4P3/8/8/3R3K w - - 0 1")
    if mirror:
        board = board.mirror()
        rook, king, take, reply = "d8d4", "h8g8", "d1d4", "h1g2"
    else:
        rook, king, take, reply = "d1d5", "h1g1", "d8d5", "h8g7"
    result = lesson(board, king, line(f"{rook} {take}"), line(f"{king} {reply}"))
    assert result["roots"]["best"]["captures"]["captures"][0]["gain"] == -4
    assert "gain of -4 material units" in result["plan"]
    assert "possible, not forced" in result["counterplan"]
    assert "not forced" in result["uncertainty"]


def test_incomplete_same_or_illegal_alternatives_remain_unpublished():
    board = chess.Board(FEN)
    best = line("a1a5 a8a5")
    assert lesson(board, "a1a5", best, best) is None
    assert lesson(board, "h1g1", best, None) is None
    assert lesson(board, "h1g1", best, line("h1g1 a8b7")) is None
    assert lesson(chess.Board(), "e2e4", None, None) is None
    board.halfmove_clock = 100
    assert lesson(board, "h1g1", best, line("h1g1 h8g7")) is None


class Engine:
    def __init__(self):
        self.id = {"name": "Synthetic"}
        self.options = {}

    def configure(self, settings):
        pass

    def analyse(self, board, limit, multipv, root_moves=None):
        if not board.move_stack:
            root = root_moves[0] if root_moves else chess.Move.from_uci("a1a5")
            reply = chess.Move.from_uci("a8a5" if root.uci() == "a1a5" else "h8g7")
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


def test_worker_review_recurrence_browser_and_currentness(tmp_path, monkeypatch):
    db = Database(tmp_path / "fixture.sqlite")
    db.initialize()
    monkeypatch.setattr(chess.engine.SimpleEngine, "popen_uci", lambda _: Engine())
    config = PipelineConfig(learner="fixture_learner", engine_path=sys.executable, nodes=100)
    for day in (1, 2, 3):
        board = chess.Board(FEN)
        game = chess.pgn.Game()
        game.setup(board)
        game.headers.update(
            {
                "White": "fixture_learner",
                "Black": "fixture_opponent",
                "UTCDate": f"2026.01.{day:02}",
                "UTCTime": "12:00:00",
                "Result": "*",
            }
        )
        game.add_variation(board.parse_uci("h1g1"))
        ingest_pgn(db, str(game))
        game_id = db.connection.execute("SELECT MAX(id) FROM games").fetchone()[0]
        assert (
            run_analysis(
                db, game_id, game_input(db, game_id), config, engine_identity(sys.executable)
            )["status"]
            == "complete"
        )
    worker = process_rook_plans(db, config)
    assert worker["processed"] == 3 and worker["outcomes"] == {"descriptive": 3}
    assert process_rook_plans(db, config)["replayed"] == 3
    evidence_id = db.connection.execute(
        "SELECT MAX(id) FROM evidence_mappings WHERE skill='open_files'"
    ).fetchone()[0]
    evidence = inspect_evidence(db, evidence_id)
    assert evidence["rook_plan_currentness"] == "current" and evidence["outcome"] == "ambiguous"
    review_evidence(db, evidence_id, decision="accept", actor="fixture")
    eligible, reasons = eligible_contexts(
        db, "fixture_learner", "open_files", "evaluate", datetime.now(UTC)
    )
    assert not eligible and reasons["pawn_family_unvalidated"] == 1
    args = (
        db,
        "fixture_learner",
        "2026-01-01T00:00:00+00:00",
        "2026-02-01T00:00:00+00:00",
        "2025-12-01T00:00:00+00:00",
    )
    group = report(*args, skill="open_files", operation="evaluate")["current"][0]
    assert group["independent_games"] == group["ambiguous"] == 3
    assert group["successes"] == group["misses"] == 0
    with monkeypatch.context() as patch:

        def no_inference(*args):
            raise AssertionError("published lessons must not rerun the detector")

        patch.setattr("chess_coach.rook_plan_source.lesson", no_inference)
        coaching = build(db, "fixture_learner", group)
    assert "ambiguous descriptive observations, not skill evidence" in coaching["qualification"]
    assert len(coaching["examples"]) == 3
    assert any("bounded exchange gains 5" in fact for fact in coaching["examples"][0]["facts"])
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
    assert (
        page.status_code == 200
        and b"Counterplan" in page.data
        and b"bounded exchange gains 5" in page.data
        and b"After Ra5" in page.data
        and b"Rxa5" in page.data
        and b"Next inspection" in page.data
    )
    db.connection.execute(
        "UPDATE decision_analysis_lines SET score_value=score_value+1 WHERE position_id=3 AND role='best'"
    )
    db.connection.commit()
    assert state(db, 3, "fixture_learner") == "needed"
    assert inspect_evidence(db, evidence_id)["rook_plan_currentness"] == "stale"
    changed = process_rook_plans(db, config)
    assert changed["processed"] == 1
    assert inspect_evidence(db, evidence_id)["review_status"] == "accepted"
    assert inspect_evidence(db, evidence_id)["lifecycle_status"] == "superseded"


def test_prior_review_is_preserved_and_upgrade_is_unreviewed(tmp_path, monkeypatch):
    from chess_coach import rook_plan_mapping, rook_plan_publish
    from chess_coach.rook_plan_source import prepare_lesson

    db = Database(tmp_path / "upgrade.sqlite")
    db.initialize()
    board = chess.Board(FEN)
    game = chess.pgn.Game()
    game.setup(board)
    game.headers.update(
        {
            "White": "fixture_learner",
            "Black": "fixture_opponent",
            "UTCDate": "2026.01.01",
            "UTCTime": "12:00:00",
            "Result": "*",
        }
    )
    game.add_variation(board.parse_uci("h1g1"))
    ingest_pgn(db, str(game))
    monkeypatch.setattr(chess.engine.SimpleEngine, "popen_uci", lambda _: Engine())
    config = PipelineConfig(learner="fixture_learner", engine_path=sys.executable, nodes=100)
    assert (
        run_analysis(db, 1, game_input(db, 1), config, engine_identity(sys.executable))["status"]
        == "complete"
    )
    prepared, fact = prepare_lesson(db, 1, "fixture_learner")
    old_fact = {key: value for key, value in fact.items() if key not in {"plan_status", "next"}}
    old_fact.update(
        {"version": "1.0.0", "plan": "Generic plan", "counterplan": "Generic counterplan"}
    )
    with monkeypatch.context() as patch:
        patch.setattr(rook_plan_publish, "VERSION", "1.0.0")
        patch.setattr(rook_plan_mapping, "VERSION", "1.0.0")
        old = rook_plan_publish.publish(db, prepared, old_fact)
    old_id = old["mapping"]["evidence_ids"][0]
    review_evidence(db, old_id, decision="accept", actor="fixture")
    assert inspect_evidence(db, old_id)["rook_plan_currentness"] == "stale"
    assert state(db, 1, "fixture_learner") == "needed"
    assert process_rook_plans(db, config)["processed"] == 1
    prior = inspect_evidence(db, old_id)
    assert prior["review_status"] == "accepted" and prior["lifecycle_status"] == "superseded"
    new_id = db.connection.execute(
        "SELECT MAX(id) FROM evidence_mappings WHERE skill='open_files'"
    ).fetchone()[0]
    current = inspect_evidence(db, new_id)
    assert new_id != old_id and current["review_status"] == "unreviewed"
    assert current["rook_plan_currentness"] == "current"
    assert current["facts"][0]["detector_version"] == "1.1.0"
    assert current["outcome"] == "ambiguous"
