"""Synthetic bounded capture objectives preserve source and event history."""

import json

import chess
import pytest

from chess_coach.evidence_review import review_evidence
from chess_coach.material_detector import process_decision
from chess_coach.objective_capture_contract import GAIN_VERSION, TARGET_VERSION
from chess_coach.objective_capture_judge import judge
from chess_coach.objective_status import inspect
from chess_coach.objective_worker import process
from chess_coach.unified_session_events import show, submit
from chess_coach.unified_sessions import start
from tests.test_material_pipeline import LEARNER, make_game


def evaluate(board, move, objective="capture_named_target", target="d4"):
    return judge(
        board,
        board.parse_uci(move),
        objective,
        chess.parse_square(target),
        3,
        lambda: 0.0,
        0.0,
        5.0,
        {},
    )


@pytest.mark.parametrize("version", [TARGET_VERSION, GAIN_VERSION])
def test_owned_session_immutable_retry_and_stale_review(tmp_path, monkeypatch, version):
    db = make_game(tmp_path / "capture.sqlite", monkeypatch)
    evidence = process_decision(db, 1, LEARNER)["evidence_ids"][0]
    state = start(
        db,
        attempt_id="one",
        subject=LEARNER,
        source_type="own-game",
        version=version,
        key=str(evidence),
    )
    assert state["gain_threshold"] == 3
    if version == TARGET_VERSION:
        assert state["objective_target"] == "d4"
    else:
        assert "objective_target" not in state
    before = db.connection.execute("SELECT COUNT(*) FROM mastery_events").fetchone()[0]
    response = submit(db, "one", LEARNER, event_id="move", move="e1f1")
    assert response["feedback"] == "needs_verification"
    frozen = db.connection.execute("SELECT response_json FROM unified_session_events").fetchone()[0]
    assert process(db, LEARNER)["processed"] == 1
    outcome = inspect(db, LEARNER, "one", "move")
    assert outcome["status"] == ("incorrect" if version == TARGET_VERSION else "unresolved")
    assert submit(db, "one", LEARNER, event_id="move", move="e1f1") == response
    assert (
        db.connection.execute("SELECT response_json FROM unified_session_events").fetchone()[0]
        == frozen
    )
    assert db.connection.execute("SELECT COUNT(*) FROM mastery_events").fetchone()[0] == before
    assert show(db, "one", LEARNER)["verification"]["status"] == outcome["status"]
    review_evidence(db, evidence, decision="reject", actor="fixture_reviewer")
    with pytest.raises(ValueError):
        show(db, "one", LEARNER)
    assert json.loads(frozen)["feedback"] == "needs_verification"


