"""Synthetic tests of legal king-safety observations and source lifecycle."""

import sys
from dataclasses import replace
from datetime import UTC, datetime

import chess
import chess.engine
import chess.pgn
import pytest

from chess_coach.db import Database
from chess_coach.evidence_review import inspect_evidence, review_evidence
from chess_coach.ingest import ingest_pgn
from chess_coach.king_safety_lesson import lesson
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


@pytest.mark.parametrize("mirror", [False, True])
def test_castling_and_luft_are_descriptive(mirror):
    board = chess.Board(CASTLE)
    if mirror:
        board = board.mirror()
    castle = "e8g8" if mirror else "e1g1"
    result = lesson(board, castle, None, None)
    assert result["before"]["king"] != result["after"]["king"]
    assert result["played"]["move"]["san"] == "O-O"
    assert result["alternative"]["move"]["uci"] in {m.uci() for m in board.legal_moves}
    assert result["mastery_eligible"] is False
    pawn_move = "h7h6" if mirror else "h2h3"
    castled = chess.Board("4k3/8/8/8/8/8/5PPP/6K1 w - - 0 1")
    if mirror:
        castled = castled.mirror()
    luft = lesson(castled, pawn_move, None, None)
    assert luft["before"] != luft["after"]
    assert "not prove" in luft["uncertainty"]


def test_immediate_check_and_legal_king_replies():
    board = chess.Board("6rk/8/8/8/8/8/5PPP/6K1 w - - 0 1")
    result = lesson(board, "h2h3", None, None)
    assert result is not None
    checks = result["played"]["checks"]
    assert checks
    assert all(board.parse_uci("h2h3") in board.legal_moves for _ in checks)
    for check in checks:
        replay = board.copy()
        replay.push_uci("h2h3")
        replay.push_uci(check["uci"])
        assert set(check["king_replies"]) == {
            replay.san(m)
            for m in replay.legal_moves
            if replay.piece_type_at(m.from_square) == chess.KING
        }


def test_root_history_is_checked_before_quiet_move():
    board = chess.Board()
    for move in ("g1f3", "g8f6", "f3g1", "f6g8"):
        board.push_uci(move)
    assert board.is_repetition(2)
    with pytest.raises(ValueError):
        lesson(board, "h2h3", None, None)
    for move in ("g1f3", "g8f6", "f3g1", "f6g8"):
        board.push_uci(move)
    assert board.is_repetition(3)
    with pytest.raises(ValueError):
        lesson(board, "h2h3", None, None)
    for _ in range(2):
        for move in ("g1f3", "g8f6", "f3g1", "f6g8"):
            board.push_uci(move)
    assert board.is_fivefold_repetition()
    with pytest.raises(ValueError):
        lesson(board, "h2h3", None, None)
    for clock in (99, 100, 150):
        board = chess.Board(CASTLE)
        board.halfmove_clock = clock
        with pytest.raises(ValueError):
            lesson(board, "h2h3", None, None)


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


def test_specific_mate_threat_and_defensive_counterline():
    board = chess.Board("6rk/8/8/6q1/8/8/5PPP/6K1 w - - 0 1")
    result = lesson(board, "h2h3", None, None)
    assert any(check["san"] == "Qxg2#" and check["mate"] for check in result["played"]["checks"])
    alternative = result["alternative"]
    assert alternative["move"]["san"] == "g3"
    check = next(check for check in alternative["checks"] if check["san"] == "Qxg3+")
    assert check["king_replies"] == ["Kf1", "Kh1"]
    assert not any(check["mate"] for check in alternative["checks"])
    assert result["mastery_eligible"] is False
    from chess_coach.lesson_king_safety import king_safety

    facts, lines = king_safety({"facts": [{"payload": result}]}, board.fen())
    assert any("permits immediate mate by Qxg2#" in fact and "g3" in fact for fact in facts)
    assert any(line["moves"] == ["g3", "Qxg3+"] for line in lines)


def test_attacking_and_harmless_pawn_changes_are_not_failures():
    attacking = chess.Board("8/8/8/7k/8/8/5NPP/6K1 w - - 0 1")
    result = lesson(attacking, "g2g4", None, None)
    assert result["played"]["move"]["san"] == "g4+"
    assert result["mastery_eligible"] is False
    quiet = chess.Board("4k3/8/8/8/8/8/5PPP/6K1 w - - 0 1")
    result = lesson(quiet, "h2h3", None, None)
    assert result["played"]["checks"] == []
    assert result["mastery_eligible"] is False
    assert "compensation" in result["uncertainty"]


