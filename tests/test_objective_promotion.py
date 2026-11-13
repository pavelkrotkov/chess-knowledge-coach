"""Explicit public promotion goals use durable bounded legal proof."""

from pathlib import Path

import chess
import pytest

from chess_coach.db import Database
from chess_coach.objective_promotion_contract import FORCE, NOW
from chess_coach.objective_promotion_judge import judge
from chess_coach.objective_worker import process
from chess_coach.public_training import import_collection
from chess_coach.unified_session_events import show, submit
from chess_coach.unified_sessions import start

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "src/chess_coach/data/promotion_objectives/canonical.csv"
MANIFEST = ROOT / "src/chess_coach/data/promotion_objectives/manifest.json"
VERSION = "canonical-promotion-v1"
SUBJECT = "fixture_learner"


def setup_db(path):
    db = Database(path)
    db.initialize()
    result = import_collection(db, CONTENT, CONTENT, MANIFEST, project_root=ROOT)
    assert result == {"version": VERSION, "accepted": 8, "excluded": 0}
    return db


def begin(db, key, attempt):
    return start(
        db, attempt_id=attempt, subject=SUBJECT, source_type="public", version=VERSION, key=key
    )


def oriented(text, black):
    move = chess.Move.from_uci(text)
    if black:
        move = chess.Move(
            chess.square_mirror(move.from_square),
            chess.square_mirror(move.to_square),
            promotion=move.promotion,
        )
    return move.uci()


@pytest.mark.parametrize("black", [False, True])
def test_immediate_promotion_including_stalemate_and_capture(black):
    board = chess.Board("7k/P4K2/8/5B2/8/8/8/8 w - - 0 1")
    if black:
        board = board.mirror()
    move = board.parse_uci(oriented("a7a8n", black))
    result = judge(board, move, NOW, lambda: 0.0, 0.0, 5.0, {})
    assert result["status"] == "correct" and result["reason"] == "promotion_performed"
    board.push(move)
    assert board.is_stalemate()
    capture = chess.Board("r6k/1PK5/8/8/8/8/8/8 w - - 0 1")
    if black:
        capture = capture.mirror()
    move = capture.parse_uci(oriented("b7a8n", black))
    assert (
        capture.is_capture(move)
        and judge(capture, move, NOW, lambda: 0.0, 0.0, 5.0, {})["status"] == "correct"
    )


