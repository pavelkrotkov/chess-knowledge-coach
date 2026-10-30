"""Explicit public promotion goals use durable bounded legal proof."""

import json
from pathlib import Path

import chess
import pytest

from chess_coach.db import Database
from chess_coach.objective_promotion_contract import FORCE, NOW
from chess_coach.objective_promotion_judge import judge
from chess_coach.objective_status import inspect
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


@pytest.mark.parametrize("black", [False, True])
def test_forced_two_checks_every_legal_reply_and_finds_refutation(black):
    board = chess.Board("7k/8/P1K5/8/8/8/8/8 w - - 0 1")
    if black:
        board = board.mirror()
    move = board.parse_uci(oriented("a6a7", black))
    result = judge(board, move, FORCE, lambda: 0.0, 0.0, 5.0, {})
    assert result["status"] == "correct"
    board.push(move)
    assert {item["reply"] for item in result["proof"]["witnesses"]} == {
        reply.uci() for reply in board.legal_moves
    }
    bad = chess.Board("1k6/8/P1K5/8/8/8/8/8 w - - 0 1")
    if black:
        bad = bad.mirror()
    root = bad.parse_uci(oriented("a6a7", black))
    result = judge(bad, root, FORCE, lambda: 0.0, 0.0, 5.0, {})
    assert result["status"] == "incorrect"
    bad.push(root)
    reply = bad.parse_uci(result["proof"]["reply"])
    assert reply in bad.legal_moves
    bad.push(reply)
    assert bad.outcome(claim_draw=False) is not None or not any(
        move.promotion for move in bad.legal_moves
    )


def test_timeout_history_and_budget_are_unresolved(monkeypatch):
    import chess_coach.objective_promotion_root as module

    board = chess.Board("7k/8/P1K5/8/8/8/8/8 w - - 0 1")
    move = board.parse_uci("a6a7")
    assert judge(board, move, FORCE, lambda: 10.0, 0.0, 5.0, {})["reason"] == "timeout"
    monkeypatch.setattr(module, "MAX_NODES", 1)
    assert judge(board, move, FORCE, lambda: 0.0, 0.0, 5.0, {})["status"] == "unresolved"
    unknown = chess.Board("7k/8/P1K5/8/8/8/8/8 w - - 9 1")
    assert (
        judge(unknown, unknown.parse_uci("a6a7"), FORCE, lambda: 0.0, 0.0, 5.0, {})["status"]
        == "unresolved"
    )


def test_imported_source_queues_exemplar_and_resumes_every_defense(tmp_path):
    db = setup_db(tmp_path / "promotion.sqlite")
    before = db.connection.execute("SELECT COUNT(*) FROM evidence_mappings").fetchone()[0]
    state = begin(db, "forced-white", "forced")
    assert state["objective"] == FORCE
    original = submit(db, "forced", SUBJECT, event_id="root", move="a6a7")
    assert original["feedback"] == "needs_verification"
    frozen = db.connection.execute(
        "SELECT response_json FROM unified_session_events WHERE event_id=?", ("root",)
    ).fetchone()[0]
    assert process(db, SUBJECT)["outcomes"] == {"correct": 1}
    resumed = show(db, "forced", SUBJECT)
    assert resumed["status"] == "active" and resumed["promotion_continuation"]
    board = chess.Board(resumed["fen"])
    move = next(move for move in board.legal_moves if move.promotion == chess.KNIGHT)
    final = submit(db, "forced", SUBJECT, event_id="final", move=move.uci())
    assert final["status"] == "objective_verified"
    assert submit(db, "forced", SUBJECT, event_id="root", move="a6a7") == original
    assert (
        db.connection.execute(
            "SELECT response_json FROM unified_session_events WHERE event_id=?", ("root",)
        ).fetchone()[0]
        == frozen
    )
    assert db.connection.execute("SELECT COUNT(*) FROM evidence_mappings").fetchone()[0] == before


def test_public_immediate_stalemate_is_promotion_not_a_win(tmp_path):
    db = setup_db(tmp_path / "stalemate.sqlite")
    begin(db, "stalemate-white", "now")
    assert (
        submit(db, "now", SUBJECT, event_id="move", move="a7a8n")["feedback"]
        == "needs_verification"
    )
    assert process(db, SUBJECT)["outcomes"] == {"correct": 1}
    result = inspect(db, SUBJECT, "now", "move")
    assert result["reason"] == "promotion_performed"
    state = show(db, "now", SUBJECT)
    assert state["status"] == "objective_verified" and chess.Board(state["fen"]).is_stalemate()


