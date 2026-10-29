"""Synthetic original-history proof for a specified threatened piece."""

import json

import chess
import pytest

from chess_coach.evidence_review import review_evidence
from chess_coach.material_detector import process_decision
from chess_coach.objective_protection_contract import VERSION
from chess_coach.objective_protection_judge import judge
from chess_coach.objective_status import inspect
from chess_coach.objective_worker import process
from chess_coach.unified_session_events import show, submit
from chess_coach.unified_sessions import start
from tests.test_material_pipeline import LEARNER, make_protection_game


def oriented(text, black):
    move = chess.Move.from_uci(text)
    if black:
        move = chess.Move(
            chess.square_mirror(move.from_square), chess.square_mirror(move.to_square)
        )
    return move.uci()


def fixture(path, monkeypatch, black=False, played="a2a3"):
    db = make_protection_game(path, monkeypatch, color="black" if black else "white", played=played)
    evidence = process_decision(db, 1, LEARNER)["evidence_ids"][0]
    return db, evidence


def begin(db, evidence, attempt):
    return start(
        db,
        attempt_id=attempt,
        subject=LEARNER,
        source_type="own-game",
        version=VERSION,
        key=str(evidence),
    )


@pytest.mark.parametrize("black", [False, True])
def test_alternative_defense_and_concrete_refutation(tmp_path, monkeypatch, black):
    db, evidence = fixture(tmp_path / "protect.sqlite", monkeypatch, black)
    tracked = (
        "evidence_mappings",
        "evidence_review_events",
        "mastery_states",
        "mastery_events",
        "training_items",
        "training_attempts",
        "training_completions",
    )
    counts = {
        table: db.connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        for table in tracked
    }
    initial = begin(db, evidence, "safe")
    assert initial["objective_target"] == ("d5" if black else "d4")
    assert initial["gain_threshold"] == 3
    safe = oriented("d4d3", black)
    unsafe = oriented("h1g2", black)
    original = submit(db, "safe", LEARNER, event_id="move", move=safe)
    assert original["feedback"] == "needs_verification"
    frozen = db.connection.execute("SELECT response_json FROM unified_session_events").fetchone()[0]
    assert process(db, LEARNER)["outcomes"] == {"correct": 1}
    assert inspect(db, LEARNER, "safe", "move")["reason"] == "no_profitable_immediate_capture"
    assert submit(db, "safe", LEARNER, event_id="move", move=safe) == original
    assert (
        db.connection.execute("SELECT response_json FROM unified_session_events").fetchone()[0]
        == frozen
    )
    begin(db, evidence, "unsafe")
    submit(db, "unsafe", LEARNER, event_id="move", move=unsafe)
    assert process(db, LEARNER)["outcomes"] == {"incorrect": 1}
    result = json.loads(
        db.connection.execute(
            "SELECT result_json FROM objective_results WHERE attempt_id=?", ("unsafe",)
        ).fetchone()[0]
    )
    assert result["capture_reply"] == oriented("c5d4", black)
    assert result["learning_eligible"] is False
    assert show(db, "safe", LEARNER)["verification"]["status"] == "correct"
    assert {
        table: db.connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        for table in tracked
    } == counts


@pytest.mark.parametrize("black", [False, True])
def test_success_source_binds_original_piece_not_historical_destination(
    tmp_path, monkeypatch, black
):
    db, evidence = fixture(tmp_path / "moved.sqlite", monkeypatch, black, played="d4d5")
    state = begin(db, evidence, "moved")
    assert state["objective_target"] == ("d5" if black else "d4")
    board = chess.Board(state["fen"])
    assert board.piece_at(chess.parse_square(state["objective_target"])) == chess.Piece(
        chess.ROOK, not black
    )


@pytest.mark.parametrize("black", [False, True])
def test_countercapture_defense_and_unsupported_defender_exchange(black):
    board = chess.Board("4k3/8/8/R1b5/3R4/8/P7/7K w - - 0 1")
    if black:
        board = board.mirror()
    target = chess.D5 if black else chess.D4
    move = board.parse_uci(oriented("a5c5", black))
    result = judge(board, move, target, lambda: 0.0, 0.0, 5.0, {})
    assert result["status"] == "correct"
    board = chess.Board("4k3/8/8/2b5/3R4/8/P7/6NK w - - 0 1")
    if black:
        board = board.mirror()
    move = board.parse_uci(oriented("g1f3", black))
    result = judge(board, move, target, lambda: 0.0, 0.0, 5.0, {})
    assert result["status"] == "unresolved"


def test_other_captures_and_checking_replies_remain_unresolved():
    board = chess.Board("4k3/8/8/2b5/3R4/8/P7/7K w - - 0 1")
    pawn = judge(board, board.parse_uci("a2a3"), chess.D4, lambda: 0.0, 0.0, 5.0, {})
    assert pawn["reason"] == "other_capture_unresolved"
    king = judge(board, board.parse_uci("h1h2"), chess.D4, lambda: 0.0, 0.0, 5.0, {})
    assert king["reason"] == "checking_reply_unresolved"


