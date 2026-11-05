"""Bounded unfamiliar short-mate assessment keeps provenance and assistance."""

import json

import chess
import pytest

from chess_coach.evidence_review import review_evidence
from chess_coach.mate_auto import process_decision
from chess_coach.related_mate import preview
from chess_coach.related_mate_source import source_for_evidence
from chess_coach.related_mate_start import start_related
from chess_coach.unified_session_events import hint, reveal, show, submit
from chess_coach.web import create_app
from tests.test_mate_proof import owned_game

SUBJECT = "fixture_a"


@pytest.mark.parametrize("mode", ["unassisted", "assisted", "ungraded", "incorrect"])
def test_related_short_mate_assessment_workflow(tmp_path, monkeypatch, mode):
    fen = "6k1/5ppp/8/1p5Q/8/5R2/7r/KQ3R2 w - - 0 1"
    db = owned_game(tmp_path / "short.sqlite", monkeypatch, fen=fen, move="Qa2")
    monkeypatch.setattr("chess_coach.mate_auto.short_candidate", lambda *_: True)
    process_decision(db, 1, SUBJECT)
    evidence = db.connection.execute(
        "SELECT id FROM evidence_mappings WHERE skill='calculation' AND operation='execute'"
    ).fetchone()[0]
    initial = chess.Board("6k1/1p3ppp/8/7Q/8/5R2/7r/KQ3R2 b - - 0 1")
    source = source_for_evidence(db, SUBJECT, evidence)
    moves = "b7b6 " + source["lines"][0]
    db.connection.execute(
        "INSERT INTO puzzle_corpora(version,source,checksum,state) VALUES('short','fixture','checksum','staging')"
    )
    corpus = db.connection.execute("SELECT id FROM puzzle_corpora").fetchone()[0]
    db.connection.execute(
        """INSERT INTO puzzles(puzzle_id,corpus_id,fen,source,solution,rating,rating_deviation,themes_json,objective)
        VALUES('short',?,?,'https://example.invalid',?,1200,80,'["mateIn2"]','unknown')""",
        (corpus, initial.fen(), moves),
    )
    db.connection.execute("INSERT INTO puzzle_themes VALUES(?,?,'mateIn2',1200)", (corpus, "short"))
    db.connection.execute("UPDATE puzzle_corpora SET state='ready' WHERE id=?", (corpus,))
    db.connection.commit()
    selected = preview(db, SUBJECT, evidence, "short")
    assert selected["mate_timing"] == "mate_within_two"
    assert len(selected["items"]) == 1 and selected["items"][0]["assessment_available"]
    ref = selected["items"][0]["reference"]
    before = db.connection.execute("SELECT COUNT(*) FROM training_attempts").fetchone()[0]
    state = start_related(
        db,
        attempt_id="assessment",
        subject=SUBJECT,
        evidence_id=evidence,
        corpus_version="short",
        reference=ref,
        assessment=True,
    )
    assert state["short_mate_assessment"] and state["objective"] == "mate_within_two"
    row = db.connection.execute(
        "SELECT * FROM unified_sessions WHERE attempt_id='assessment'"
    ).fetchone()
    data = json.loads(row["provenance_json"])["related_mate"]["assessment"]
    assert data["history_mode"] == "zeroing_setup" and data["roots"]
    assert len(data["roots"]) >= 2
    first_move = data["roots"][1 if mode == "unassisted" else 0]["move"]["uci"]
    if mode == "unassisted":
        assert first_move != moves.split()[1]
    if mode == "ungraded":
        board = chess.Board(state["fen"])
        proved = {root["move"]["uci"] for root in data["roots"]}
        unknown = next(move for move in board.legal_moves if move.uci() not in proved)
        result = submit(db, "assessment", SUBJECT, event_id="first", move=unknown.uci())
        assert result["status"] == "needs_verification" and "source_key" not in result
        assert db.connection.execute("SELECT COUNT(*) FROM objective_requests").fetchone()[0] == 0
    else:
        first = submit(db, "assessment", SUBJECT, event_id="first", move=first_move)
        assert first["status"] == "active" and first["opponent_move"]
        if mode == "assisted":
            hint(db, "assessment", SUBJECT, event_id="hint")
            reveal(db, "assessment", SUBJECT, event_id="reveal")
        board = chess.Board(show(db, "assessment", SUBJECT)["fen"])
        move = next(
            move for move in board.legal_moves if _mate(board, move) != (mode == "incorrect")
        )
        result = submit(db, "assessment", SUBJECT, event_id="mate", move=move.uci())
        assert result["status"] == (
            "line_completed" if mode == "incorrect" else "objective_verified"
        )
        assert result["hints_used"] == (2 if mode == "assisted" else 0)
    assert db.connection.execute("SELECT COUNT(*) FROM training_attempts").fetchone()[0] == before
    app = create_app(
        db_path=tmp_path / "short.sqlite",
        subject=SUBJECT,
        actor="fixture",
        corpus="short",
        login="fixture",
        origin="https://coach.invalid",
    )
    page = app.test_client().get(
        "/unified/assessment",
        base_url="https://coach.invalid",
        headers={"Tailscale-User-Login": "fixture"},
    )
    assert page.status_code == 200
    expected = {
        "unassisted": b"No hint or reveal was used",
        "assisted": b"This attempt was assisted",
        "ungraded": b"remains ungraded",
        "incorrect": b"Incorrect: this final move did not give checkmate",
    }
    assert expected[mode] in page.data
    review_evidence(db, evidence, decision="reject", actor="fixture_reviewer")
    with pytest.raises(ValueError):
        show(db, "assessment", SUBJECT)
    db.close()


def _mate(board, move):
    board.push(move)
    result = board.is_checkmate()
    board.pop()
    return result
