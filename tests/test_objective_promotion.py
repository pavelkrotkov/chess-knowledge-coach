"""Explicit public promotion goals use durable bounded legal proof."""

import json
import re
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

    # A public collection version can equal an unrelated owned practice version.
    collision_version = "discovery-material-defense-own-v1"
    collision_content = tmp_path / "collision.csv"
    collision_content.write_bytes(CONTENT.read_bytes())
    collision_manifest = tmp_path / "collision-manifest.json"
    collision_manifest.write_text(
        json.dumps(json.loads(MANIFEST.read_text()) | {"version": collision_version}),
        encoding="utf-8",
    )
    assert (
        import_collection(
            db, collision_content, collision_content, collision_manifest, project_root=tmp_path
        )["accepted"]
        == 8
    )
    collision = client.post(
        "/unified/start",
        base_url="https://coach.invalid",
        headers=headers | {"Origin": "https://coach.invalid"},
        data={
            "csrf": csrf,
            "source_type": "public",
            "version": collision_version,
            "key": "direct-white",
        },
    )
    assert collision.status_code == 303
    collision_page = collision.headers["Location"]
    active = client.get(collision_page, base_url="https://coach.invalid", headers=headers)
    assert b"Objective: Promote a pawn now" in active.data
    assert b"discovered attack" not in active.data
    with client.session_transaction(base_url="https://coach.invalid") as browser:
        collision_attempt = browser["unified_attempt"]
    moved = client.post(
        "/unified/move",
        base_url="https://coach.invalid",
        headers=headers | {"Origin": "https://coach.invalid"},
        data={"csrf": csrf, "attempt": collision_attempt, "event": "collision", "move": "a7a8q"},
    )
    assert moved.status_code == 303
    pending = client.get(collision_page, base_url="https://coach.invalid", headers=headers)
    assert b"Verification queued" in pending.data and b"discovered attack" not in pending.data
    assert process(db, SUBJECT)["outcomes"] == {"correct": 1}
    verified = client.get(collision_page, base_url="https://coach.invalid", headers=headers)
    assert b"Verified correct" in verified.data and b"discovered attack" not in verified.data

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
    _canonical_learning_workflow(db, client, headers, monkeypatch)