def test_source_change_before_publication_cancels_verdict(tmp_path, monkeypatch):
    from chess_coach import unified_sources
    from chess_coach.objective_verify import compute

    db = setup_db(tmp_path / "race.sqlite")
    begin(db, "direct-white", "race")
    submit(db, "race", SUBJECT, event_id="move", move="a7a8q")

    def change_source(database, request, clock, *, seconds):
        result = compute(database, request, clock, seconds=seconds)
        assert result["status"] == "correct"
        monkeypatch.setattr(unified_sources, "public_task", lambda *args: None)
        return result

    assert process(db, SUBJECT, verifier=change_source)["outcomes"] == {"unresolved": 1}
    result = json.loads(
        db.connection.execute("SELECT result_json FROM objective_results").fetchone()[0]
    )
    assert result["reason"] == "source_unavailable" and result["learning_eligible"] is False


def test_generic_promotion_and_owned_wdl_are_not_upgraded(tmp_path):
    from chess_coach.public_training import import_collection
    from tests.test_public_training import file_set

    source, manifest, _ = file_set(
        tmp_path,
        rows=[
            ("generic", "8/P7/8/8/8/8/8/k6K w - - 0 1", "promotion", ["a7a8q"]),
        ],
    )
    db = Database(tmp_path / "legacy.sqlite")
    db.initialize()
    import_collection(db, source, source, manifest, project_root=tmp_path)
    start(
        db,
        attempt_id="legacy",
        subject=SUBJECT,
        source_type="public",
        version="fixture",
        key="generic",
    )
    result = submit(db, "legacy", SUBJECT, event_id="move", move="a7a8q")
    assert result["status"] == "line_completed"
    assert db.connection.execute("SELECT COUNT(*) FROM objective_requests").fetchone()[0] == 0


def test_cli_import_and_browser_continuation(tmp_path, monkeypatch, capsys):
    from argparse import Namespace

    from chess_coach.cli_public_training import handle_import
    from chess_coach.cli_unified_practice import handle_show, handle_start
    from chess_coach.web import create_app
    from tests.test_unified_sessions import token

    path = tmp_path / "browser.sqlite"
    db = Database(path)
    db.initialize()
    handle_import(
        db, Namespace(content=CONTENT, source=CONTENT, manifest=MANIFEST, project_root=ROOT)
    )
    assert json.loads(capsys.readouterr().out) == {"version": VERSION, "accepted": 8, "excluded": 0}
    handle_start(
        db,
        Namespace(
            attempt="cli", subject=SUBJECT, source="public", version=VERSION, key="forced-white"
        ),
    )
    cli_start = json.loads(capsys.readouterr().out)
    assert cli_start["objective"] == FORCE and "a6a7" not in json.dumps(cli_start)
    handle_show(db, Namespace(attempt="cli", subject=SUBJECT))
    assert json.loads(capsys.readouterr().out)["status"] == "active"
    db.close()
    app = create_app(
        db_path=path,
        subject=SUBJECT,
        actor="operator",
        corpus="legacy",
        login="fixture",
        origin="https://coach.invalid",
    )
    client = app.test_client()
    headers = {"Tailscale-User-Login": "fixture"}
    library = client.get("/library", base_url="https://coach.invalid", headers=headers)
    assert library.status_code == 200 and b"canonical-promotion-v1" in library.data
    assert b"a6a7" not in library.data
    response = client.post(
        "/unified/start",
        base_url="https://coach.invalid",
        headers=headers | {"Origin": "https://coach.invalid"},
        data={
            "csrf": token(library, "csrf"),
            "source_type": "public",
            "version": VERSION,
            "key": "forced-white",
        },
    )
    assert response.status_code == 303
    page = client.get(
        response.headers["Location"], base_url="https://coach.invalid", headers=headers
    )
    assert b"Force promotion within two moves" in page.data and b"a6a7" not in page.data
    attempt = token(page, "attempt")
    post = client.post(
        "/unified/move",
        base_url="https://coach.invalid",
        headers=headers | {"Origin": "https://coach.invalid"},
        data={
            "csrf": token(page, "csrf"),
            "attempt": attempt,
            "event": token(page, "event"),
            "move": "a6a7",
        },
    )
    assert post.status_code == 303
    db = Database(path)
    assert process(db, SUBJECT)["outcomes"] == {"correct": 1}
    state = show(db, attempt, SUBJECT)
    promotion = next(
        move for move in chess.Board(state["fen"]).legal_moves if move.promotion == chess.KNIGHT
    )
    db.close()
    resumed = client.get(
        post.headers["Location"], base_url="https://coach.invalid", headers=headers
    )
    assert (
        b"proved against every legal defense" in resumed.data
        and b"does not establish a win" in resumed.data
    )
    final = client.post(
        "/unified/move",
        base_url="https://coach.invalid",
        headers=headers | {"Origin": "https://coach.invalid"},
        data={
            "csrf": token(resumed, "csrf"),
            "attempt": attempt,
            "event": token(resumed, "event"),
            "move": promotion.uci(),
        },
    )
    assert final.status_code == 303
    complete = client.get(
        final.headers["Location"], base_url="https://coach.invalid", headers=headers
    )
    assert b"Promotion verified" in complete.data and b"does not establish a win" in complete.data


