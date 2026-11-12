"""Owned fork objectives verify equivalent moves without inventing game results."""

import json
import re

import pytest

from chess_coach.objective_fork_contract import VERSION
from chess_coach.objective_fork_list import candidates
from chess_coach.objective_status import inspect
from chess_coach.objective_worker import process
from chess_coach.unified_session_events import show, submit
from chess_coach.web import create_app
from tests.objective_fork_support import SUBJECT, begin, owned_fork
from tests.test_unified_sessions import token


@pytest.mark.parametrize("played,outcome", [("f6g5", "failure"), ("b5c7", "success")])
def test_unlisted_owned_fork_is_proved_for_success_and_miss(tmp_path, monkeypatch, played, outcome):
    path = tmp_path / "fork.sqlite"
    db, evidence = owned_fork(path, monkeypatch, played)
    for _ in range(10):
        db.connection.execute(
            """INSERT INTO evidence_mappings
            (position_id, skill, operation, outcome, confidence, subject, mapping_run_id)
            SELECT position_id, skill, operation, 'ambiguous', confidence, subject, mapping_run_id
            FROM evidence_mappings WHERE id=?""",
            (evidence,),
        )
    db.connection.commit()
    assert candidates(db, SUBJECT)["candidates"] == [{"key": str(evidence)}]

    app = create_app(
        db_path=path,
        subject=SUBJECT,
        actor="fixture",
        corpus="fixture",
        login="fixture-login",
        origin="https://coach.invalid",
    )
    client = app.test_client()
    headers = {"Tailscale-User-Login": "fixture-login"}
    library = client.get("/library?family=fork", base_url="https://coach.invalid", headers=headers)
    section = library.get_data(as_text=True).split("<h2>Own-game fork execution</h2>", 1)[1]
    section = section.split("<h2>", 1)[0]
    assert f'name="key" value="{evidence}"' in section
    assert f'name="version" value="{VERSION}"' in section
    posted = client.post(
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
    assert posted.status_code == 303
    page = client.get(posted.location, base_url="https://coach.invalid", headers=headers)
    assert page.status_code == 200
    assert not re.search(rb"(?<![A-Za-z0-9_-])b5c7(?![A-Za-z0-9_-])", page.data)
    before = {
        table: db.connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        for table in (
            "evidence_mappings",
            "evidence_review_events",
            "mastery_events",
            "mastery_states",
            "training_items",
            "training_attempts",
            "training_completions",
        )
    }
    state = begin(db, evidence)
    assert state["source_outcome"] == outcome
    assert state["fork_attacker"] == "b5" and state["fork_anchor"] == "e8"
    assert "b5c7" not in json.dumps(state) and "b5d6" not in json.dumps(state)
    original = submit(db, "fork", SUBJECT, event_id="answer", move="b5d6")
    assert original["status"] == "needs_verification"
    assert process(db, SUBJECT)["outcomes"] == {"correct": 1}
    assert inspect(db, SUBJECT, "fork", "answer")["status"] == "correct"
    result = json.loads(
        db.connection.execute("SELECT result_json FROM objective_results").fetchone()[0]
    )
    assert result["status"] == "correct" and result["proven_gain_floor"] == 3
    assert result["proof"]["targets"] == ["f5", "e8"]
    assert show(db, "fork", SUBJECT)["verification"]["status"] == "correct"
    assert submit(db, "fork", SUBJECT, event_id="answer", move="b5d6") == original
    begin(db, evidence, attempt="owned-unsupported")
    submit(db, "owned-unsupported", SUBJECT, event_id="answer", move="f6g5")
    assert process(db, SUBJECT)["outcomes"] == {"unresolved": 1}
    assert inspect(db, SUBJECT, "owned-unsupported", "answer")["status"] == "unresolved"
    assert {
        table: db.connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        for table in before
    } == before


@pytest.mark.parametrize("mode", ["correct", "assisted", "unresolved", "miss_piece", "miss_target"])
def test_unfamiliar_fork_browser_and_worker(tmp_path, monkeypatch, mode):

    from chess_coach.db import Database
    from chess_coach.evidence_review import review_evidence
    from chess_coach.related_fork_assessment import certificate

    path = tmp_path / "unfamiliar.sqlite"
    db, evidence = owned_fork(path, monkeypatch, "f6g5")
    db.connection.execute(
        "INSERT INTO puzzle_corpora(version,source,checksum,state) VALUES('fork-fixture','fixture','checksum','staging')"
    )
    corpus = db.connection.execute("SELECT id FROM puzzle_corpora").fetchone()[0]
    db.connection.execute(
        """INSERT INTO puzzles(puzzle_id,corpus_id,fen,source,solution,rating,rating_deviation,themes_json,objective)
        VALUES('synthetic-key',?,?,'https://example.invalid',?,1200,80,'["fork"]','unknown')""",
        (corpus, "b3k3/4B2p/5K2/1N3b2/8/8/8/8 b - - 0 1", "h7h6 b5c7 e8d7 c7a8"),
    )
    db.connection.execute(
        "INSERT INTO puzzle_themes VALUES(?,?,'fork',1200)", (corpus, "synthetic-key")
    )
    if mode == "correct":
        # Two additional proof-capable forks share the theme and roles; only one
        # is in the recorded difficulty cohort. The first prompt is now familiar.
        for key, fen, solution, rating in (
            ("match", "3k3b/p2B4/2K5/2b3N1/8/8/8/8 b - - 0 1", "a7a6 g5f7 d8e7 f7h8", 1250),
            (
                "different-band",
                "8/8/8/8/1n3B2/5k2/4b2P/B3K3 w - - 0 1",
                "h2h3 b4c2 e1d2 c2a1",
                1600,
            ),
        ):
            db.connection.execute(
                """INSERT INTO puzzles(puzzle_id,corpus_id,fen,source,solution,rating,
                    rating_deviation,themes_json,objective) VALUES(?,?,?,'https://example.invalid',?,?,80,'["fork"]','unknown')""",
                (key, corpus, fen, solution, rating),
            )
            db.connection.execute(
                "INSERT INTO puzzle_themes VALUES(?,?,'fork',?)", (corpus, key, rating)
            )
    db.connection.execute("UPDATE puzzle_corpora SET state='ready' WHERE id=?", (corpus,))
    db.connection.commit()
    assert certificate(db, "fork-fixture", "synthetic-key")["proof"]["move"] == "b5c7"
    if mode == "correct":
        from chess_coach import fork_followup_finder

        checked = []

        def later_source(_db, _subject, evidence_id, *_args, **_kwargs):
            checked.append(evidence_id)
            return {"items": []} if evidence_id == 4 else None

        with monkeypatch.context() as patch:
            patch.setattr(
                fork_followup_finder,
                "evidence",
                lambda *_a, **_k: ([{"id": n} for n in range(1, 5)], False),
            )
            patch.setattr(fork_followup_finder, "find", later_source)
            assert fork_followup_finder.first(db, SUBJECT, "fork-fixture", b"secret")[0] == 4
        assert checked == [1, 2, 3, 4]
    db.close()
    app = create_app(
        db_path=path,
        subject=SUBJECT,
        actor="fixture",
        corpus="fork-fixture",
        login="fixture-login",
        origin="https://coach.invalid",
    )
    client = app.test_client()
    headers = {"Tailscale-User-Login": "fixture-login"}
    base = "https://coach.invalid"
    assert client.get("/plan/forks/history", base_url=base).status_code == 403
    from chess_coach import related_fork_assessment_finder

    original_search = related_fork_assessment_finder.search
    if mode == "correct":

        def initial_search(db, ordered, started, seconds, **options):
            selected = [item for item in ordered if item["key"] == "synthetic-key"]
            return original_search(db, selected, started, seconds, **options)

        monkeypatch.setattr(related_fork_assessment_finder, "search", initial_search)
    with monkeypatch.context() as patch:
        patch.setattr(
            related_fork_assessment_finder,
            "selection",
            lambda *_args: pytest.fail("daily plan must not search the fork corpus"),
        )
        plan = client.get("/plan", base_url=base, headers=headers)
    assert b"First-encounter fork assessment history" in plan.data
    assert b"Find a comparable next fork assessment" in plan.data
    if mode == "correct":
        initial = client.get("/plan/forks/find-verified", base_url=base, headers=headers)
        assert initial.status_code == 200 and b"Start fork assessment" in initial.data
    page = client.get(
        f"/evidence/{evidence}/related-forks/find-verified", base_url=base, headers=headers
    )
    assert page.status_code == 200 and b"Start fork assessment" in page.data
    assert b"Fork assessment history" in page.data
    assert b"synthetic-key" not in page.data
    assert not re.search(rb"(?<![A-Za-z0-9_-])b5c7(?![A-Za-z0-9_-])", page.data)
    if mode == "correct":
        oversized = 2**63
        unavailable = client.get(
            f"/evidence/{oversized}/related-forks/find-verified", base_url=base, headers=headers
        )
        assert (
            unavailable.status_code == 200 and b"No certified unfamiliar fork" in unavailable.data
        )
        rejected = client.post(
            f"/evidence/{oversized}/related-forks/start",
            base_url=base,
            headers=headers | {"Origin": base},
            data={
                "csrf": token(page, "csrf"),
                "reference": token(page, "reference"),
                "assessment": "1",
            },
        )
        assert rejected.status_code == 400
        import sqlite3

        from chess_coach import related_fork_assessment_finder, related_fork_assessment_start

        with monkeypatch.context() as patch:
            patch.setattr(
                related_fork_assessment_finder,
                "selection",
                lambda *_args: ({"outcome": "success"},),
            )
            check_db = Database(path)
            assert (
                related_fork_assessment_finder.find(
                    check_db, SUBJECT, evidence, "fork-fixture", "secret"
                )
                is None
            )
            check_db.close()

        original = related_fork_assessment_start.certificate

        def changed(current_db, *args):
            assert not current_db.connection.in_transaction
            result = original(current_db, *args)
            with sqlite3.connect(path) as other:
                other.execute("UPDATE games SET event=event WHERE id=1")
            return result

        with monkeypatch.context() as patch:
            patch.setattr(related_fork_assessment_start, "certificate", changed)
            stale = client.post(
                f"/evidence/{evidence}/related-forks/start",
                base_url=base,
                headers=headers | {"Origin": base},
                data={
                    "csrf": token(page, "csrf"),
                    "reference": token(page, "reference"),
                    "assessment": "1",
                },
            )
            assert stale.status_code == 400
        page = client.get(
            f"/evidence/{evidence}/related-forks/find-verified", base_url=base, headers=headers
        )

    posted = client.post(
        f"/evidence/{evidence}/related-forks/start",
        base_url=base,
        headers=headers | {"Origin": base},
        data={
            "csrf": token(page, "csrf"),
            "reference": token(page, "reference"),
            "assessment": "1",
        },
    )
    assert posted.status_code == 303
    monkeypatch.setattr(related_fork_assessment_finder, "search", original_search)
    page = client.get(posted.location, base_url=base, headers=headers)
    assert page.status_code == 200
    assert not re.search(rb"(?<![A-Za-z0-9_-])b5c7(?![A-Za-z0-9_-])", page.data)
    attempt = token(page, "attempt")
    db = Database(path)

    def history():
        import chess.engine

        version = db.connection.execute("PRAGMA data_version").fetchone()[0]
        with monkeypatch.context() as patch:

            def no_engine(*args, **kwargs):
                raise AssertionError("history must not start an engine")

            patch.setattr(chess.engine.SimpleEngine, "popen_uci", no_engine)
            response = client.get("/plan/forks/history", base_url=base, headers=headers)
        assert response.status_code == 200
        assert db.connection.execute("PRAGMA data_version").fetchone()[0] == version
        assert b"synthetic-key" not in response.data
        assert not re.search(rb"(?<![A-Za-z0-9_-])b5c7(?![A-Za-z0-9_-])", response.data)
        return response.data

    assert b"1 in progress" in history()
    if mode == "assisted":
        from chess_coach.unified_session_events import reveal

        reveal(db, attempt, SUBJECT, event_id="reveal")
    move = {"miss_piece": "e7f8", "miss_target": "b5a3"}.get(mode, "b5c7")
    result = submit(db, attempt, SUBJECT, event_id="answer", move=move)
    assert result["status"] == "needs_verification"
    assert b"1 pending" in history()
    from chess_coach.fork_plan_history import report as fork_plan_history
    from chess_coach.opening_queue_budget import BrowserBudget

    assert fork_plan_history(db, SUBJECT, "fork-fixture", evidence, BrowserBudget(db)) == {
        "status": "unknown"
    }
    expected = (
        "unresolved"
        if mode == "unresolved"
        else "incorrect"
        if mode.startswith("miss_")
        else "correct"
    )
    with monkeypatch.context() as patch:
        if mode == "unresolved":
            from chess_coach import objective_fork_judge

            patch.setattr(objective_fork_judge, "fork_proof", lambda *_args: None)
        assert process(db, SUBJECT)["outcomes"] == {expected: 1}
    assert inspect(db, SUBJECT, attempt, "answer")["status"] == expected
    state = show(db, attempt, SUBJECT)
    assert state["verification"]["status"] == expected
    output = json.loads(
        db.connection.execute("SELECT result_json FROM objective_results").fetchone()[0]
    )
    assert not output["learning_eligible"]
    assert output["assistance"] == ("revealed" if mode == "assisted" else "unassisted")

    # The advisory card consumes the same source-bound result without a finder,
    # engine, session creation or learning write.
    from chess_coach import fork_plan_action, fork_plan_history

    action = {"kind": "fork", "version": VERSION, "key": str(evidence), "evidence_id": evidence}
    preview = {"groups": [{"miss_games": 2}]}

    def no_work(*_args, **_kwargs):
        pytest.fail("next-focus must not search or run an engine")

    def focus():
        with monkeypatch.context() as patch:
            patch.setattr(fork_plan_action, "preview", lambda *_args: (preview, [action]))
            patch.setattr("chess_coach.web_protection_plan.admissible", lambda *_args: None)
            patch.setattr("chess_coach.web_protection_plan.report", lambda *_args: None)
            patch.setattr(related_fork_assessment_finder, "selection", no_work)
            patch.setattr("chess.engine.SimpleEngine.popen_uci", no_work)
            return client.get("/plan/next-focus", base_url=base, headers=headers)

    counts = {
        table: db.connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        for table in ("unified_sessions", "evidence_mappings", "mastery_states", "training_items")
    }
    focus_page = focus()
    assert b"Next focus: finding forks" in focus_page.data
    assert b"Rehearse this fork" in focus_page.data
    if mode == "correct":
        assert b"Find a comparable follow-up fork assessment" in focus_page.data
        assert ("/plan/forks/next?attempt=" + attempt).encode() in focus_page.data
    else:
        assert b"Find a comparable follow-up fork assessment" not in focus_page.data
        assert f"/evidence/{evidence}/related-forks/find-verified".encode() in focus_page.data
        assert (b"verified miss" in focus_page.data) == mode.startswith("miss_")
    assert {
        table: db.connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        for table in counts
    } == counts
    if mode == "correct":
        with monkeypatch.context() as patch:
            patch.setattr(
                fork_plan_history, "first", lambda *_args: (_ for _ in ()).throw(ValueError())
            )
            assert b"Find a comparable follow-up" not in focus().data
        action["evidence_id"] = evidence + 100
        assert b"Find a comparable follow-up" not in focus().data
        action["evidence_id"] = evidence
    page_data = history()
    label = {
        "correct": b"1 verified correct",
        "assisted": b"1 verified correct",
        "unresolved": b"1 unresolved",
        "miss_piece": b"1 verified misses",
        "miss_target": b"1 verified misses",
    }[mode]
    assert label in page_data
    if mode.startswith("miss_"):
        reason = "named_attacker_not_moved" if mode == "miss_piece" else "named_target_not_attacked"
        assert output["reason"] == reason and output["miss_rule"] == "certified-fork-miss-v1"
        page = client.get(posted.location, base_url=base, headers=headers)
        feedback = (
            b"The named piece was not moved"
            if mode == "miss_piece"
            else b"does not attack the named target"
        )
        assert feedback in page.data
        from chess_coach import fork_history_result
        from chess_coach.objective_current import current
        from chess_coach.objective_history_dispatch import replay

        request = db.connection.execute(
            "SELECT * FROM objective_requests WHERE attempt_id=?", (attempt,)
        ).fetchone()
        session, events = current(db, request)
        board, first_move = replay(db, session, events, request)
        real_valid = fork_history_result.valid
        assert real_valid(output, request, events, board, first_move, session)
        assert not real_valid(
            {**output, "miss_rule": "changed"}, request, events, board, first_move, session
        )
        assert not real_valid(
            {**output, "event_prefix_hash": "changed"}, request, events, board, first_move, session
        )
        assert not real_valid(
            {**output, "assistance": "revealed"}, request, events, board, first_move, session
        )
        assert not real_valid(
            {**output, "move": "b5c7"}, request, events, board, first_move, session
        )

        def forged_reason(value, *args):
            wrong = (
                "named_target_not_attacked" if mode == "miss_piece" else "named_attacker_not_moved"
            )
            return real_valid({**value, "reason": wrong}, *args)

        with monkeypatch.context() as patch:
            patch.setattr(fork_history_result, "valid", forged_reason)
            assert inspect(db, SUBJECT, attempt, "answer")["status"] == "unresolved"
            assert show(db, attempt, SUBJECT)["verification"]["status"] == "unresolved"
            assert b"1 unavailable or stale" in history()
        assert inspect(db, SUBJECT, attempt, "answer")["status"] == "incorrect"
    assert (b"1 assisted" if mode == "assisted" else b"0 assisted") in page_data
    assert attempt.encode() in page_data
    assert b"Comparisons are unavailable" in page_data
    assert b"<title>Fork assessment history - Chess coach</title>" in page_data
    if mode != "correct":
        unmatched = client.get(
            "/plan/forks/next?attempt=" + attempt, base_url=base, headers=headers
        )
        assert b"No comparable certified unfamiliar fork" in unmatched.data
    if mode == "correct":
        assessment_page = client.get(posted.location, base_url=base, headers=headers)
        assert b"Find a comparable next fork assessment" in assessment_page.data
        from chess_coach import fork_followup_search

        with monkeypatch.context() as patch:
            patch.setattr(fork_followup_search, "matches", lambda *_args: False)
            empty = client.get(
                "/plan/forks/next?attempt=" + attempt, base_url=base, headers=headers
            )
        assert b"No comparable certified unfamiliar fork" in empty.data
        assert b"Ordinary fork practice" in empty.data

        original_row = dict(
            db.connection.execute(
                "SELECT * FROM unified_sessions WHERE attempt_id=?", (attempt,)
            ).fetchone()
        )
        columns = list(original_row)
        unrelated = {
            **original_row,
            "prompt_fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
            "objective": "legal_line",
        }
        with monkeypatch.context() as patch:
            newer = {**unrelated, "started_at": "2099-01-01T00:00:00+00:00"}
            patch.setattr(fork_plan_history, "_end", lambda *_args: [*[newer] * 100, original_row])
            assert b"Find a comparable follow-up" not in focus().data
            tied = {**newer, "started_at": original_row["started_at"]}
            patch.setattr(
                fork_plan_history, "_end", lambda *_args: [*[newer] * 99, original_row, tied]
            )
            assert b"Find a comparable follow-up" not in focus().data
        from chess_coach import related_fork_assessment_search
        from chess_coach.fork_followup_prior import prior

        assert prior(db, SUBJECT, "fork-fixture", attempt)[0] == evidence
        real_certify = related_fork_assessment_search.certify
        proved = []

        def record_proof(board, moves, fingerprint):
            proved.append(moves[1])
            return real_certify(board, moves, fingerprint)

        with monkeypatch.context() as patch:
            patch.setattr(related_fork_assessment_search, "certify", record_proof)
            next_page = client.get("/plan/forks/next", base_url=base, headers=headers)
        assert b"same fork pattern and similar difficulty" in next_page.data
        assert proved == ["g5f7"]
        assert b"g5f7" not in next_page.data and b"different-band" not in next_page.data
        form = {
            "csrf": token(next_page, "csrf"),
            "reference": token(next_page, "reference"),
            "assessment": "1",
            "prior": attempt,
        }
        from chess_coach import fork_followup_admission

        count = db.connection.execute("SELECT COUNT(*) FROM unified_sessions").fetchone()[0]
        stripped = {key: value for key, value in form.items() if key != "prior"}
        response = client.post(
            f"/evidence/{evidence}/related-forks/start",
            base_url=base,
            headers=headers | {"Origin": base},
            data=stripped,
        )
        assert response.status_code == 400
        # Even a different eligible prior with the same cohort cannot reuse this reference.
        expected_context = prior(db, SUBJECT, "fork-fixture", attempt)[1]
        with monkeypatch.context() as patch:
            patch.setattr(
                fork_followup_admission, "previous", lambda *_args: (evidence, expected_context)
            )
            swapped = client.post(
                f"/evidence/{evidence}/related-forks/start",
                base_url=base,
                headers=headers | {"Origin": base},
                data={**form, "prior": "another-prior"},
            )
        assert swapped.status_code == 400
        with monkeypatch.context() as patch:
            altered_cohort = {
                **expected_context,
                "rating_band": expected_context["rating_band"] + 1,
            }
            patch.setattr(
                fork_followup_admission, "previous", lambda *_args: (evidence, altered_cohort)
            )
            wrong_cohort = client.post(
                f"/evidence/{evidence}/related-forks/start",
                base_url=base,
                headers=headers | {"Origin": base},
                data=form,
            )
        assert wrong_cohort.status_code == 400
        ordinary = client.post(
            f"/evidence/{evidence}/related-forks/start",
            base_url=base,
            headers=headers | {"Origin": base},
            data={key: value for key, value in stripped.items() if key != "assessment"},
        )
        assert ordinary.status_code == 400
        assert db.connection.execute("SELECT COUNT(*) FROM unified_sessions").fetchone()[0] == count

        original_context = fork_followup_admission.context

        def changed_context(current_db, version, key):
            value = original_context(current_db, version, key)
            return {**value, "rating_band": value["rating_band"] + 1} if key == "match" else value

        with monkeypatch.context() as patch:
            patch.setattr(fork_followup_admission, "context", changed_context)
            stale_match = client.post(
                f"/evidence/{evidence}/related-forks/start",
                base_url=base,
                headers=headers | {"Origin": base},
                data=form,
            )
        assert stale_match.status_code == 400
        next_page = client.get(
            "/plan/forks/next?attempt=" + attempt, base_url=base, headers=headers
        )
        form["csrf"], form["reference"] = token(next_page, "csrf"), token(next_page, "reference")
        second = client.post(
            f"/evidence/{evidence}/related-forks/start",
            base_url=base,
            headers=headers | {"Origin": base},
            data=form,
        )
        assert second.status_code == 303
        second_page = client.get(second.location, base_url=base, headers=headers)
        second_attempt = token(second_page, "attempt")
        second_row = db.connection.execute(
            "SELECT source_key,provenance_json FROM unified_sessions WHERE attempt_id=?",
            (second_attempt,),
        ).fetchone()
        assert second_row["source_key"] == "match"
        assert (
            json.loads(second_row["provenance_json"])["related_fork"]["assessment"]["context"]
            == json.loads(original_row["provenance_json"])["related_fork"]["assessment"]["context"]
        )
        still_offered = focus()
        assert ("/plan/forks/next?attempt=" + attempt).encode() in still_offered.data

        db.connection.executemany(
            "INSERT INTO unified_sessions ("
            + ",".join(columns)
            + ") VALUES ("
            + ",".join("?" for _ in columns)
            + ")",
            [
                tuple(
                    ({**unrelated, "attempt_id": f"unrelated-{index}"})[column]
                    for column in columns
                )
                for index in range(205)
            ],
        )
        db.connection.commit()
        from chess_coach.fork_followup_finder import latest

        assert latest(db, SUBJECT, "fork-fixture") == attempt
        from chess_coach import fork_history

        with monkeypatch.context() as patch:
            patch.setattr(fork_history, "select", lambda *_args, **_kwargs: ([], True))
            assert b"bounded session window or source checks were incomplete" in history()

        from chess_coach import fork_branch
        from chess_coach.opening_queue_budget import BrowserBudget
        from chess_coach.tactical_course_budget import PreviewUnavailable

        real_capture, real_check = fork_branch.capture, BrowserBudget.check
        calls = []

        def expire_in_capture(*args, **kwargs):
            value = real_capture(*args, **kwargs)
            calls.append(1)
            return value

        def check_deadline(budget):
            if calls:
                raise PreviewUnavailable("synthetic deadline")
            return real_check(budget)

        with monkeypatch.context() as patch:
            patch.setattr(fork_branch, "capture", expire_in_capture)
            patch.setattr(BrowserBudget, "check", check_deadline)
            assert b"bounded session window or source checks were incomplete" in history()
        assert len(calls) == 1

        from chess_coach import capture_history_select
        from chess_coach.related_fork_assessment_scope import is_source

        row = db.connection.execute(
            "SELECT * FROM unified_sessions WHERE attempt_id=?", (attempt,)
        ).fetchone()
        earlier = dict(row)
        earlier.update(
            attempt_id="earlier", started_at="2000-01-01T00:00:00+00:00", source_type="public"
        )
        with monkeypatch.context() as patch:
            patch.setattr(capture_history_select, "rows", lambda *_: ([earlier, row], False))
            assert capture_history_select.select(db, SUBJECT, predicate=is_source)[0] == []
        from chess_coach.fork_history_proof import valid
        from chess_coach.objective_current import current
        from chess_coach.objective_history_dispatch import replay

        request = db.connection.execute(
            "SELECT * FROM objective_requests WHERE attempt_id=?", (attempt,)
        ).fetchone()
        session, events = current(db, request)
        board, first_move = replay(db, session, events, request)
        assert not valid({**output, "move": "b5a3"}, request, events, board, first_move)
        assert not valid({**output, "status": "incorrect"}, request, events, board, first_move)
    review_evidence(db, evidence, decision="reject", actor="fixture_reviewer")
    stale_focus = focus()
    assert b"Find a comparable follow-up fork assessment" not in stale_focus.data
    assert b"verified miss" not in stale_focus.data
    stale_history = history()
    assert (
        b"2 unavailable or stale" if mode == "correct" else b"1 unavailable or stale"
    ) in stale_history
    assert (b"1 assisted" if mode == "assisted" else b"0 assisted") in stale_history
    with pytest.raises(ValueError):
        show(db, attempt, SUBJECT)
    db.close()


def test_certified_pawn_fork_miss_control():
    import chess

    from chess_coach.fork_assessment_miss_result import valid, verdict
    from chess_coach.related_capture_assessment import HISTORY
    from chess_coach.related_fork_assessment import certify
    from chess_coach.related_fork_features import corpus_fork_features

    fen = "8/7p/8/3k1n2/8/8/4P3/K3RR2 b - - 0 1"
    solution = "h7h6 e2e4 d5c6 e4f5"
    prompt, features = corpus_fork_features(fen, solution)
    board = chess.Board(prompt)
    certificate = certify(board, solution.split(), "synthetic")
    assert features and features["mover"] == chess.PAWN
    assert certificate["attacker"] == "e2" and certificate["anchor"] == "d5"

    data = {"related_fork": {"assessment": certificate}, "fork_attacker": "e2", "fork_anchor": "d5"}
    request = {"history_mode": HISTORY}
    session = {
        "source_type": "corpus",
        "objective": "execute_named_fork",
        "provenance_json": json.dumps(data),
    }
    for move, expected in (
        ("e1d1", "named_attacker_not_moved"),
        ("e2e3", "named_target_not_attacked"),
    ):
        move = chess.Move.from_uci(move)
        result = verdict(board, move, chess.E2, chess.D5, request, data, {})
        assert result and result["status"] == "incorrect" and result["reason"] == expected
        assert valid(result, board, move, session)
    assert (
        verdict(board, chess.Move.from_uci("e2e4"), chess.E2, chess.D5, request, data, {}) is None
    )
    assert (
        verdict(
            board,
            chess.Move.from_uci("e2e3"),
            chess.E2,
            chess.D5,
            {"history_mode": "owned"},
            data,
            {},
        )
        is None
    )