def test_recurrence_and_populated_browser(tmp_path, monkeypatch):
    import time

    from chess_coach.lesson_narrative import build
    from chess_coach.recurrence_report import report
    from chess_coach.web import create_app

    db = Database(tmp_path / "recurrence.sqlite")
    db.initialize()
    monkeypatch.setattr(chess.engine.SimpleEngine, "popen_uci", lambda _: Engine())
    config = PipelineConfig(learner="fixture_learner", engine_path=sys.executable, nodes=100)
    for day in (1, 2, 3):
        board = chess.Board(CASTLE)
        game = chess.pgn.Game()
        game.setup(board)
        game.headers.update(
            {
                "White": "fixture_learner",
                "Black": "fixture_opponent",
                "UTCDate": f"2026.01.{day:02}",
                "UTCTime": "12:00:00",
            }
        )
        game.add_variation(board.parse_uci("e1g1"))
        ingest_pgn(db, str(game))
        game_id = db.connection.execute("SELECT MAX(id) FROM games").fetchone()[0]
        run_analysis(db, game_id, game_input(db, game_id), config, engine_identity(sys.executable))
        position_id = db.connection.execute(
            "SELECT id FROM positions WHERE game_id=?", (game_id,)
        ).fetchone()[0]
        prepared, fact = prepare_lesson(db, position_id, "fixture_learner")
        publish(db, prepared, fact)
    start, end, prior = (
        "2026-01-01T00:00:00+00:00",
        "2026-02-01T00:00:00+00:00",
        "2025-12-01T00:00:00+00:00",
    )
    group = report(
        db, "fixture_learner", start, end, prior, skill="king_safety", operation="evaluate"
    )["current"][0]
    assert group["independent_games"] == group["ambiguous"] == 3
    assert len(build(db, "fixture_learner", group)["examples"]) == 3
    app = create_app(
        db_path=tmp_path / "recurrence.sqlite",
        subject="fixture_learner",
        actor="fixture",
        corpus="test",
        login="login",
        origin="https://coach.invalid",
    )
    started = time.monotonic()
    page = app.test_client().get(
        "/recurrence",
        base_url="https://coach.invalid",
        headers={"Tailscale-User-Login": "login"},
        query_string={
            "start": start,
            "end": end,
            "compare_start": prior,
            "skill": "king_safety",
            "operation": "evaluate",
        },
    )
    elapsed = time.monotonic() - started
    print(f"populated recurrence render: {elapsed:.3f}s")
    assert page.status_code == 200
    assert b"shelter pawns" in page.data and b"legal alternative" in page.data.lower()
    assert page.data.count(b"/evidence/") >= 3
    db.connection.execute(
        "UPDATE decision_analysis_lines SET score_value=score_value+1 WHERE position_id=? AND role=?",
        (position_id, "best"),
    )
    db.connection.commit()
    updated = report(
        db, "fixture_learner", start, end, prior, skill="king_safety", operation="evaluate"
    )
    assert updated["current"][0]["independent_games"] == 2
    assert updated["coverage"]["excluded"]["stale"] == 1


def test_pinned_geometric_attack_is_not_a_legal_capture():
    board = chess.Board("4k3/8/8/8/8/4r3/5PPP/4R1K1 w - - 0 1")
    result = lesson(board, "h2h3", None, None)
    assert "h3" in result["after"]["attacked"]
    board.push_uci("h2h3")
    assert chess.Move.from_uci("e3h3") not in board.legal_moves
    assert "Rxh3" not in result["played"]["captures"]


def test_capture_promotion_is_shown_as_possible_counterplay():
    board = chess.Board("k6r/6P1/5K2/8/8/8/8/8 w - - 0 1")
    result = lesson(board, "g7h8q", None, None)
    assert result["played"]["move"]["capture"]
    assert result["played"]["move"]["promotion"]
    assert result["mastery_eligible"] is False
    from chess_coach.lesson_king_safety import king_safety

    facts, _ = king_safety({"facts": [{"payload": result}]}, board.fen())
    assert any("capture, promotion" in fact for fact in facts)
    assert any("compensation" in fact for fact in facts)
