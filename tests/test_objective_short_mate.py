"""Owned short-mate alternatives preserve proof, history and playable state."""

import json

import chess
import pytest

from chess_coach.mate_auto import process_decision
from chess_coach.mate_contract import MAPPER
from chess_coach.objective_short_source import VERSION
from chess_coach.objective_worker import process
from chess_coach.unified_session_events import hint, reveal, show, submit
from chess_coach.unified_sessions import start
from chess_coach.web import create_app
from tests.test_mate_proof import owned_game

WHITE = "7k/5Q2/6K1/8/8/8/8/8 w - - 0 1"
BLACK = chess.Board(WHITE).mirror().fen()


def fixture(path, monkeypatch, black=False):
    subject = "fixture_b" if black else "fixture_a"
    db = owned_game(
        path, monkeypatch, fen=BLACK if black else WHITE, move="Qa2" if black else "Qa7"
    )
    process_decision(db, 1, subject)
    evidence = db.connection.execute(
        "SELECT e.id FROM evidence_mappings e JOIN mapping_runs r ON r.id=e.mapping_run_id WHERE r.producer=?",
        (MAPPER,),
    ).fetchone()[0]
    return db, evidence, subject


def begin(db, evidence, subject, attempt="attempt"):
    return start(
        db,
        attempt_id=attempt,
        subject=subject,
        source_type="own-game",
        version=VERSION,
        key=str(evidence),
    )


def alternative(db, attempt):
    row = db.connection.execute(
        "SELECT lines_json,provenance_json FROM unified_sessions WHERE attempt_id=?", (attempt,)
    ).fetchone()
    root = json.loads(row["lines_json"])[0][0]
    fact = db.connection.execute(
        "SELECT payload_json FROM detector_facts WHERE id=(SELECT fact_id FROM evidence_fact_links WHERE evidence_id=?)",
        (json.loads(row["provenance_json"])["evidence_id"],),
    ).fetchone()
    proof = json.loads(fact[0])["proof"]
    return next(
        item["move"]["uci"]
        for item in proof["alternatives"]
        if item["status"] == "proved"
        and item["distance_plies"] == 3
        and item["move"]["uci"] != root
    )


@pytest.mark.parametrize("black", [False, True])
def test_proved_alternative_is_playable_and_only_actual_mate_completes(
    tmp_path, monkeypatch, black
):
    db, evidence, subject = fixture(tmp_path / "fixture.sqlite", monkeypatch, black)
    begin(db, evidence, subject)
    answer = alternative(db, "attempt")
    pending = submit(db, "attempt", subject, event_id="answer", move=answer)
    assert pending["status"] == "needs_verification"
    frozen = db.connection.execute(
        "SELECT response_json FROM unified_session_events WHERE event_id=?", ("answer",)
    ).fetchone()[0]
    assert process(db, subject)["outcomes"] == {"correct": 1}
    result = json.loads(
        db.connection.execute("SELECT result_json FROM objective_results").fetchone()[0]
    )
    assert result["proof"]["distance_plies"] == 3 and result["learning_eligible"] is False
    changes = db.connection.total_changes
    state = show(db, "attempt", subject)
    assert state["status"] == "active" and state["proved_continuation"]
    assert show(db, "attempt", subject) == state
    assert db.connection.total_changes == changes
    assert process(db, subject)["processed"] == 0
    assert submit(db, "attempt", subject, event_id="answer", move=answer) == pending
    assert (
        db.connection.execute(
            "SELECT response_json FROM unified_session_events WHERE event_id=?", ("answer",)
        ).fetchone()[0]
        == frozen
    )
    assert hint(db, "attempt", subject, event_id="hint")["assistance_kind"] == "hinted"
    revealed = reveal(db, "attempt", subject, event_id="reveal")
    assert revealed["assistance_kind"] == "revealed"
    mate = revealed["revealed_line"]
    assert chess.Board(state["fen"]).parse_uci(mate) in chess.Board(state["fen"]).legal_moves
    completed = submit(db, "attempt", subject, event_id="finish", move=mate)
    assert (
        completed["status"] == "objective_verified" and chess.Board(completed["fen"]).is_checkmate()
    )
    assert submit(db, "attempt", subject, event_id="finish", move=mate) == completed
    assert db.connection.execute("SELECT COUNT(*) FROM training_attempts").fetchone()[0] == 0
    app = create_app(
        db_path=tmp_path / "fixture.sqlite",
        subject=subject,
        actor="fixture",
        corpus="fixture",
        login="fixture",
        origin="https://coach.invalid",
    )
    response = app.test_client().get(
        "/unified/attempt",
        base_url="https://coach.invalid",
        headers={"Tailscale-User-Login": "fixture"},
    )
    assert response.status_code == 200 and b"checkmate objective was verified" in response.data