def test_imported_source_queues_exemplar_and_resumes_every_defense(tmp_path, monkeypatch):
    from chess_coach.objective_publication import cancel
    from chess_coach.plan_promotion import recommendation
    from chess_coach.unified_session_events import hint, reveal
    from chess_coach.web import create_app

    path = tmp_path / "promotion.sqlite"
    db = setup_db(path)
    before = db.connection.execute("SELECT COUNT(*) FROM evidence_mappings").fetchone()[0]
    mastery_before = db.connection.execute("SELECT COUNT(*) FROM mastery_states").fetchone()[0]
    assert recommendation(db, SUBJECT)["key"] == "direct-white"

    # Correct forcing roots are unfinished until their promoting continuation.
    for index in range(26):
        attempt = f"unfinished-{index}"
        begin(db, "forced-white", attempt)
        submit(db, attempt, SUBJECT, event_id="root", move="a6a7")
    assert process(db, SUBJECT, limit=20)["outcomes"] == {"correct": 20}
    assert process(db, SUBJECT, limit=20)["outcomes"] == {"correct": 6}
    assert recommendation(db, SUBJECT)["key"] == "direct-white"

    # An absent or changed canonical collection is explicitly unavailable.
    missing = Database(tmp_path / "missing.sqlite")
    missing.initialize()
    assert recommendation(missing, SUBJECT)["status"] == "unavailable"
    missing.close()
    with monkeypatch.context() as patch:
        patch.setattr("chess_coach.plan_promotion_catalog.TASKS", "0" * 64)
        assert recommendation(db, SUBJECT)["status"] == "unavailable"

    # The private plan is read-only and starts through the existing public form.
    app = create_app(
        db_path=path,
        subject=SUBJECT,
        actor="fixture",
        corpus="none",
        login="fixture",
        origin="https://coach.invalid",
    )
    client = app.test_client()
    headers = {"Tailscale-User-Login": "fixture"}
    assert client.get("/plan", base_url="https://coach.invalid").status_code == 403
    data_version = db.connection.execute("PRAGMA data_version").fetchone()[0]
    page = client.get("/plan", base_url="https://coach.invalid", headers=headers)
    assert page.status_code == 200 and b"Optional promotion practice" in page.data
    assert b"Play White" in page.data and b"Promote a pawn now" in page.data
    assert db.connection.execute("PRAGMA data_version").fetchone()[0] == data_version
    assert db.connection.execute("SELECT COUNT(*) FROM unified_sessions").fetchone()[0] == 26
    with client.session_transaction(base_url="https://coach.invalid") as browser:
        csrf = browser["csrf"]
    assert (
        client.post(
            "/unified/start",
            base_url="https://coach.invalid",
            headers=headers | {"Origin": "https://coach.invalid"},
            data={"csrf": csrf, "source_type": "public", "version": VERSION, "key": "direct-white"},
        ).status_code
        == 303
    )

    # Pending, unresolved and assisted answers cannot advance the card.
    begin(db, "direct-white", "unresolved")
    submit(db, "unresolved", SUBJECT, event_id="root", move="a7a8q")
    assert recommendation(db, SUBJECT)["key"] == "direct-white"
    cancel(db, SUBJECT, "unresolved", "root")
    assert recommendation(db, SUBJECT)["key"] == "direct-white"
    begin(db, "direct-white", "hinted-white")
    hint(db, "hinted-white", SUBJECT, event_id="hint")
    submit(db, "hinted-white", SUBJECT, event_id="root", move="a7a8q")
    assert process(db, SUBJECT)["outcomes"] == {"correct": 1}
    assert recommendation(db, SUBJECT)["key"] == "direct-white"

    start(
        db,
        attempt_id="other-black",
        subject="other",
        source_type="public",
        version=VERSION,
        key="direct-black",
    )
    submit(db, "other-black", "other", event_id="root", move="a2a1q")
    assert process(db, "other")["outcomes"] == {"correct": 1}
    assert recommendation(db, SUBJECT)["key"] == "direct-white"

    begin(db, "capture-white", "white")
    submit(db, "white", SUBJECT, event_id="root", move="b7a8q")
    assert process(db, SUBJECT)["outcomes"] == {"correct": 1}
    assert recommendation(db, SUBJECT)["key"] == "direct-black"
    black_page = client.get("/plan", base_url="https://coach.invalid", headers=headers)
    assert b"Play Black" in black_page.data and b"Promote a pawn now" in black_page.data
    begin(db, "capture-white", "white-again")
    submit(db, "white-again", SUBJECT, event_id="root", move="b7a8q")
    assert process(db, SUBJECT)["outcomes"] == {"correct": 1}
    # Repeated completions and nonqualifying attempts do not consume another task's scan.
    with monkeypatch.context() as patch:
        patch.setattr("chess_coach.plan_promotion_history.LIMIT", 1)
        assert recommendation(db, SUBJECT)["key"] == "direct-black"
    begin(db, "direct-black", "black")
    submit(db, "black", SUBJECT, event_id="root", move="a2a1q")
    assert process(db, SUBJECT)["outcomes"] == {"correct": 1}
    assert recommendation(db, SUBJECT)["key"] == "forced-white"
    forcing_page = client.get("/plan", base_url="https://coach.invalid", headers=headers)
    assert (
        b"Play White" in forcing_page.data
        and b"Force a promotion within two moves" in forcing_page.data
    )
    with monkeypatch.context() as patch:
        patch.setattr("chess_coach.unified_source_current.snapshot_hash", lambda _source: "0" * 64)
        assert recommendation(db, SUBJECT)["key"] == "direct-white"

    state = begin(db, "forced-white", "forced")
    assert state["objective"] == FORCE
    original = submit(db, "forced", SUBJECT, event_id="root", move="a6a7")
    assert original["feedback"] == "needs_verification"
    frozen = db.connection.execute(
        "SELECT response_json FROM unified_session_events WHERE event_id=? AND attempt_id=?",
        ("root", "forced"),
    ).fetchone()[0]
    assert process(db, SUBJECT)["outcomes"] == {"correct": 1}
    resumed = show(db, "forced", SUBJECT)
    assert resumed["status"] == "active" and resumed["promotion_continuation"]
    assert recommendation(db, SUBJECT)["key"] == "forced-white"
    reveal(db, "forced", SUBJECT, event_id="after-proof")
    board = chess.Board(resumed["fen"])
    move = next(move for move in board.legal_moves if move.promotion == chess.KNIGHT)
    final = submit(db, "forced", SUBJECT, event_id="final", move=move.uci())
    assert final["status"] == "objective_verified"
    assert recommendation(db, SUBJECT)["key"] == "forced-white"
    assert submit(db, "forced", SUBJECT, event_id="root", move="a6a7") == original
    assert (
        db.connection.execute(
            "SELECT response_json FROM unified_session_events WHERE event_id=? AND attempt_id=?",
            ("root", "forced"),
        ).fetchone()[0]
        == frozen
    )

    for color, root_move in (("white", "a6a7"), ("black", "a3a2")):
        attempt = "clean-" + color
        assert recommendation(db, SUBJECT)["key"] == "forced-" + color
        begin(db, "forced-" + color, attempt)
        submit(db, attempt, SUBJECT, event_id="root", move=root_move)
        assert process(db, SUBJECT)["outcomes"] == {"correct": 1}
        resumed = show(db, attempt, SUBJECT)
        board = chess.Board(resumed["fen"])
        move = next(move for move in board.legal_moves if move.promotion)
        assert (
            submit(db, attempt, SUBJECT, event_id="final", move=move.uci())["status"]
            == "objective_verified"
        )
    assert recommendation(db, SUBJECT)["status"] == "complete"
    complete_page = client.get("/plan", base_url="https://coach.invalid", headers=headers)
    assert b"completed the two-color promotion sequence" in complete_page.data
    library = client.get("/library", base_url="https://coach.invalid", headers=headers)
    assert all(
        key in library.data
        for key in (b"direct-white", b"capture-black", b"forced-white", b"forced-black")
    )
    assert db.connection.execute("SELECT COUNT(*) FROM evidence_mappings").fetchone()[0] == before
    assert (
        db.connection.execute("SELECT COUNT(*) FROM mastery_states").fetchone()[0] == mastery_before
    )
