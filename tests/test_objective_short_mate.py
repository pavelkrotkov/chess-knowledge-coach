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
    from chess_coach.coaching_practice import choices
    from chess_coach.lesson_mechanisms import describe
    from chess_coach.lesson_source import source

    coaching_board = chess.Board("6k1/5ppp/8/7Q/8/5R2/7r/K4R2 w - - 0 1")
    failure_db = owned_game(
        tmp_path / "coaching-short.sqlite",
        monkeypatch,
        fen=(coaching_board.mirror() if black else coaching_board).fen(),
        move="Kb8" if black else "Kb1",
    )
    monkeypatch.setattr("chess_coach.mate_auto.short_candidate", lambda *_: True)
    process_decision(failure_db, 1, subject)
    failed_evidence = failure_db.connection.execute(
        "SELECT id FROM evidence_mappings WHERE skill='calculation' AND operation='execute'"
    ).fetchone()[0]
    inspected = source(failure_db, subject, {"id": failed_evidence, "position_id": 1})
    assert inspected is not None and inspected["evidence"]["outcome"] == "failure"
    fact = inspected["evidence"]["facts"][0]
    example = describe(inspected)
    lesson = {
        "skill": "calculation",
        "operation": "execute",
        "family": MAPPER,
        "source_version": fact["detector_version"],
        "examples": [dict(example, evidence_id=0), example],
    }
    selected = choices(failure_db, subject, {"groups": [{"lesson": lesson}]})[0]
    assert selected["version"] == VERSION and selected["key"] == str(failed_evidence)
    assert selected["kind"] == "short_mate"
    state = start(
        failure_db,
        attempt_id="coaching",
        subject=subject,
        source_type="own-game",
        version=selected["version"],
        key=selected["key"],
    )
    assert state["objective"] == "mate_within_two"
    failure_db.close()
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
    from chess_coach.coaching_short_rehearsal import rehearsed_sources

    assert rehearsed_sources(db, subject, {str(evidence)}) == {}
    beginning = begin(db, evidence, subject, attempt="unassisted-alternative")
    beginning_fen = beginning["fen"]
    other = alternative(db, "unassisted-alternative")
    submit(db, "unassisted-alternative", subject, event_id="answer", move=other)
    assert process(db, subject)["outcomes"] == {"correct": 1}
    assert rehearsed_sources(db, subject, {str(evidence)}) == {}
    state = show(db, "unassisted-alternative", subject)
    board = chess.Board(state["fen"])
    mating_move = next(move for move in board.legal_moves if _is_mate(board, move))
    assert (
        submit(db, "unassisted-alternative", subject, event_id="finish", move=mating_move.uci())[
            "status"
        ]
        == "objective_verified"
    )
    assert rehearsed_sources(db, subject, {str(evidence)}) == {
        str(evidence): " ".join(beginning_fen.split()[:4])
    }
    from chess_coach.objective_current import current, short_terminal

    request = db.connection.execute(
        "SELECT * FROM objective_requests WHERE attempt_id=? AND event_id=?",
        ("unassisted-alternative", "answer"),
    ).fetchone()
    with pytest.raises(ValueError):
        current(db, request)
    assert short_terminal(db, request)[0]["status"] == "objective_verified"
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


def _is_mate(board, move):
    board.push(move)
    result = board.is_checkmate()
    board.pop()
    return result


@pytest.mark.parametrize(
    ("black", "form", "assisted"),
    [
        (False, "immediate_root", False),
        (True, "alternative_final", False),
        (False, "alternative_final", True),
        (True, "immediate_root", True),
    ],
)
def test_async_terminal_recognition_requires_correct_unassisted_proof(
    tmp_path, monkeypatch, black, form, assisted
):
    from chess_coach.coaching_short_rehearsal import rehearsed_sources
    from chess_coach.evidence_review import review_evidence

    db, evidence, subject = fixture(tmp_path / "terminal.sqlite", monkeypatch, black)
    state = begin(db, evidence, subject, attempt="terminal")
    source_fen = state["fen"]
    lines = json.loads(
        db.connection.execute(
            "SELECT lines_json FROM unified_sessions WHERE attempt_id='terminal'"
        ).fetchone()[0]
    )
    if form == "alternative_final":
        root = lines[0][0]
        state = submit(db, "terminal", subject, event_id="root", move=root)
        assert state["status"] == "active"
        board = chess.Board(state["fen"])
        selected = {line[2] for line in lines if line[:2] == [root, state["opponent_move"]]}
        move = next(
            move
            for move in board.legal_moves
            if _is_mate(board, move) and move.uci() not in selected
        )
    else:
        board = chess.Board(source_fen)
        move = next(move for move in board.legal_moves if _is_mate(board, move))
    if assisted:
        hint(db, "terminal", subject, event_id="hint")
    pending = submit(db, "terminal", subject, event_id="answer", move=move.uci())
    assert pending["status"] == "needs_verification"
    assert rehearsed_sources(db, subject, {str(evidence)}) == {}
    assert process(db, subject)["outcomes"] == {"correct": 1}
    assert show(db, "terminal", subject)["status"] == "objective_verified"
    assert (
        db.connection.execute(
            "SELECT status FROM unified_sessions WHERE attempt_id='terminal'"
        ).fetchone()[0]
        == "needs_verification"
    )
    expected = {} if assisted else {str(evidence): " ".join(source_fen.split()[:4])}
    assert rehearsed_sources(db, subject, {str(evidence)}) == expected
    review_evidence(db, evidence, decision="reject", actor="fixture_reviewer")
    assert rehearsed_sources(db, subject, {str(evidence)}) == {}
    db.close()


@pytest.mark.parametrize("outcome", ["incorrect", "cancelled"])
def test_async_noncorrect_root_never_advances(tmp_path, monkeypatch, outcome):
    from chess_coach.coaching_short_rehearsal import rehearsed_sources
    from chess_coach.objective_publication import cancel

    db, evidence, subject = fixture(tmp_path / "unverified.sqlite", monkeypatch)
    begin(db, evidence, subject, attempt="unverified")
    row = db.connection.execute(
        "SELECT lines_json,provenance_json FROM unified_sessions WHERE attempt_id='unverified'"
    ).fetchone()
    root = json.loads(row["lines_json"])[0][0]
    fact = db.connection.execute(
        "SELECT payload_json FROM detector_facts WHERE id=(SELECT fact_id FROM evidence_fact_links WHERE evidence_id=?)",
        (json.loads(row["provenance_json"])["evidence_id"],),
    ).fetchone()
    proofs = json.loads(fact[0])["proof"]["alternatives"]
    move = next(
        item["move"]["uci"]
        for item in proofs
        if item["status"] == "disproved" and item["move"]["uci"] != root
    )
    submit(db, "unverified", subject, event_id="answer", move=move)
    if outcome == "cancelled":
        assert cancel(db, subject, "unverified", "answer")["status"] == "unresolved"
    else:
        assert process(db, subject)["outcomes"] == {"incorrect": 1}
    assert rehearsed_sources(db, subject, {str(evidence)}) == {}
    db.close()
