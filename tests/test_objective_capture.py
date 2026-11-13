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
    library = client.get(
        "/library?family=capture", base_url="https://coach.invalid", headers=headers
    )
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
    if mode == "correct":
        for file in ("d", "e"):
            harder_board = chess.Board("4k3/8/8/8/3q4/8/8/3RK3 b - - 0 1")
            harder_board.set_piece_at(
                chess.parse_square(file + "7"), chess.Piece(chess.PAWN, chess.BLACK)
            )
            db.connection.execute(
                """INSERT INTO puzzles(puzzle_id,corpus_id,fen,source,solution,rating,rating_deviation,themes_json,objective)
                VALUES(?,?,?,'https://example.invalid',?,1400,80,'["hangingPiece"]','unknown')""",
                (
                    "harder-fixture-" + file,
                    corpus,
                    harder_board.fen(),
                    file + "7" + file + "6 d1d4",
                ),
            )
            db.connection.execute(
                "INSERT INTO puzzle_themes VALUES(?,?,'hangingPiece',1400)",
                (corpus, "harder-fixture-" + file),
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
    if mode == "correct":
        from chess_coach.recurrence_snapshot import read_snapshot
        from chess_coach.tactical_course_related import unfamiliar

        with read_snapshot(db):
            course_chapter = unfamiliar(
                db,
                LEARNER,
                "capture",
                {"kind": "capture", "position_id": 1, "evidence_id": evidence},
            )
        assert course_chapter["mode"] == "conceal"
        assert "Pattern-cued unfamiliar worked example" in course_chapter["pgn"]
        assert "Worked example, ungraded" in course_chapter["pgn"]
        with pytest.raises(ValueError, match="differs"):
            unfamiliar(
                db,
                LEARNER,
                "capture",
                {"kind": "capture", "position_id": 1, "evidence_id": evidence + 1},
            )
        import time

        from chess_coach.tactical_course_budget import Budget, PreviewUnavailable
        from chess_coach.tactical_course_resolve import related

        choice = {"kind": "capture", "position_id": 1, "evidence_id": evidence}
        matched, reason = related(db, LEARNER, "capture", choice, Budget(db))
        assert reason is None and matched["mode"] == "conceal"

        def slow_match(*_args, **_kwargs):
            time.sleep(0.05)

        with monkeypatch.context() as patch:
            patch.setattr("chess_coach.tactical_course_budget.SLICE_SECONDS", 0.01)
            patch.setattr("chess_coach.tactical_course_resolve.unfamiliar", slow_match)
            item, reason = related(
                db,
                LEARNER,
                "capture",
                {"kind": "capture", "position_id": 1, "evidence_id": evidence},
                Budget(db),
            )
        assert item is None and reason == "related matching deferred: time budget"

        def slow_sql(connection_db, *_args, **_kwargs):
            connection_db.connection.execute(
                "WITH RECURSIVE n(x) AS (VALUES(0) UNION ALL SELECT x+1 FROM n WHERE x<100000000) SELECT sum(x) FROM n"
            ).fetchone()

        with monkeypatch.context() as patch:
            patch.setattr("chess_coach.tactical_course_budget.SLICE_SECONDS", 0.01)
            patch.setattr("chess_coach.tactical_course_resolve.unfamiliar", slow_sql)
            item, reason = related(db, LEARNER, "capture", choice, Budget(db))
        assert item is None and reason == "related matching deferred: time budget"
        assert not db.connection.in_transaction

        def concurrent_slow(*_args):
            import sqlite3

            with sqlite3.connect(path) as other:
                other.execute("UPDATE games SET event=event WHERE id=1")
            time.sleep(0.5)

        with monkeypatch.context() as patch:
            patch.setattr("chess_coach.tactical_course_budget.SLICE_SECONDS", 0.2)
            patch.setattr("chess_coach.tactical_course_resolve.unfamiliar", concurrent_slow)
            with pytest.raises(PreviewUnavailable, match="changed"):
                related(db, LEARNER, "capture", choice, Budget(db))
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
    sections = re.findall(r"<section>.*?</section>", page.get_data(as_text=True), re.DOTALL)
    assessment_form = next(
        section
        for section in sections
        if "content rating 1200" in section and 'name="assessment"' in section
    )
    match = re.search(r'name="reference" value="([^"]+)"', assessment_form)
    assert match
    reference = match.group(1)
    if mode == "correct":
        import base64
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
    admitted = check_db.connection.execute(
        "SELECT provenance_json FROM unified_sessions"
    ).fetchone()[0]
    context = json.loads(admitted)["related_capture"]["assessment"]["context"]
    assert context["content_rating"] == 1200 and context["content_deviation"] == 80
    assert context["corpus_checksum"] == "checksum" and context["mechanism"]["target"]
    check_db.close()
    attempt = token(shown, "attempt")

    def daily_attempt():
        with monkeypatch.context() as patch:
            patch.setattr(
                "chess_coach.capture_plan.choose",
                lambda *_, **_kwargs: {
                    "source": {
                        "position_id": 1,
                        "evidence_id": evidence,
                        "games": 2,
                        "version": "material-own-v2",
                        "key": f"1:material_capture:{evidence}",
                    },
                    "limited": False,
                    "scanned": 2,
                },
            )
            patch.setattr("chess_coach.plan_capture_action.resolve_source", lambda *_a, **_k: {})
            patch.setattr("chess_coach.web_protection_plan.report", lambda *_: None)
            patch.setattr("chess_coach.web_protection_plan.fork_recommendation", lambda *_: None)
            return client.get("/plan", base_url="https://coach.invalid", headers=headers)

    def focus_page(protection_games=2, *, unavailable=False, capture_unavailable=False):
        from chess_coach.tactical_course_budget import PreviewUnavailable

        protection = {
            "source": {
                "games": protection_games,
                "evidence_id": evidence,
                "review_status": "provisional",
                "color": "white",
                "version": "fixture",
                "key": "fixture",
            },
            "groups": 1,
            "scanned": 2,
            "checked": 1,
            "unavailable": 0,
            "limited": True,
            "partial": True,
        }

        def checked_protection(*_args):
            if unavailable:
                raise PreviewUnavailable()
            return protection

        with monkeypatch.context() as patch:
            patch.setattr(
                "chess_coach.capture_plan.choose",
                lambda *_, **_kwargs: {
                    "source": {
                        "position_id": 1,
                        "evidence_id": evidence,
                        "games": 2,
                        "reviewed": False,
                        "version": "material-own-v2",
                        "key": f"1:material_capture:{evidence}",
                    },
                    "limited": True,
                    "scanned": 2,
                },
            )
            patch.setattr("chess_coach.web_protection_plan.report", checked_protection)

            def checked_capture(*_args, **_kwargs):
                if capture_unavailable:
                    raise ValueError("replay unavailable")
                return {}

            patch.setattr("chess_coach.plan_capture_action.resolve_source", checked_capture)
            return client.get("/plan/next-focus", base_url="https://coach.invalid", headers=headers)

    if mode == "correct":
        assert b"Continue your capture assessment" in daily_attempt().data
        initial_focus = focus_page()
        assert b"Next focus: find captures" in initial_focus.data
        assert b"Some candidates were not checked" in initial_focus.data
        assert b"Additional markers were not inspected" in initial_focus.data
        assert b"Protection has more supporting games" in focus_page(3).data
        unavailable_capture = focus_page(capture_unavailable=True)
        assert b"Next focus: protect a piece" in unavailable_capture.data
        assert b"capture check was unavailable" in unavailable_capture.data
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
    if mode == "correct":
        assert b"Check your capture assessment status" in daily_attempt().data
    pending_page = client.get("/plan/captures", base_url="https://coach.invalid", headers=headers)
    assert b"awaiting verification" in pending_page.data
    history_page = client.get(
        "/plan/captures/history", base_url="https://coach.invalid", headers=headers
    )
    assert b"1 pending" in history_page.data and b"puzzle rating 1200" in history_page.data
    with monkeypatch.context() as patch:
        patch.setattr(
            "chess_coach.capture_compare_samples.verify",
            lambda *_args: (_ for _ in ()).throw(
                AssertionError("sparse comparison performed proof work")
            ),
        )
        sparse_page = client.get(
            "/plan/captures/comparison", base_url="https://coach.invalid", headers=headers
        )
    assert (
        sparse_page.status_code == 200
        and b"largest group has 1 recorded matches" in sparse_page.data
    )
    assert b"not verified comparison results" in sparse_page.data
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
    focus = focus_page()
    if mode == "correct":
        assert b"Next focus: protect a piece" in focus.data
        assert b"verified correct without assistance" in focus.data
        assert b"Replay the prepared defensive line" in focus.data
        fallback = focus_page(unavailable=True)
        assert b"Next focus: find captures" in fallback.data
        assert b"matching comparison context" in fallback.data
    else:
        assert b"Next focus: find captures" in focus.data
        if mode == "incorrect":
            assert b"missed the target" in focus.data
            assert b"fresh verified assessment" in focus.data
    if mode == "correct":
        import chess_coach.capture_finder_match as match_policy
        import chess_coach.capture_finder_proof as finder_proof

        original_context = match_policy.capture
        checked = []

        def first_mismatch(*args):
            context = original_context(*args)
            checked.append(True)
            if len(checked) == 1:
                context["content_rating"] += 200
            return context

        with monkeypatch.context() as patch:
            patch.setattr(match_policy, "capture", first_mismatch)
            matched_page = client.get(
                f"/plan/captures/find-verified?attempt={attempt}&position=1",
                base_url="https://coach.invalid",
                headers=headers,
            )
        assert len(checked) >= 2
        assert matched_page.status_code == 200
        assert b"passed the bounded capture proof" in matched_page.data
        assert b"same comparison context" in matched_page.data
        from chess_coach.capture_compare_signature import signature
        from chess_coach.fact_fingerprint import canonical
        from chess_coach.related_capture_start import _admit

        form = next(
            form
            for form in re.findall(
                r"<form\b.*?</form>", matched_page.get_data(as_text=True), re.DOTALL
            )
            if 'name="assessment"' in form
        )
        reference_match = re.search(r'name="reference" value="([^"]+)"', form)
        assert reference_match
        matched_reference = reference_match.group(1)
        admitted_again = _admit(db, LEARNER, 1, "capture", matched_reference, app.secret_key, True)
        next_context = json.loads(canonical(admitted_again[3]["assessment"]["context"]))
        assert signature(next_context, "capture") == signature(context, "capture")

        second_post = client.post(
            "/decisions/1/related-captures/start",
            base_url="https://coach.invalid",
            headers=headers | {"Origin": "https://coach.invalid"},
            data={
                "csrf": token(matched_page, "csrf"),
                "reference": matched_reference,
                "assessment": "1",
            },
        )
        assert second_post.status_code == 303
        second_shown = client.get(
            second_post.headers["Location"], base_url="https://coach.invalid", headers=headers
        )
        second_attempt = token(second_shown, "attempt")
        second_move = client.post(
            "/unified/move",
            base_url="https://coach.invalid",
            headers=headers | {"Origin": "https://coach.invalid"},
            data={
                "csrf": token(second_shown, "csrf"),
                "attempt": second_attempt,
                "event": token(second_shown, "event"),
                "move": "d1d4",
            },
        )
        assert second_move.status_code == 303
        assert process(db, LEARNER)["outcomes"] == {"correct": 1}

        def no_match(*args):
            context = original_context(*args)
            context["content_rating"] += 200
            return context

        with monkeypatch.context() as patch:
            patch.setattr(match_policy, "capture", no_match)
            patch.setattr(
                finder_proof,
                "certificate",
                lambda *_: (_ for _ in ()).throw(AssertionError("proved a mismatched candidate")),
            )
            empty = client.get(
                f"/plan/captures/find-verified?attempt={attempt}&position=1",
                base_url="https://coach.invalid",
                headers=headers,
            )
        assert b"with the same comparison context" in empty.data
        assert b"Find a verified unfamiliar capture of the same pattern" in empty.data
        assert b"/plan/captures/find-verified?position=1" in empty.data
    else:
        blocked = client.get(
            f"/plan/captures/find-verified?attempt={attempt}&position=1",
            base_url="https://coach.invalid",
            headers=headers,
        )
        assert b"with the same comparison context" in blocked.data
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
    daily = daily_attempt()
    assert daily.status_code == 200
    assert (
        b"Find a verified unfamiliar capture with matching comparison context" in daily.data
    ) == (mode == "correct")
    assert (b"Find another verified unfamiliar capture of this pattern" in daily.data) == (
        mode == "correct"
    )
    assert (b"find a fresh verified assessment of this pattern" in daily.data) == (
        mode == "incorrect"
    )
    if mode in {"assisted", "unresolved"}:
        assert b"does not advance this recommendation" in daily.data
    if mode == "tampered":
        assert b"latest assessment could not be checked" in daily.data
    adaptive = client.get("/plan/captures", base_url="https://coach.invalid", headers=headers)
    adaptive_text = {
        "correct": b"first move was verified without a hint or reveal",
        "assisted": b"first move was verified with assistance",
        "incorrect": b"checked first move did not capture the named target",
        "unresolved": b"first move remains ungraded",
        "tampered": b"latest assessment could not be checked",
    }
    assert adaptive_text[mode] in adaptive.data
    assert b"View first-encounter capture history" in adaptive.data
    assert b"Capture choices in your games" in adaptive.data
    count_text = {
        "correct": b"2 correct without assistance",
        "assisted": b"1 assisted",
        "incorrect": b"1 incorrect without assistance",
        "unresolved": b"1 ungraded",
        "tampered": b"1 unavailable or stale",
    }
    history_page = client.get(
        "/plan/captures/history", base_url="https://coach.invalid", headers=headers
    )
    assert count_text[mode] in history_page.data
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
        # A second unfamiliar prompt shares source checking, while old snapshots
        # without admission context remain descriptive and unranked.
        next_page = client.get(
            "/decisions/1/related-captures", base_url="https://coach.invalid", headers=headers
        )
        sections = re.findall(
            r"<section>.*?</section>", next_page.get_data(as_text=True), re.DOTALL
        )
        next_form = next(
            section
            for section in sections
            if "content rating 1200" in section and 'name="assessment"' in section
        )
        next_match = re.search(r"name=\"reference\" value=\"([^\"]+)\"", next_form)
        assert next_match
        next_ref = next_match.group(1)
        with monkeypatch.context() as patch:
            patch.setattr(
                "chess_coach.related_capture_assessment_context.capture",
                lambda *args: (_ for _ in ()).throw(ValueError()),
            )
            second = client.post(
                "/decisions/1/related-captures/start",
                base_url="https://coach.invalid",
                headers=headers | {"Origin": "https://coach.invalid"},
                data={"csrf": token(next_page, "csrf"), "reference": next_ref, "assessment": "1"},
            )
        assert second.status_code == 303
        import chess_coach.related_capture_source as source_module
        from chess_coach.capture_history_first import report as first_history

        original_source = source_module.source_for_position
        checks = []

        def counted_source(*args, **kwargs):
            checks.append(True)
            return original_source(*args, **kwargs)

        with monkeypatch.context() as patch:
            patch.setattr(source_module, "source_for_position", counted_source)
            assessed = first_history(db, LEARNER, "capture")
        assert assessed["counts"]["unassisted_correct"] == 2
        assert assessed["counts"]["incomplete"] == 1 and len(checks) == 1
        assert {entry["rating"] for entry in assessed["items"]} == {None, 1200}
        from chess_coach.capture_history_first import HistoryDeadline

        checks = []

        def expiring_check():
            checks.append(True)
            if len(checks) == 2:
                raise HistoryDeadline()

        with pytest.raises(HistoryDeadline):
            original_source(db, LEARNER, 1, check=expiring_check)
        assert len(checks) == 2
        with monkeypatch.context() as patch:
            patch.setattr("chess_coach.capture_history_first.SECONDS", 0)
            partial = client.get(
                "/plan/captures/history", base_url="https://coach.invalid", headers=headers
            )
        assert b"Capture assessments in inspected sessions" in partial.data
        assert b"earlier encounters may be missing" in partial.data
        # A second owned source contributes another independently admitted prompt.
        import sys

        from chess import pgn

        from chess_coach.ingest import ingest_pgn
        from chess_coach.pipeline_config import PipelineConfig
        from chess_coach.pipeline_inputs import engine_identity, game_input
        from chess_coach.pipeline_work import run_analysis
        from chess_coach.related_capture import preview as capture_preview
        from chess_coach.related_capture_start import start_related

        new_board = chess.Board("4k3/7p/8/8/3q4/8/8/3RK3 w - - 0 1")
        new_game = pgn.Game()
        new_game.setup(new_board)
        new_game.headers["White"] = LEARNER
        new_game.headers["Black"] = "fixture_opponent"
        new_game.headers["UTCDate"] = "2026.01.02"
        new_game.headers["UTCTime"] = "12:00:00"
        node = new_game.add_variation(new_board.parse_uci("e1f1"))
        new_board.push_uci("e1f1")
        node.add_variation(new_board.parse_uci("e8f8"))
        ingest_pgn(db, str(new_game))
        game_id = db.connection.execute("SELECT MAX(id) FROM games").fetchone()[0]
        position = db.connection.execute(
            "SELECT id FROM positions WHERE game_id=? ORDER BY ply LIMIT 1", (game_id,)
        ).fetchone()[0]
        config = PipelineConfig(learner=LEARNER, engine_path=sys.executable, nodes=100)
        run_analysis(db, game_id, game_input(db, game_id), config, engine_identity(sys.executable))
        assert process_decision(db, position, LEARNER)["evidence_ids"]
        second_source = capture_preview(db, LEARNER, position, "capture", secret=app.secret_key)
        reference = next(
            value["reference"]
            for value in second_source["items"]
            if value.get("assessment_available") and value.get("rating") == 1200
        )
        start_related(
            db,
            attempt_id="another-source",
            subject=LEARNER,
            position=position,
            corpus_version="capture",
            reference=reference,
            assessment=True,
            secret=app.secret_key,
        )
        across_sources = first_history(db, LEARNER, "capture")
        assert across_sources["counts"]["unassisted_correct"] == 2
        assert across_sources["counts"]["incomplete"] == 2
        # Two synthetic nonoverlapping, matched cohorts exercise the comparison
        # gates without creating or publishing any learner attempts.
        import chess_coach.capture_compare_report as comparison_report
        import chess_coach.capture_compare_select as comparison_select
        import chess_coach.capture_compare_verify as comparison_verify
        from chess_coach.capture_compare_scope import scope as comparison_scope

        original_row = dict(
            db.connection.execute(
                "SELECT * FROM unified_sessions WHERE attempt_id=?", (attempt,)
            ).fetchone()
        )
        # Screen side before same-game deduplication for the harder search.
        from chess_coach.capture_difficulty_binding import options as difficulty_options
        from chess_coach.capture_difficulty_history import _ordered
        from chess_coach.related_capture_rank import rank
        from chess_coach.related_capture_source import source_for_position

        setup = chess.Board("4k3/4p3/8/8/3q4/8/8/3RK3 b - - 0 1")
        shared = {
            "type": "corpus",
            "version": "capture",
            "game": "same-game",
            "opening": None,
            "rating": 1400,
            "rating_deviation": 80,
        }
        pool = [
            dict(shared, key="a", fen=setup.mirror().fen(), solution="e2e3 d8d5"),
            dict(shared, key="z", fen=setup.fen(), solution="e7e6 d1d4"),
        ]
        owned = source_for_position(db, LEARNER, 1)
        assert rank(owned, pool, set(), 1400)[0]["key"] == "a"
        score = difficulty_options({"side": "white", "band": 1400})["score"]
        assert rank(owned, pool, set(), 1400, score=score)[0]["key"] == "z"
        dated = [{"started_at": f"2026-01-01T00:00:0{x}+00:00"} for x in (3, 2, 1)]
        _ordered(dated, dated[2]["started_at"])
        with pytest.raises(ValueError):
            _ordered(dated, dated[1]["started_at"])
        with pytest.raises(ValueError):
            _ordered([dated[0], dated[1], dated[1]], dated[2]["started_at"])

        # Use the two real verified results while isolating this control from
        # unrelated later incomplete fixture attempts.
        import chess_coach.capture_difficulty_history as difficulty_history
        import chess_coach.capture_finder as difficulty_finder
        import chess_coach.capture_finder_search as difficulty_search
        from chess_coach.capture_difficulty import eligible

        pair = [
            dict(
                db.connection.execute(
                    "SELECT * FROM unified_sessions WHERE attempt_id=?", (value,)
                ).fetchone()
            )
            for value in (second_attempt, attempt)
        ]
        with monkeypatch.context() as patch:
            patch.setattr(difficulty_history, "_rows", lambda *_: pair)
            assert eligible(db, LEARNER, "capture", 1, second_attempt)["band"] == 1400
            with pytest.raises(ValueError):
                eligible(db, LEARNER, "capture", 1, attempt)
            patch.setattr(
                difficulty_finder,
                "_groups",
                lambda *_: ({("capture", "v"): [{"position_id": 1}]}, False, 1),
            )
            patch.setattr(
                difficulty_search, "witnesses", lambda *_args, **_kwargs: iter([{"position_id": 1}])
            )
            harder = client.get(
                f"/plan/captures/find-verified?position=1&attempt={second_attempt}&harder=1",
                base_url="https://coach.invalid",
                headers=headers,
            )
            assert b"1400" in harder.data and b"Check my capture choice" in harder.data
            started = client.post(
                "/decisions/1/related-captures/start",
                base_url="https://coach.invalid",
                headers=headers | {"Origin": "https://coach.invalid"},
                data={
                    "csrf": token(harder, "csrf"),
                    "reference": token(harder, "reference"),
                    "assessment": "1",
                    "harder_attempt": second_attempt,
                },
            )
            assert started.status_code == 303
            binding = json.loads(
                db.connection.execute(
                    "SELECT provenance_json FROM unified_sessions ORDER BY rowid DESC LIMIT 1"
                ).fetchone()[0]
            )["related_capture"]
            assert binding["progression"]["prior_attempts"] == [attempt, second_attempt]
        synthetic = []
        for index in range(20):
            position_board = chess.Board.empty()
            position_board.set_piece_at(index, chess.Piece(chess.PAWN, chess.WHITE))
            row = dict(
                original_row,
                attempt_id=f"cohort-{index:02}",
                prompt_fen=position_board.fen(),
                started_at=f"2026-01-01T00:00:{index:02}+00:00",
            )
            synthetic.append(row)
        assert comparison_scope(synthetic[0], "capture") is not None
        bad_context = json.loads(synthetic[0]["provenance_json"])
        bad_context["related_capture"]["assessment"]["context"]["same_geometry"] ^= True
        assert (
            comparison_scope(dict(synthetic[0], provenance_json=json.dumps(bad_context)), "capture")
            is None
        )

        def synthetic_item(_db, row, _corpus, _cache, _check):
            number = int(row["attempt_id"].split("-")[-1])
            return {
                "attempt_id": row["attempt_id"],
                "started_at": row["started_at"],
                "status": "correct" if number < 15 else "incorrect",
                "hints": 0,
                "reveals": 0,
            }

        with monkeypatch.context() as patch:
            patch.setattr(comparison_select, "rows", lambda *_args: (synthetic[:19], False))
            patch.setattr(
                "chess_coach.capture_compare_samples.verify",
                lambda *_args: (_ for _ in ()).throw(AssertionError("sparse proof")),
            )
            assert comparison_report.report(db, LEARNER, "capture")["status"] == "sparse"
            duplicate = [
                *synthetic[:19],
                dict(synthetic[19], prompt_fen=synthetic[0]["prompt_fen"]),
            ]
            patch.setattr(comparison_select, "rows", lambda *_args: (duplicate, False))
            assert comparison_report.report(db, LEARNER, "capture")["status"] == "sparse"
            different = json.loads(synthetic[19]["provenance_json"])
            different["related_capture"]["assessment"]["context"]["content_rating"] = 1600
            split = [*synthetic[:19], dict(synthetic[19], provenance_json=json.dumps(different))]
            patch.setattr(comparison_select, "rows", lambda *_args: (split, False))
            assert comparison_report.report(db, LEARNER, "capture")["status"] == "sparse"
        with monkeypatch.context() as patch:
            patch.setattr(comparison_select, "rows", lambda *_args: (synthetic, False))
            patch.setattr(comparison_verify, "item", synthetic_item)
            matched = comparison_report.report(db, LEARNER, "capture")
            assert matched["status"] == "comparable" and matched["checked"] == 20
            assert matched["earlier"]["unassisted"]["verified"] == 10
            assert matched["later"]["unassisted"]["verified"] == 5
            assert matched["later"]["unassisted"]["incorrect"] == 5
            assert matched["earlier"]["end"] < matched["later"]["start"]
            compared_page = client.get(
                "/plan/captures/comparison", base_url="https://coach.invalid", headers=headers
            )
            assert (
                compared_page.status_code == 200
                and b"Both nonoverlapping samples" in compared_page.data
            )
            assert b"10 correct" in compared_page.data and b"5 incorrect" in compared_page.data
            tied = list(synthetic)
            tied[10] = dict(tied[10], started_at=tied[9]["started_at"])
            patch.setattr(comparison_select, "rows", lambda *_args: (tied, False))
            assert comparison_report.report(db, LEARNER, "capture")["status"] == "unavailable"
            patch.setattr(comparison_select, "rows", lambda *_args: (synthetic, False))
            patch.setattr(
                comparison_verify, "item", lambda *args: {**synthetic_item(*args), "hints": 1}
            )
            assert comparison_report.report(db, LEARNER, "capture")["status"] == "unavailable"
            patch.setattr(
                comparison_verify,
                "item",
                lambda *args: {"status": "stale", "started_at": args[1]["started_at"]},
            )
            assert comparison_report.report(db, LEARNER, "capture")["status"] == "unavailable"
            patch.setattr(comparison_verify, "SECONDS", 0)
            assert comparison_report.report(db, LEARNER, "capture")["checked"] == 0
        # The omitted middle record must not tie either selected cutoff.
        board21 = chess.Board.empty()
        board21.set_piece_at(20, chess.Piece(chess.PAWN, chess.WHITE))
        extra = dict(
            synthetic[19],
            attempt_id="cohort-20",
            prompt_fen=board21.fen(),
            started_at="2026-01-01T00:00:20+00:00",
        )
        for tied_index in (9, 11):
            twenty_one = [*synthetic, extra]
            twenty_one[10] = dict(twenty_one[10], started_at=twenty_one[tied_index]["started_at"])
            with monkeypatch.context() as patch:
                patch.setattr(
                    comparison_select, "rows", lambda *_args, rows=twenty_one: (rows, False)
                )
                patch.setattr(
                    "chess_coach.capture_compare_samples.verify",
                    lambda *_args: (_ for _ in ()).throw(AssertionError("tied boundary proof")),
                )
                ambiguous = comparison_report.report(db, LEARNER, "capture")
            assert (
                ambiguous["status"] == "unavailable" and ambiguous["reason"] == "ambiguous_boundary"
            )
            assert ambiguous["checked"] == 0
        with monkeypatch.context() as patch:
            patch.setattr(comparison_select, "rows", lambda *_args: (synthetic, True))
            patch.setattr(
                "chess_coach.capture_compare_samples.verify",
                lambda *_args: (_ for _ in ()).throw(AssertionError("incomplete proof")),
            )
            assert comparison_report.report(db, LEARNER, "capture")["status"] == "incomplete"
        # The opt-in finder skips a source whose candidate proofs do not pass,
        # then displays a proved candidate from a second current owned source.
        import chess_coach.capture_finder as finder
        import chess_coach.capture_finder_proof as finder_proof
        import chess_coach.capture_finder_search as finder_search

        original_select = finder_search._selection
        original_certificate = finder_proof.certificate
        original_familiarity = finder.familiarity
        positions, familiarity_calls = [], []

        def selected_source(*args, **kwargs):
            positions.append(args[2])
            return original_select(*args, **kwargs)

        def proof_after_first(*args):
            if len(positions) == 1:
                raise ValueError("synthetic unresolved proof")
            return original_certificate(*args)

        def counted_familiarity(*args):
            familiarity_calls.append(True)
            return original_familiarity(*args)

        filtered = []
        with monkeypatch.context() as patch:
            patch.setattr(
                finder,
                "_groups",
                lambda *_: ({("capture", "v"): [{"position_id": 1}, {"position_id": 2}]}, False, 2),
            )
            patch.setattr(finder, "familiarity", lambda *_: {})
            patch.setattr(finder, "search", lambda *args: filtered.append(args[5]))
            scoped = client.get(
                "/plan/captures/find-verified?position=2",
                base_url="https://coach.invalid",
                headers=headers,
            )
            invalid = client.get(
                "/plan/captures/find-verified?position=9223372036854775808",
                base_url="https://coach.invalid",
                headers=headers,
            )
        assert scoped.status_code == invalid.status_code == 200
        assert filtered == [{("capture", "v"): [{"position_id": 2}]}]

        before_count = db.connection.execute("SELECT COUNT(*) FROM unified_sessions").fetchone()[0]
        with monkeypatch.context() as patch:
            patch.setattr(finder_search, "_selection", selected_source)
            patch.setattr(finder_proof, "certificate", proof_after_first)
            patch.setattr(finder, "familiarity", counted_familiarity)
            found = client.get(
                "/plan/captures/find-verified", base_url="https://coach.invalid", headers=headers
            )
        assert len(positions) >= 2, (len(positions), len(familiarity_calls))
        assert found.status_code == 200 and b"passed the bounded capture proof" in found.data
        assert len(positions) >= 2 and positions[0] != positions[1] and len(familiarity_calls) == 1
        assert (
            db.connection.execute("SELECT COUNT(*) FROM unified_sessions").fetchone()[0]
            == before_count
        )
        assert b"private-fixture" not in found.data
        proved_forms = re.findall(r"<form\b.*?</form>", found.get_data(as_text=True), re.DOTALL)
        proved_form = next(form for form in proved_forms if 'name="assessment"' in form)
        form_action = re.search(r"action=\"([^\"]+)\"", proved_form)
        proved_reference = re.search(r"name=\"reference\" value=\"([^\"]+)\"", proved_form)
        assert form_action and proved_reference
        accepted = client.post(
            form_action.group(1),
            base_url="https://coach.invalid",
            headers=headers | {"Origin": "https://coach.invalid"},
            data={
                "csrf": token(found, "csrf"),
                "reference": proved_reference.group(1),
                "assessment": "1",
            },
        )
        assert accepted.status_code == 303
        stale = client.post(
            form_action.group(1),
            base_url="https://coach.invalid",
            headers=headers | {"Origin": "https://coach.invalid"},
            data={
                "csrf": token(found, "csrf"),
                "reference": proved_reference.group(1),
                "assessment": "1",
            },
        )
        assert stale.status_code == 400
        assert (
            db.connection.execute("SELECT COUNT(*) FROM unified_sessions").fetchone()[0]
            == before_count + 1
        )
        with monkeypatch.context() as patch:
            patch.setattr(finder, "SECONDS", 0)
            patch.setattr(finder, "_groups", lambda *_: (_ for _ in ()).throw(AssertionError()))
            empty = client.get(
                "/plan/captures/find-verified", base_url="https://coach.invalid", headers=headers
            )
        assert empty.status_code == 200 and b"bounded search" in empty.data
        # Unsupported sources are skipped and scope uses the original subject.
        seen_subjects = []

        def unsupported_then_empty(_db, subject, position, _corpus, **_kwargs):
            seen_subjects.append(subject)
            if position == 1:
                raise ValueError("unsupported mechanism")
            return None

        with monkeypatch.context() as patch:
            patch.setattr(
                finder_search,
                "witnesses",
                lambda *_args, **_kwargs: iter([{"position_id": 1}, {"position_id": 2}]),
            )
            patch.setattr(finder_search, "_selection", unsupported_then_empty)
            assert (
                finder_search.search(
                    db,
                    "normalized",
                    "MiXeD",
                    "capture",
                    app.secret_key,
                    {},
                    None,
                    1,
                    lambda _: False,
                )
                is None
            )
        assert seen_subjects == ["MiXeD", "MiXeD"]
        # A proof that completes after the cooperative budget is never shown.
        clock = iter((False, False, True))
        with monkeypatch.context() as patch:
            patch.setattr(finder_proof, "setup", lambda *_args: None)
            patch.setattr(finder_proof, "certificate", lambda *_args: None)
            candidate, used = finder_proof.prove(
                db,
                (None, None, None, [{"type": "corpus", "version": "fixture", "key": "fixture"}]),
                1,
                1,
                lambda _: next(clock),
            )
        assert candidate is None and used == 1
        # Setup may consume the remaining budget; do not start a proof then.
        started = []
        clock = iter((False, True))
        with monkeypatch.context() as patch:
            patch.setattr(finder_proof, "setup", lambda *_args: None)
            patch.setattr(finder_proof, "certificate", lambda *_args: started.append(True))
            candidate, used = finder_proof.prove(
                db,
                (None, None, None, [{"type": "corpus", "version": "fixture", "key": "fixture"}]),
                1,
                4,
                lambda _: next(clock),
            )
        assert candidate is None and used == 0 and not started
        # Cheap preflight skips do not consume the proof budget or hide a later candidate.
        candidates = [
            {"type": "corpus", "version": "fixture", "key": str(index)} for index in range(16)
        ]

        def last_only(_db, _version, key):
            if key != "15":
                raise ValueError("unsupported setup")

        with monkeypatch.context() as patch:
            patch.setattr(finder_proof, "setup", last_only)
            patch.setattr(finder_proof, "certificate", lambda *_args: None)
            candidate, used = finder_proof.prove(
                db, (None, None, None, candidates), 1, 12, lambda _: False
            )
        assert candidate["key"] == "15" and used == 1
        proofs = []

        def unresolved(*args):
            proofs.append(True)
            raise ValueError("unresolved")

        with monkeypatch.context() as patch:
            patch.setattr(finder_proof, "setup", lambda *_args: None)
            patch.setattr(finder_proof, "certificate", unresolved)
            candidate, used = finder_proof.prove(
                db, (None, None, None, candidates), 1, 12, lambda _: False
            )
        assert candidate is None and used == 12 and len(proofs) == 12
        proof_quotas = []
        fake_candidate = {"type": "corpus", "version": "fixture", "key": "fixture"}

        def per_source(_db, _selection, _deadline, remaining, _expired):
            proof_quotas.append(remaining)
            return (None, remaining) if len(proof_quotas) == 1 else (fake_candidate, 1)

        with monkeypatch.context() as patch:
            patch.setattr(
                finder_search,
                "witnesses",
                lambda *_args, **_kwargs: iter([{"position_id": 1}, {"position_id": 2}]),
            )
            patch.setattr(
                finder_search,
                "_selection",
                lambda *_args, **_kwargs: (None, None, None, [fake_candidate], None, None),
            )
            patch.setattr(finder_search, "prove", per_source)
            patch.setattr(finder_search, "present", lambda *_args, **_kwargs: {"items": [{}]})
            answer = finder_search.search(
                db, LEARNER, LEARNER, "capture", app.secret_key, {}, None, 1, lambda _: False
            )
        assert answer[0] == 2 and proof_quotas == [4, 4]
    review_evidence(db, evidence, decision="reject", actor="reviewer")
    with pytest.raises(ValueError):
        show(db, attempt, LEARNER)
    assert latest(db, LEARNER, 1, "capture")["status"] == "stale"
    from chess_coach.capture_history_first import report as first_report

    expected_stale = (
        4 + int(form_action.group(1).startswith("/decisions/1/")) if mode == "correct" else 1
    )
    assert first_report(db, LEARNER, "capture")["counts"]["stale"] == expected_stale
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
    from chess_coach.capture_plan_sources import _groups
    from chess_coach.tactical_course_budget import PreviewUnavailable

    checkpoints = []

    def deadline():
        checkpoints.append(True)
        if len(checkpoints) == 2:
            raise PreviewUnavailable("deadline")

    with pytest.raises(PreviewUnavailable):
        _groups(db, LEARNER, check=deadline)
    assert len(checkpoints) == 2
    initial = report(db, LEARNER, "legacy")
    assert initial["source"]["games"] == 1 and initial["history"]["status"] == "none"
    # A full history still shows the newest distinct first encounters.
    import chess_coach.capture_history_select as history_selection

    samples = []
    for index, square in enumerate(chess.SQUARES[:10]):
        board = chess.Board.empty()
        board.set_piece_at(square, chess.Piece(chess.PAWN, chess.WHITE))
        samples.append(
            {
                "attempt_id": str(index),
                "started_at": "2026-01-01T00:00:00+00:00",
                "prompt_fen": board.fen(),
            }
        )
    samples.append(dict(samples[0]))
    with monkeypatch.context() as patch:
        patch.setattr(history_selection, "rows", lambda *_: (samples, False))
        patch.setattr(history_selection, "is_source", lambda _: True)
        recent, limited = history_selection.select(db, LEARNER)
    assert limited and [row["attempt_id"] for row in recent] == [
        str(index) for index in range(2, 10)
    ]
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

        patch.setattr("chess_coach.capture_finder.find", forbidden)
        plan = client.get("/plan", base_url="https://coach.invalid", headers=headers)
    assert plan.status_code == 200 and b"/plan/captures" in plan.data
    assert b"<h3>Capture practice</h3>" not in plan.data
    with monkeypatch.context() as patch:
        patch.setattr("chess_coach.capture_plan.report", forbidden)
        patch.setattr(
            "chess_coach.web_views.daily_plan",
            lambda *_args, **_kwargs: {
                "items": [],
                "evidence": {"state": "fixture"},
                "corpus_status": "fixture",
                "diagnostic": None,
                "next_cursor": None,
            },
        )
        continuation = client.get(
            "/plan?cursor=next", base_url="https://coach.invalid", headers=headers
        )
    assert continuation.status_code == 200 and b"<h3>Capture practice</h3>" not in continuation.data
    assert b"Practice protecting a piece" not in continuation.data
    with monkeypatch.context() as patch:
        patch.setattr("chess_coach.capture_finder.find", forbidden)
        single = client.get("/plan/captures", base_url="https://coach.invalid", headers=headers)
    assert b"Find a verified unfamiliar capture" in single.data
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
    import chess_coach.capture_plan as capture_plan

    original_report = capture_plan.report
    calls = []

    def counted(*args, **kwargs):
        calls.append(True)
        return original_report(*args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr("chess_coach.capture_finder.find", forbidden)
        patch.setattr(capture_plan, "report", counted)
        daily = client.get("/plan", base_url="https://coach.invalid", headers=headers)
    assert calls == [True]
    assert b"<h3>Capture practice</h3>" in daily.data
    assert b"Replay the prepared capture" in daily.data
    assert f'name="key" value="{repeated["source"]["key"]}"'.encode() in daily.data
    assert b"Find a verified unfamiliar capture" in daily.data
    assert b"Compare matched capture assessments" in daily.data
    with monkeypatch.context() as patch:
        patch.setattr(
            "chess_coach.web_protection_plan.report",
            lambda *_args: (_ for _ in ()).throw(ValueError("unavailable")),
        )
        first_focus = client.get(
            "/plan/next-focus", base_url="https://coach.invalid", headers=headers
        )
    assert b"Next focus: find captures" in first_focus.data
    assert (
        f"/plan/captures/find-verified?position={repeated['source']['position_id']}".encode()
        in first_focus.data
    )
    assert b"protection check was unavailable" in first_focus.data
    assert b"Replay the prepared capture from this game" in first_focus.data
    assert b"separate from a verified unfamiliar assessment" in first_focus.data
    from tests.test_unified_sessions import token

    replay_data = {
        "csrf": token(first_focus, "csrf"),
        "source_type": token(first_focus, "source_type"),
        "version": token(first_focus, "version"),
        "key": token(first_focus, "key"),
    }
    assert replay_data["key"] == repeated["source"]["key"]
    assert replay_data["version"] == repeated["source"]["version"]
    replay = client.post(
        "/unified/start",
        base_url="https://coach.invalid",
        headers=headers | {"Origin": "https://coach.invalid"},
        data=replay_data,
    )
    assert replay.status_code == 303
    replay_page = client.get(
        replay.headers["Location"], base_url="https://coach.invalid", headers=headers
    )
    assert b"one supplied continuation" in replay_page.data
    replay_row = db.connection.execute(
        "SELECT source_key, objective, provenance_json FROM unified_sessions"
    ).fetchone()
    assert replay_row["source_key"] == repeated["source"]["key"]
    assert replay_row["objective"] == "material_capture"
    assert (
        json.loads(replay_row["provenance_json"])["evidence_id"]
        == repeated["source"]["evidence_id"]
    )
    with monkeypatch.context() as patch:
        patch.setattr(
            "chess_coach.web_views.daily_plan",
            lambda *_args, **_kwargs: {
                "items": [
                    {
                        "objective": "Fixture scheduled review",
                        "kind": "review",
                        "reason": "",
                        "due": None,
                        "corpus_version": "legacy",
                        "puzzle_id": "fixture",
                    },
                    {
                        "objective": "Fixture new puzzle",
                        "kind": "new",
                        "reason": "",
                        "due": None,
                        "corpus_version": "legacy",
                        "puzzle_id": "new-fixture",
                    },
                ],
                "scan": {"due_incomplete": False},
                "evidence": {"state": "fixture"},
                "corpus_status": "fixture",
                "diagnostic": None,
                "next_cursor": "fixture-cursor",
                "continuation_reason": "corpus_scan_incomplete",
            },
        )
        scheduled = client.get("/plan", base_url="https://coach.invalid", headers=headers)
    assert scheduled.data.index(b"Fixture scheduled review") < scheduled.data.index(
        b"<h3>Capture practice</h3>"
    )
    assert scheduled.data.index(b"Fixture scheduled review") < scheduled.data.index(
        b"Check your next non-mate practice focus"
    )
    assert scheduled.data.index(b"<h3>Capture practice</h3>") < scheduled.data.index(
        b"Fixture new puzzle"
    )
    assert scheduled.data.count(b"<h3>Capture practice</h3>") == 1
    assert b"cursor=fixture-cursor" in scheduled.data
    assert b"Check your next non-mate practice focus" not in continuation.data

    # Incomplete or full due coverage never triggers the added source check.
    from chess_coach.plan_page import _room_after_due

    due = {
        "objective": "Due",
        "kind": "due",
        "reason": "",
        "due": None,
        "corpus_version": "legacy",
        "puzzle_id": "fixture",
    }
    assert not _room_after_due({"scan": {"due_incomplete": True}, "items": [due]})
    assert not _room_after_due({"scan": {"due_incomplete": False}, "items": [due] * 10})
    with monkeypatch.context() as patch:
        patch.setattr("chess_coach.plan_page.current_focus", forbidden)
        for result in (
            {"scan": {"due_incomplete": True}, "items": [due]},
            {"scan": {"due_incomplete": False}, "items": [due] * 10},
        ):
            page_data = {
                **result,
                "evidence": {"state": "fixture"},
                "corpus_status": "fixture",
                "diagnostic": None,
                "next_cursor": None,
            }
            patch.setattr(
                "chess_coach.web_views.daily_plan", lambda *_, page_data=page_data, **_k: page_data
            )
            page = client.get("/plan", base_url="https://coach.invalid", headers=headers)
            assert page.status_code == 200 and b"<h3>Capture practice</h3>" not in page.data
    from chess_coach.tactical_course_budget import PreviewUnavailable

    with monkeypatch.context() as patch:
        patch.setattr(
            "chess_coach.capture_plan.report",
            lambda *_, **_kwargs: (_ for _ in ()).throw(PreviewUnavailable()),
        )
        timed_out = client.get("/plan", base_url="https://coach.invalid", headers=headers)
    assert timed_out.status_code == 200 and b"<h3>Capture practice</h3>" not in timed_out.data
    with monkeypatch.context() as patch:
        patch.setattr(
            "chess_coach.capture_plan.report", lambda *_: (_ for _ in ()).throw(ValueError())
        )
        fallback = client.get("/plan", base_url="https://coach.invalid", headers=headers)
    assert fallback.status_code == 200 and b"<h3>Capture practice</h3>" not in fallback.data
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
    stale_replay = client.post(
        "/unified/start",
        base_url="https://coach.invalid",
        headers=headers | {"Origin": "https://coach.invalid"},
        data=replay_data,
    )
    assert stale_replay.status_code == 400
    assert db.connection.execute("SELECT count(*) FROM unified_sessions").fetchone()[0] == 1
    db.close()