def test_browser_and_cli_resume_show_the_bound_objective(tmp_path, monkeypatch, capsys):
    from argparse import Namespace

    from chess_coach.cli_unified_practice import handle_show, handle_start
    from chess_coach.web import create_app
    from tests.test_unified_sessions import token

    path = tmp_path / "browser.sqlite"
    db = make_game(path, monkeypatch)
    evidence = process_decision(db, 1, LEARNER)["evidence_ids"][0]
    handle_start(
        db,
        Namespace(
            attempt="cli",
            subject=LEARNER,
            source="own-game",
            version=TARGET_VERSION,
            key=str(evidence),
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
    assert library.status_code == 200 and b"Capture the named target" in library.data
    post = client.post(
        "/unified/start",
        base_url="https://coach.invalid",
        headers=headers | {"Origin": "https://coach.invalid"},
        data={
            "csrf": token(library, "csrf"),
            "source_type": "own-game",
            "version": TARGET_VERSION,
            "key": str(evidence),
        },
    )
    assert post.status_code == 303
    page = client.get(post.headers["Location"], base_url="https://coach.invalid", headers=headers)
    assert b"Capture the piece on d4" in page.data and b"at least 3 material points" in page.data
    move = client.post(
        "/unified/move",
        base_url="https://coach.invalid",
        headers=headers | {"Origin": "https://coach.invalid"},
        data={
            "csrf": token(page, "csrf"),
            "attempt": token(page, "attempt"),
            "event": token(page, "event"),
            "move": "e1f1",
        },
    )
    assert move.status_code == 303
    pending = client.get(
        move.headers["Location"], base_url="https://coach.invalid", headers=headers
    )
    assert b"Verification is queued" in pending.data
    from chess_coach.db import Database

    db = Database(path)
    assert process(db, LEARNER)["outcomes"] == {"incorrect": 1}
    db.close()
    resumed = client.get(
        move.headers["Location"], base_url="https://coach.invalid", headers=headers
    )
    assert b"This move did not capture the named target" in resumed.data


@pytest.mark.parametrize("mode", ["correct", "assisted", "incorrect", "unresolved", "tampered"])
def test_unfamiliar_capture_assessment_browser_and_currentness(tmp_path, monkeypatch, mode):
    import re

    from chess_coach.capture_plan_history import latest
    from chess_coach.db import Database
    from chess_coach.unified_session_events import show
    from chess_coach.web import create_app
    from tests.test_unified_sessions import token

    path = tmp_path / "transfer.sqlite"
    db = make_game(path, monkeypatch)
    evidence = process_decision(db, 1, LEARNER)["evidence_ids"][0]
    db.connection.execute(
        "INSERT INTO puzzle_corpora(version,source,checksum,state) VALUES('capture','fixture','checksum','staging')"
    )
    corpus = db.connection.execute("SELECT id FROM puzzle_corpora").fetchone()[0]
    for file in ("a", "b", "c", "f", "g"):
        board = chess.Board("4k3/8/8/8/3q4/8/8/3RK3 b - - 0 1")
        board.set_piece_at(chess.parse_square(file + "7"), chess.Piece(chess.PAWN, chess.BLACK))
        key = "private-fixture-" + file
        db.connection.execute(
            """INSERT INTO puzzles(puzzle_id,corpus_id,fen,source,solution,rating,rating_deviation,themes_json,objective)
            VALUES(?,?,?,'https://example.invalid',?,1200,80,'["hangingPiece"]','unknown')""",
            (key, corpus, board.fen(), file + "7" + file + "6 d1d4"),
        )
        db.connection.execute(
            "INSERT INTO puzzle_themes VALUES(?,?,'hangingPiece',1200)", (corpus, key)
        )
    no_reset = chess.Board("4k3/8/8/8/3q4/8/8/3RK3 b - - 0 1")
    db.connection.execute(
        """INSERT INTO puzzles(puzzle_id,corpus_id,fen,source,solution,rating,rating_deviation,themes_json,objective)
        VALUES('private-fixture-no-reset',?,?,'https://example.invalid','e8f8 d1d4',1200,80,'["hangingPiece"]','unknown')""",
        (corpus, no_reset.fen()),
    )
    db.connection.execute(
        "INSERT INTO puzzle_themes VALUES(?,?,'hangingPiece',1200)",
        (corpus, "private-fixture-no-reset"),
    )
    db.connection.execute("UPDATE puzzle_corpora SET state='ready' WHERE id=?", (corpus,))
    db.connection.commit()
    db.close()
    app = create_app(
        db_path=path,
        subject=LEARNER,
        actor="operator",
        corpus="capture",
        login="fixture",
        origin="https://coach.invalid",
    )
    client = app.test_client()
    headers = {"Tailscale-User-Login": "fixture"}
    page = client.get(
        "/decisions/1/related-captures", base_url="https://coach.invalid", headers=headers
    )
    assert page.status_code == 200 and b"Check my capture choice" in page.data
    assert b"private-fixture" not in page.data and b"b7b6 d1d4" not in page.data
    forms = re.findall(r"<form\b.*?</form>", page.get_data(as_text=True), re.DOTALL)
    assessment_form = next(form for form in forms if 'name="assessment"' in form)
    match = re.search(r'name="reference" value="([^"]+)"', assessment_form)
    assert match
    reference = match.group(1)
    if mode == "correct":
        import base64
        import json
        import sqlite3
        from html import unescape
        from urllib.parse import parse_qs, urlparse

        from chess_coach import related_capture_assessment
        from chess_coach.fact_fingerprint import canonical, digest

        link = re.search(r'href="([^"]*cursor=[^"]+)"', page.get_data(as_text=True))
        assert link
        cursor = parse_qs(urlparse(unescape(link.group(1))).query)["cursor"][0]
        _, tag = json.loads(base64.urlsafe_b64decode(cursor))
        from chess_coach.related_capture import preview

        check_db = Database(path)
        first = preview(check_db, LEARNER, 1, "capture", secret=app.secret_key)
        later = preview(check_db, LEARNER, 1, "capture", cursor, secret=app.secret_key)
        no_reset.push_uci("e8f8")
        no_reset_item = next(
            item for item in first["items"] + later["items"] if item["fen"] == no_reset.fen()
        )
        assert not no_reset_item.get("assessment_available")
        check_db.close()
        assert all(
            reference != digest(canonical([tag, "corpus", "capture", "private-fixture-" + file]))
            for file in ("a", "b", "c", "f", "g")
        )
        original = related_capture_assessment.certificate

        def racing(*args):
            result = original(*args)
            with sqlite3.connect(path) as other:
                other.execute("UPDATE games SET event=event WHERE id=1")
            return result

        with monkeypatch.context() as patch:
            patch.setattr(related_capture_assessment, "certificate", racing)
            changed = client.post(
                "/decisions/1/related-captures/start",
                base_url="https://coach.invalid",
                headers=headers | {"Origin": "https://coach.invalid"},
                data={"csrf": token(page, "csrf"), "reference": reference, "assessment": "1"},
            )
            assert changed.status_code == 400
        with sqlite3.connect(path) as check:
            assert check.execute("SELECT count(*) FROM unified_sessions").fetchone()[0] == 0
        with monkeypatch.context() as patch:
            patch.setattr(
                related_capture_assessment,
                "certificate",
                lambda *args: (_ for _ in ()).throw(ValueError("unresolved")),
            )
            unavailable = client.post(
                "/decisions/1/related-captures/start",
                base_url="https://coach.invalid",
                headers=headers | {"Origin": "https://coach.invalid"},
                data={"csrf": token(page, "csrf"), "reference": reference, "assessment": "1"},
            )
            assert unavailable.status_code == 400
            assert b"capture could not be verified" in unavailable.data
    post = client.post(
        "/decisions/1/related-captures/start",
        base_url="https://coach.invalid",
        headers=headers | {"Origin": "https://coach.invalid"},
        data={
            "csrf": token(page, "csrf"),
            "reference": reference,
            "assessment": "1",
        },
    )
    assert post.status_code == 303
    shown = client.get(post.headers["Location"], base_url="https://coach.invalid", headers=headers)
    assert b"Capture the piece on d4" in shown.data and b"It is your turn as white" in shown.data
    check_db = Database(path)
    assert latest(check_db, LEARNER, 1, "capture")["status"] == "incomplete"
    check_db.close()
    attempt = token(shown, "attempt")
    if mode == "assisted":
        for endpoint in ("/unified/hint", "/unified/reveal"):
            clue = client.post(
                endpoint,
                base_url="https://coach.invalid",
                headers=headers | {"Origin": "https://coach.invalid"},
                data={
                    "csrf": token(shown, "csrf"),
                    "attempt": attempt,
                    "event": token(shown, "event"),
                },
            )
            assert clue.status_code == (200 if endpoint.endswith("reveal") else 303)
            shown = client.get(
                post.headers["Location"], base_url="https://coach.invalid", headers=headers
            )
    move = client.post(
        "/unified/move",
        base_url="https://coach.invalid",
        headers=headers | {"Origin": "https://coach.invalid"},
        data={
            "csrf": token(shown, "csrf"),
            "attempt": attempt,
            "event": token(shown, "event"),
            "move": "e1f1" if mode == "incorrect" else "d1d4",
        },
    )
    assert move.status_code == 303
    pending = client.get(
        move.headers["Location"], base_url="https://coach.invalid", headers=headers
    )
    assert b"Verification is queued" in pending.data
    pending_page = client.get("/plan/captures", base_url="https://coach.invalid", headers=headers)
    assert b"awaiting verification" in pending_page.data
    db = Database(path)
    pending_history = latest(db, LEARNER, 1, "capture")
    assert pending_history["status"] == "pending"
    assert pending_history["hints"] == (2 if mode == "assisted" else 0)
    if mode == "unresolved":
        monkeypatch.setattr(
            "chess_coach.objective_verify_dispatch.verify_capture",
            lambda *args: {**args[7], "status": "unresolved", "reason": "proof_limit"},
        )
    if mode == "tampered":
        from chess_coach import objective_verify_dispatch

        original_verify = objective_verify_dispatch.verify_capture

        def mismatched_move(*args):
            result = original_verify(*args)
            return {**result, "move": "a1a2"}

        monkeypatch.setattr(objective_verify_dispatch, "verify_capture", mismatched_move)
    expected = "correct" if mode in {"correct", "assisted", "tampered"} else mode
    assert process(db, LEARNER)["outcomes"] == {expected: 1}
    result = show(db, attempt, LEARNER)["verification"]
    assert result["status"] == expected
    assert result["assistance"] == ("revealed" if mode == "assisted" else "unassisted")
    history = latest(db, LEARNER, 1, "capture")
    assert history["status"] == ("unavailable" if mode == "tampered" else expected)
    assert latest(db, LEARNER, 1, "different")["status"] == "none"
    assert history["hints"] == (2 if mode == "assisted" else 0)
    finished = client.get(
        move.headers["Location"], base_url="https://coach.invalid", headers=headers
    )
    text = {
        "correct": b"bounded capture objective is verified",
        "assisted": b"A continuation was revealed",
        "incorrect": b"This move did not capture the named target",
        "unresolved": b"The move remains ungraded",
        "tampered": b"bounded capture objective is verified",
    }
    assert text[mode] in finished.data
    adaptive = client.get("/plan/captures", base_url="https://coach.invalid", headers=headers)
    adaptive_text = {
        "correct": b"first move was verified without a hint or reveal",
        "assisted": b"first move was verified with assistance",
        "incorrect": b"checked first move did not capture the named target",
        "unresolved": b"first move remains ungraded",
        "tampered": b"latest assessment could not be checked",
    }
    assert adaptive_text[mode] in adaptive.data
    assert (b"Explore another unfamiliar capture example" in adaptive.data) == (
        mode in {"correct", "incorrect"}
    )
    assert b"Comparisons need more comparable first attempts" in adaptive.data
    assert db.connection.execute("SELECT COUNT(*) FROM training_attempts").fetchone()[0] == 0
    if mode == "correct":
        again = client.get(
            "/decisions/1/related-captures", base_url="https://coach.invalid", headers=headers
        )
        rehearsal = client.post(
            "/decisions/1/related-captures/start",
            base_url="https://coach.invalid",
            headers=headers | {"Origin": "https://coach.invalid"},
            data={"csrf": token(again, "csrf"), "reference": token(again, "reference")},
        )
        assert rehearsal.status_code == 303
        rehearsal_page = client.get(
            rehearsal.headers["Location"], base_url="https://coach.invalid", headers=headers
        )
        assert b"Find a continuation" in rehearsal_page.data
        assert latest(db, LEARNER, 1, "capture")["status"] == "correct"
    review_evidence(db, evidence, decision="reject", actor="reviewer")
    with pytest.raises(ValueError):
        show(db, attempt, LEARNER)
    assert latest(db, LEARNER, 1, "capture")["status"] == "stale"
    if mode == "correct":
        for index in range(101):
            db.connection.execute(
                """INSERT INTO unified_sessions
                (attempt_id,subject,source_type,source_version,source_key,snapshot_hash,prompt_fen,
                 learner_color,objective,lines_json,provenance_json,current_fen,candidates_json,
                 next_index,status,started_at)
                VALUES(?,?,'public','fixture','fixture','fixture',?,'white','legal_line',
                       '[]','{}',?,'[]',0,'active','9999-01-01T00:00:00+00:00')""",
                (f"unrelated-{index:03}", LEARNER, chess.STARTING_FEN, chess.STARTING_FEN),
            )
        db.connection.commit()
        limited = latest(db, LEARNER, 1, "capture")
        assert limited["status"] == "none" and limited["limited"]
    db.close()


def test_capture_plan_uses_independent_current_sources_and_is_lazy(tmp_path, monkeypatch):
    import sys

    import chess.pgn

    from chess_coach.capture_plan import report
    from chess_coach.ingest import ingest_pgn
    from chess_coach.pipeline_config import PipelineConfig
    from chess_coach.pipeline_inputs import engine_identity, game_input
    from chess_coach.pipeline_work import run_analysis
    from chess_coach.web import create_app

    path = tmp_path / "capture-plan.sqlite"
    db = make_game(path, monkeypatch)
    first = process_decision(db, 1, LEARNER)["evidence_ids"][0]
    initial = report(db, LEARNER, "legacy")
    assert initial["source"]["games"] == 1 and initial["history"]["status"] == "none"
    before = db.connection.total_changes
    operations = []
    db.connection.set_trace_callback(lambda sql: operations.append(sql.split(None, 1)[0].upper()))
    assert report(db, LEARNER, "legacy")["source"]["games"] == 1
    db.connection.set_trace_callback(None)
    assert not {"BEGIN", "SAVEPOINT"} & set(operations)
    assert db.connection.total_changes == before

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
    with monkeypatch.context() as patch:

        def forbidden(*args, **kwargs):
            raise AssertionError("capture analysis ran on the daily plan")

        patch.setattr("chess_coach.capture_plan.report", forbidden)
        plan = client.get("/plan", base_url="https://coach.invalid", headers=headers)
    assert plan.status_code == 200 and b"/plan/captures" in plan.data
    single = client.get("/plan/captures", base_url="https://coach.invalid", headers=headers)
    assert single.status_code == 200 and b"single game does not establish recurrence" in single.data
    assert b"No certified assessment in the active corpus for this source" in single.data

    board = chess.Board("4k3/7p/8/8/3q4/8/8/3RK3 w - - 0 1")
    game = chess.pgn.Game()
    game.setup(board)
    game.headers["White"] = LEARNER
    game.headers["Black"] = "fixture_opponent"
    game.headers["Result"] = "*"
    game.headers["UTCDate"] = "2026.01.01"
    game.headers["UTCTime"] = "12:01:00"
    node = game.add_variation(board.parse_uci("e1f1"))
    board.push_uci("e1f1")
    node.add_variation(board.parse_uci("e8f8"))
    config = PipelineConfig(learner=LEARNER, engine_path=sys.executable, nodes=100)
    new_evidence = []
    for _ in range(2):
        ingest_pgn(db, str(game))
        game_id = db.connection.execute("SELECT MAX(id) FROM games").fetchone()[0]
        position = db.connection.execute(
            "SELECT id FROM positions WHERE game_id=? ORDER BY ply LIMIT 1", (game_id,)
        ).fetchone()[0]
        assert (
            run_analysis(
                db, game_id, game_input(db, game_id), config, engine_identity(sys.executable)
            )["status"]
            == "complete"
        )
        new_evidence.append(process_decision(db, position, LEARNER)["evidence_ids"][0])

    from chess_coach.recurrence_cursor import MAX_ID
    from chess_coach.recurrence_sources import evidence as recurrence_evidence

    bounded, truncated = recurrence_evidence(
        db, LEARNER, "hanging_piece", "execute", MAX_ID, failure_only=True, limit=1
    )
    assert len(bounded) == 1 and truncated
    repeated = report(db, LEARNER, "legacy")
    assert repeated["source"]["games"] == 2
    assert repeated["source"]["observations"] == 2
    page = client.get("/plan/captures", base_url="https://coach.invalid", headers=headers)
    assert b"across 2 independent games" in page.data
    assert b"detector was not rerun" in page.data
    linked = client.get(
        f"/decisions/{repeated['source']['position_id']}/related-captures",
        base_url="https://coach.invalid",
        headers=headers,
    )
    assert linked.status_code == 200
    for evidence_id in new_evidence:
        review_evidence(db, evidence_id, decision="reject", actor="reviewer")
    assert report(db, LEARNER, "legacy")["source"]["games"] == 1
    review_evidence(db, first, decision="reject", actor="reviewer")
    assert report(db, LEARNER, "legacy")["source"] is None
    db.close()