def _canonical_learning_workflow(db, client, headers, monkeypatch):
    from chess_coach import unified_session_apply, unified_sessions
    from chess_coach.objective_publication import cancel
    from chess_coach.unified_session_events import hint, reveal
    from chess_coach.unified_training_complete import complete

    def enrolled(key, attempt, **kwargs):
        return start(
            db,
            attempt_id=attempt,
            subject=SUBJECT,
            source_type="public",
            version=VERSION,
            key=key,
            training=True,
            **kwargs,
        )

    with pytest.raises(ValueError, match="qualified training"):
        enrolled("forced-white", "forced-unavailable")
    with pytest.raises(ValueError, match="qualified training"):
        start(
            db,
            attempt_id="other-collection",
            subject=SUBJECT,
            source_type="public",
            version="discovery-material-defense-own-v1",
            key="direct-white",
            training=True,
        )
    with monkeypatch.context() as patch:
        patch.setattr(unified_sessions, "now", lambda: "2026-01-01T00:00:00+00:00")
        patch.setattr(unified_session_apply, "now", lambda: "2026-01-01T00:00:00+00:00")
        enrolled("stalemate-white", "canonical-learning")
        illegal = submit(db, "canonical-learning", SUBJECT, event_id="illegal", move="a7a5")
        assert illegal["feedback"] == "illegal" and illegal["status"] == "active"
        queued = submit(db, "canonical-learning", SUBJECT, event_id="answer", move="a7a8n")
    assert queued["status"] == "needs_verification"
    assert show(db, "canonical-learning", SUBJECT)["learning"]["state"] == "pending"
    assert process(db, SUBJECT)["outcomes"] == {"correct": 1}
    result = show(db, "canonical-learning", SUBJECT)
    learning = result["learning"]
    assert learning["state"] == "completed" and learning["outcome"] == "success"
    assert learning["rating"] == "good" and learning["evidence_id"]
    assert chess.Board(result["fen"]).is_stalemate()
    evidence = db.connection.execute(
        "SELECT * FROM evidence_mappings WHERE id=?", (learning["evidence_id"],)
    ).fetchone()
    assert json.loads(evidence["context_json"])["source"] == "unified_canonical_promotion"
    from chess_coach.mastery_unified_training import training_context

    context, error = training_context(db, evidence)
    assert context is not None and error is None
    assert (
        complete(db, "canonical-learning", SUBJECT, event_id="answer")["item_id"]
        == learning["item_id"]
    )
    assert submit(db, "canonical-learning", SUBJECT, event_id="answer", move="a7a8n") == queued
    reviewed = db.connection.execute(
        "SELECT reviewed_at FROM training_attempts WHERE item_id=?", (learning["item_id"],)
    ).fetchone()[0]
    assert reviewed == "2026-01-01T00:00:00+00:00"

    for query in (
        "SELECT id FROM training_items INDEXED BY idx_curriculum_source_due "
        "WHERE source_type='unified_canonical_promotion' AND skill='promotion' "
        "AND operation='execute' AND lower(due) != 'now' AND julianday(due)<=julianday('2027-01-01') "
        "ORDER BY julianday(due),id LIMIT 10",
        "SELECT id FROM training_items INDEXED BY idx_curriculum_source_scheduled "
        "WHERE source_type='unified_canonical_promotion' AND skill='promotion' "
        "AND operation='execute' AND id>0 ORDER BY id LIMIT 10",
    ):
        plan = [row[3] for row in db.connection.execute("EXPLAIN QUERY PLAN " + query)]
        assert any("idx_curriculum_source_" in detail for detail in plan)
        assert not any("TEMP B-TREE" in detail for detail in plan)

    with monkeypatch.context() as patch:
        from chess_coach import objective_promotion_root

        patch.setattr(objective_promotion_root, "scan", lambda *_: pytest.fail("solver on GET"))
        page = client.get("/plan", base_url="https://coach.invalid", headers=headers)
    assert page.status_code == 200 and b"Scheduled review is due." in page.data
    assert b'name="source_type" value="public"' in page.data
    assert f'name="item_id" value="{learning["item_id"]}"'.encode() in page.data
    with client.session_transaction(base_url="https://coach.invalid") as browser:
        csrf = browser["csrf"]
    opened = client.post(
        "/unified/start",
        base_url="https://coach.invalid",
        headers=headers | {"Origin": "https://coach.invalid"},
        data={
            "csrf": csrf,
            "source_type": "public",
            "version": VERSION,
            "key": "stalemate-white",
            "training": "1",
            "item_id": str(learning["item_id"]),
        },
    )
    assert opened.status_code == 303
    reopened = opened.headers["Location"].rsplit("/", 1)[-1]
    assert (
        db.connection.execute(
            "SELECT item_id FROM unified_training_enrollments WHERE attempt_id=?", (reopened,)
        ).fetchone()[0]
        == learning["item_id"]
    )

    practice = client.get(
        opened.headers["Location"], base_url="https://coach.invalid", headers=headers
    )
    event_match = re.search(r'name="event" value="([^"]+)"', practice.get_data(as_text=True))
    assert event_match is not None
    played = client.post(
        "/unified/move",
        base_url="https://coach.invalid",
        headers=headers | {"Origin": "https://coach.invalid"},
        data={"csrf": csrf, "attempt": reopened, "event": event_match.group(1), "move": "a7a8n"},
    )
    assert played.status_code == 303
    assert process(db, SUBJECT)["outcomes"] == {"correct": 1}
    assert show(db, reopened, SUBJECT)["learning"]["item_id"] == learning["item_id"]
    with pytest.raises(ValueError, match="training item"):
        start(
            db,
            attempt_id="other-owner",
            subject="other",
            source_type="public",
            version=VERSION,
            key="stalemate-white",
            training=True,
            item_id=learning["item_id"],
        )

    # Every legal choice of promotion piece is a success, not a winning claim.
    for piece in "qrbn":
        attempt = "piece-" + piece
        enrolled("direct-white", attempt)
        submit(db, attempt, SUBJECT, event_id="answer", move="a7a8" + piece)
    assert process(db, SUBJECT, limit=4)["outcomes"] == {"correct": 4}
    for piece in "qrbn":
        assert show(db, "piece-" + piece, SUBJECT)["learning"]["outcome"] == "success"

    # A normalized worker request must still complete the exact original owner.
    start(
        db,
        attempt_id="mixed-owner",
        subject="Fixture_Learner",
        source_type="public",
        version=VERSION,
        key="direct-black",
        training=True,
    )
    submit(db, "mixed-owner", "Fixture_Learner", event_id="answer", move="a2a1q")
    assert process(db, SUBJECT)["outcomes"] == {"correct": 1}
    assert show(db, "mixed-owner", "Fixture_Learner")["learning"]["outcome"] == "success"

    enrolled("capture-black", "black-learning")
    submit(db, "black-learning", SUBJECT, event_id="answer", move="b2a1n")
    assert process(db, SUBJECT)["outcomes"] == {"correct": 1}
    assert show(db, "black-learning", SUBJECT)["learning"]["outcome"] == "success"

    enrolled("direct-white", "assisted-learning")
    hint(db, "assisted-learning", SUBJECT, event_id="hint")
    reveal(db, "assisted-learning", SUBJECT, event_id="reveal")
    submit(db, "assisted-learning", SUBJECT, event_id="answer", move="a7a8r")
    assert process(db, SUBJECT)["outcomes"] == {"correct": 1}
    assisted = show(db, "assisted-learning", SUBJECT)["learning"]
    assert assisted["assistance"] == "assisted"
    assert assisted["evidence_id"] is None and assisted["rating"] is None

    enrolled("direct-white", "miss-learning")
    submit(db, "miss-learning", SUBJECT, event_id="answer", move="h1h2")
    assert process(db, SUBJECT)["outcomes"] == {"incorrect": 1}
    missed = show(db, "miss-learning", SUBJECT)["learning"]
    assert missed["outcome"] == "failure" and missed["rating"] == "again"
    event_time = db.connection.execute(
        "SELECT created_at FROM unified_session_events WHERE attempt_id='miss-learning' AND event_id='answer'"
    ).fetchone()[0]
    review_time = db.connection.execute(
        """SELECT t.reviewed_at FROM training_attempts t JOIN unified_training_completions c
        ON c.training_attempt_id=t.id WHERE c.attempt_id='miss-learning'"""
    ).fetchone()[0]
    assert event_time == review_time

    enrolled("direct-black", "cancelled-learning")
    submit(db, "cancelled-learning", SUBJECT, event_id="answer", move="a2a1q")
    cancel(db, SUBJECT, "cancelled-learning", "answer")
    with pytest.raises(ValueError):
        complete(db, "cancelled-learning", SUBJECT, event_id="answer")
    assert (
        db.connection.execute(
            "SELECT count(*) FROM unified_training_completions WHERE attempt_id='cancelled-learning'"
        ).fetchone()[0]
        == 0
    )

    enrolled("direct-black", "stale-catalog")
    submit(db, "stale-catalog", SUBJECT, event_id="answer", move="a2a1q")
    with monkeypatch.context() as patch:
        patch.setattr("chess_coach.plan_promotion_catalog.TASKS", "0" * 64)
        assert process(db, SUBJECT)["outcomes"] == {"correct": 1}
        with pytest.raises(ValueError):
            complete(db, "stale-catalog", SUBJECT, event_id="answer")
        assert training_context(db, evidence) == (None, "invalid_training_lineage")
    assert complete(db, "stale-catalog", SUBJECT, event_id="answer")["outcome"] == "success"