def test_all_authored_tasks_are_independently_admitted(tmp_path):
    from chess_coach.public_training_query import tasks

    db = setup_db(tmp_path / "admission.sqlite")
    items = tasks(db, VERSION)
    assert len(items) == 8
    for item in items:
        state = begin(db, item["task_id"], "task-" + item["task_id"])
        assert state["status"] == "active" and state["objective"] in {NOW, FORCE}


def test_claimed_forced_line_is_rejected_when_one_defense_refutes(tmp_path):
    from tests.test_public_training import file_set

    fen = "1k6/8/P1K5/8/8/8/8/8 w - - 0 1"
    source, manifest, _ = file_set(tmp_path, rows=[("false", fen, FORCE, ["a6a7 b8c8 a7a8q"])])
    db = Database(tmp_path / "false.sqlite")
    db.initialize()
    assert import_collection(db, source, source, manifest, project_root=tmp_path)["accepted"] == 1
    with pytest.raises(ValueError, match="exemplar unavailable"):
        start(
            db,
            attempt_id="false",
            subject=SUBJECT,
            source_type="public",
            version="fixture",
            key="false",
        )


def test_stored_witness_must_cover_every_legal_defense():
    from chess_coach.objective_promotion_witness import choose

    board = chess.Board("7k/8/P1K5/8/8/8/8/8 w - - 0 1")
    move = board.parse_uci("a6a7")
    proof = judge(board, move, FORCE, lambda: 0.0, 0.0, 5.0, {})["proof"]
    board.push(move)
    assert choose(board, proof)["reply"] in {reply.uci() for reply in board.legal_moves}
    with pytest.raises(ValueError, match="defenses changed"):
        choose(board, proof | {"witnesses": proof["witnesses"][:-1]})


@pytest.mark.parametrize(
    "collision",
    [
        "mate-one-own-v1",
        "mate-two-own-v1",
        "avoid-immediate-mate-own-v1",
        "capture-target-own-v1",
        "capture-gain-own-v1",
        "pawn-result-own-v1",
    ],
)
def test_public_promotion_version_collision_never_routes_to_owned_proof(tmp_path, collision):
    from tests.test_public_training import file_set

    source, manifest, metadata = file_set(
        tmp_path,
        rows=[
            ("explicit", "8/P7/8/8/8/8/8/k6K w - - 0 1", NOW, ["a7a8q"]),
        ],
    )
    manifest.write_text(json.dumps(metadata | {"version": collision}))
    db = Database(tmp_path / "collision.sqlite")
    db.initialize()
    import_collection(db, source, source, manifest, project_root=tmp_path)
    start(
        db,
        attempt_id="public",
        subject=SUBJECT,
        source_type="public",
        version=collision,
        key="explicit",
    )
    submit(db, "public", SUBJECT, event_id="move", move="a7a8q")
    assert process(db, SUBJECT)["outcomes"] == {"correct": 1}
    state = show(db, "public", SUBJECT)
    assert state["status"] == "objective_verified" and "pawn_continuation_unavailable" not in state
    result = json.loads(
        db.connection.execute("SELECT result_json FROM objective_results").fetchone()[0]
    )
    assert result["verifier"] == "promotion-verifier-v1"