def test_incomplete_threat_or_check_stays_unresolved(monkeypatch):
    import chess_coach.objective_protection_before as module

    board = chess.Board("4k3/8/8/2b5/3R4/8/P7/7K w - - 0 1")
    move = board.parse_uci("d4d3")
    assert judge(board, move, chess.D4, lambda: 9.0, 0.0, 5.0, {})["reason"] == "timeout"
    monkeypatch.setattr(module, "MAX_CAPTURES", 0)
    assert (
        judge(board, move, chess.D4, lambda: 0.0, 0.0, 5.0, {})["reason"]
        == "original_threat_unresolved"
    )
    checking = chess.Board("4k3/8/8/2b5/3R4/8/P7/7K w - - 0 1")
    assert (
        judge(checking, checking.parse_uci("d4d8"), chess.D4, lambda: 0.0, 0.0, 5.0, {})["status"]
        == "unresolved"
    )


def test_review_change_before_publication_invalidates_verdict(tmp_path, monkeypatch):
    from chess_coach.objective_verify import compute

    db, evidence = fixture(tmp_path / "race.sqlite", monkeypatch)
    begin(db, evidence, "race")
    submit(db, "race", LEARNER, event_id="move", move="d4d3")

    def revoke(database, request, clock, *, seconds):
        result = compute(database, request, clock, seconds=seconds)
        assert result["status"] == "correct"
        review_evidence(database, evidence, decision="reject", actor="fixture_reviewer")
        return result

    assert process(db, LEARNER, verifier=revoke)["outcomes"] == {"unresolved": 1}
    data = json.loads(
        db.connection.execute("SELECT result_json FROM objective_results").fetchone()[0]
    )
    assert data["reason"] == "source_unavailable" and data["learning_eligible"] is False


def test_original_other_capture_is_not_ignored():
    from chess_coach.objective_protection_before import probe

    board = chess.Board("4k3/8/8/2b5/3R4/P7/8/7K w - - 0 1")
    assert probe(board) is None


def test_original_repetition_history_is_not_erased_by_hypothetical_probe():
    board = chess.Board("4k3/8/8/2b5/3R4/8/P7/7K w - - 0 1")
    for text in ("h1g2", "e8f8", "g2h1", "f8e8"):
        board.push_uci(text)
    assert board.is_repetition(2)
    result = judge(board, board.parse_uci("d4d3"), chess.D4, lambda: 0.0, 0.0, 5.0, {})
    assert result["status"] == "unresolved" and result["reason"] == "terminal_or_claimable_history"


@pytest.mark.parametrize(
    "field,value",
    [
        ("producer", "other"),
        ("mapper_version", "other"),
        ("subject", "other"),
        ("operation", "execute"),
        ("position_id", 2),
        ("scope_key", "other"),
        ("status", "superseded"),
    ],
)
def test_changed_mapping_identity_rejects_owned_protection(tmp_path, monkeypatch, field, value):
    db, evidence = fixture(tmp_path / "identity.sqlite", monkeypatch)
    run = db.connection.execute(
        "SELECT mapping_run_id FROM evidence_mappings WHERE id=?", (evidence,)
    ).fetchone()[0]
    db.connection.execute(f"UPDATE mapping_runs SET {field}=? WHERE id=?", (value, run))
    db.connection.commit()
    with pytest.raises(ValueError):
        begin(db, evidence, "stale")


def test_browser_and_cli_queue_resume_the_specified_piece(tmp_path, monkeypatch, capsys):
    from argparse import Namespace

    from chess_coach.cli_unified_practice import handle_show, handle_start
    from chess_coach.db import Database
    from chess_coach.web import create_app
    from tests.test_unified_sessions import token

    path = tmp_path / "browser.sqlite"
    db, evidence = fixture(path, monkeypatch)
    handle_start(
        db,
        Namespace(
            attempt="cli", subject=LEARNER, source="own-game", version=VERSION, key=str(evidence)
        ),
    )
    assert json.loads(capsys.readouterr().out)["objective_target"] == "d4"
    handle_show(db, Namespace(attempt="cli", subject=LEARNER))
    assert json.loads(capsys.readouterr().out)["gain_threshold"] == 3
    db.close()
    app = create_app(
        db_path=path,
        subject=LEARNER,
        actor="operator",
        corpus="legacy",
        login="fixture",
        origin="https://coach.invalid",
    )
    client = app.test_client()
    headers = {"Tailscale-User-Login": "fixture"}
    library = client.get("/library", base_url="https://coach.invalid", headers=headers)
    assert library.status_code == 200 and b"Verify and practice piece defense" in library.data
    post = client.post(
        "/unified/start",
        base_url="https://coach.invalid",
        headers=headers | {"Origin": "https://coach.invalid"},
        data={
            "csrf": token(library, "csrf"),
            "source_type": "own-game",
            "version": VERSION,
            "key": str(evidence),
        },
    )
    assert post.status_code == 303
    page = client.get(post.headers["Location"], base_url="https://coach.invalid", headers=headers)
    assert b"Save the piece on d4" in page.data and b"at least 3 material points" in page.data
    move = client.post(
        "/unified/move",
        base_url="https://coach.invalid",
        headers=headers | {"Origin": "https://coach.invalid"},
        data={
            "csrf": token(page, "csrf"),
            "attempt": token(page, "attempt"),
            "event": token(page, "event"),
            "move": "d4d3",
        },
    )
    assert move.status_code == 303
    pending = client.get(
        move.headers["Location"], base_url="https://coach.invalid", headers=headers
    )
    assert b"Verification is queued" in pending.data
    db = Database(path)
    assert process(db, LEARNER)["outcomes"] == {"correct": 1}
    db.close()
    resumed = client.get(
        move.headers["Location"], base_url="https://coach.invalid", headers=headers
    )
    assert b"no supported immediate profitable capture" in resumed.data
