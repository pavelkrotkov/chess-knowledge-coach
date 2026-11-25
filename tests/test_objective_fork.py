"""Owned fork objectives verify equivalent moves without inventing game results."""

import json
import re

import pytest

from chess_coach.objective_fork_contract import MISS_VERSION, VERSION
from chess_coach.objective_fork_list import candidates
from chess_coach.objective_status import inspect
from chess_coach.objective_worker import process
from chess_coach.unified_session_events import show, submit
from chess_coach.web import create_app
from tests.objective_fork_support import SUBJECT, begin, owned_fork
from tests.test_unified_sessions import token


@pytest.mark.parametrize("played,outcome", [("f6g5", "failure"), ("b5c7", "success")])
def test_unlisted_owned_fork_is_proved_for_success_and_miss(tmp_path, monkeypatch, played, outcome):
    if played == "f6g5":
        _daily_fork_workflow(tmp_path, monkeypatch)
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
    assert f'name="version" value="{MISS_VERSION}"' in section
    posted = client.post(
        "/unified/start",
        base_url="https://coach.invalid",
        headers=headers | {"Origin": "https://coach.invalid"},
        data={
            "csrf": token(library, "csrf"),
            "source_type": "own-game",
            "version": MISS_VERSION,
            "key": str(evidence),
        },
    )
    assert posted.status_code == 303
    page = client.get(posted.location, base_url="https://coach.invalid", headers=headers)
    assert page.status_code == 200
    assert b"piece on b5" in page.data and b"piece on e8" in page.data
    assert b"not automatically a blunder" in page.data
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
            "unified_training_enrollments",
            "unified_training_completions",
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

    # New policy binds a separate version and preserves the old unresolved session.
    from chess_coach.fork_history_proof import valid as valid_result
    from chess_coach.objective_current import current as current_request
    from chess_coach.objective_history_dispatch import replay as replay_answer
    from chess_coach.unified_session_events import hint, reveal

    with pytest.raises(ValueError, match="another source"):
        begin(db, evidence, attempt="owned-unsupported", version=MISS_VERSION)
    assert begin(db, evidence, attempt="owned-unsupported")["status"] == "needs_verification"
    assert inspect(db, SUBJECT, "owned-unsupported", "answer")["status"] == "unresolved"

    for attempt, move in (("v2-exemplar", "b5c7"), ("v2-alternative", "b5d6")):
        state = begin(db, evidence, attempt=attempt, version=MISS_VERSION)
        assert state["fork_objective_miss_policy"] and state["learner_color"] == "white"
        assert (
            submit(db, attempt, SUBJECT, event_id="answer", move=move)["status"]
            == "needs_verification"
        )
        assert process(db, SUBJECT)["outcomes"] == {"correct": 1}
        assert inspect(db, SUBJECT, attempt, "answer")["status"] == "correct"

    begin(db, evidence, attempt="v2-miss", version=MISS_VERSION)
    hint(db, "v2-miss", SUBJECT, event_id="hint")
    reveal(db, "v2-miss", SUBJECT, event_id="reveal")
    answer = submit(db, "v2-miss", SUBJECT, event_id="answer", move="e7d6")
    assert answer["status"] == "needs_verification"
    assert process(db, SUBJECT)["outcomes"] == {"incorrect": 1}
    missed = inspect(db, SUBJECT, "v2-miss", "answer")
    assert missed["reason"] == "named_attacker_not_moved" and missed["assistance"] == "revealed"
    page = client.get("/unified/v2-miss", base_url="https://coach.invalid", headers=headers)
    assert b"Objective missed" in page.data and b"named piece was not moved" in page.data
    assert b"learner plays white" in page.data
    assert submit(db, "v2-miss", SUBJECT, event_id="answer", move="e7d6") == answer

    request = db.connection.execute(
        "SELECT * FROM objective_requests WHERE attempt_id='v2-miss'"
    ).fetchone()
    session, events = current_request(db, request)
    board, move = replay_answer(db, session, events, request)
    assert not valid_result(result, request, events, board, move, session)
    from chess_coach.objective_fork_owned_replay import valid as valid_owned_miss

    stored = json.loads(
        db.connection.execute(
            "SELECT result_json FROM objective_results WHERE attempt_id='v2-miss'"
        ).fetchone()[0]
    )
    assert not valid_owned_miss(stored, board, move, dict(session) | {"source_type": "corpus"})
    begin(db, evidence, attempt="v2-unresolved", version=MISS_VERSION)
    submit(db, "v2-unresolved", SUBJECT, event_id="answer", move="f6g5")
    assert process(db, SUBJECT)["outcomes"] == {"unresolved": 1}
    begin(db, evidence, attempt="v2-capture", version=MISS_VERSION)
    submit(db, "v2-capture", SUBJECT, event_id="answer", move="f6f5")
    assert process(db, SUBJECT)["outcomes"] == {"unresolved": 1}

    import itertools

    begin(db, evidence, attempt="v2-timeout", version=MISS_VERSION)
    submit(db, "v2-timeout", SUBJECT, event_id="answer", move="e7d6")
    ticks = itertools.count()
    assert process(db, SUBJECT, clock=lambda: next(ticks), seconds=0.01)["outcomes"] == {
        "unresolved": 1
    }
    assert inspect(db, SUBJECT, "v2-timeout", "answer")["reason"] == "timeout"

    if played == "f6g5":
        black, black_evidence = owned_fork(
            tmp_path / "black.sqlite", monkeypatch, played, with_history=True, mirrored=True
        )
        state = begin(black, black_evidence, attempt="black", version=MISS_VERSION)
        assert state["learner_color"] == "black"
        assert (state["fork_attacker"], state["fork_anchor"]) == ("b4", "e1")
        submit(black, "black", SUBJECT, event_id="answer", move="b4d3")
        assert process(black, SUBJECT)["outcomes"] == {"correct": 1}
        black_request = black.connection.execute(
            "SELECT * FROM objective_requests WHERE attempt_id='black'"
        ).fetchone()
        black_session, black_events = current_request(black, black_request)
        black_board, _ = replay_answer(black, black_session, black_events, black_request)
        assert len(black_board.move_stack) == 1
        begin(black, black_evidence, attempt="black-miss", version=MISS_VERSION)
        submit(black, "black-miss", SUBJECT, event_id="answer", move="e2d3")
        assert process(black, SUBJECT)["outcomes"] == {"incorrect": 1}
        assert (
            inspect(black, SUBJECT, "black-miss", "answer")["reason"] == "named_attacker_not_moved"
        )
        from chess_coach.unified_sessions import start

        start(
            black,
            attempt_id="black-learning",
            subject=SUBJECT,
            source_type="own-game",
            version=MISS_VERSION,
            key=str(black_evidence),
            training=True,
        )
        submit(black, "black-learning", SUBJECT, event_id="answer", move="b4d3")
        assert process(black, SUBJECT)["outcomes"] == {"correct": 1}
        assert show(black, "black-learning", SUBJECT)["learning"]["rating"] == "good"
        black.close()
        anchor_db, anchor_evidence = owned_fork(
            tmp_path / "anchor.sqlite", monkeypatch, played, anchor_layout=True
        )
        begin(anchor_db, anchor_evidence, attempt="anchor", version=MISS_VERSION)
        submit(anchor_db, "anchor", SUBJECT, event_id="answer", move="b5d4")
        assert process(anchor_db, SUBJECT)["outcomes"] == {"incorrect": 1}
        assert (
            inspect(anchor_db, SUBJECT, "anchor", "answer")["reason"] == "named_target_not_attacked"
        )

    assert {
        table: db.connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        for table in before
    } == before

    learning = None
    if played == "f6g5":
        learning = _fork_learning_workflow(db, evidence, client, headers, monkeypatch)

    # Revocation after a queued answer invalidates its source, without grading it.
    from chess_coach.evidence_review import review_evidence

    begin(db, evidence, attempt="v2-stale", version=MISS_VERSION)
    submit(db, "v2-stale", SUBJECT, event_id="answer", move="e7d6")
    review_evidence(db, evidence, decision="reject", actor="fixture")
    assert process(db, SUBJECT)["outcomes"] == {"unresolved": 1}
    assert inspect(db, SUBJECT, "v2-stale", "answer")["reason"] == "source_unavailable"
    if learning:
        from chess_coach.mastery_unified_training import training_context
        from chess_coach.unified_training_complete import complete

        with pytest.raises(ValueError):
            complete(db, learning["attempt"], SUBJECT)
        item = db.connection.execute(
            "SELECT * FROM evidence_mappings WHERE id=?", (learning["evidence_id"],)
        ).fetchone()
        assert training_context(db, item) == (None, "invalid_training_lineage")


def _fork_learning_workflow(db, evidence, client, headers, monkeypatch):
    from chess_coach import unified_capture_completion
    from chess_coach.unified_session_events import reveal
    from chess_coach.unified_sessions import start
    from chess_coach.unified_training_complete import complete

    base = "https://coach.invalid"
    library = client.get("/library?family=fork", base_url=base, headers=headers)
    assert b"Practice and schedule this fork" in library.data
    posted = client.post(
        "/unified/start",
        base_url=base,
        headers=headers | {"Origin": base},
        data={
            "csrf": token(library, "csrf"),
            "source_type": "own-game",
            "version": MISS_VERSION,
            "key": str(evidence),
            "training": "1",
        },
    )
    assert posted.status_code == 303
    page = client.get(posted.location, base_url=base, headers=headers)
    attempt = token(page, "attempt")
    answer = submit(db, attempt, SUBJECT, event_id="answer", move="b5d6")
    assert answer["status"] == "needs_verification"
    with monkeypatch.context() as patch:
        patch.setattr(
            unified_capture_completion,
            "review_item_in_transaction",
            lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("synthetic rollback")),
        )
        assert process(db, SUBJECT)["outcomes"] == {"correct": 1}
    assert show(db, attempt, SUBJECT)["learning"]["state"] == "pending"
    assert (
        db.connection.execute(
            "SELECT COUNT(*) FROM unified_training_completions WHERE attempt_id=?", (attempt,)
        ).fetchone()[0]
        == 0
    )
    receipt = complete(db, attempt, SUBJECT, event_id="answer")
    assert receipt["outcome"] == "success" and receipt["rating"] == "good"
    assert receipt["evidence_id"] and complete(db, attempt, SUBJECT) == receipt
    from chess_coach.mastery_unified_training import training_context

    evidence_row = db.connection.execute(
        "SELECT * FROM evidence_mappings WHERE id=?", (receipt["evidence_id"],)
    ).fetchone()
    assert training_context(db, evidence_row)[0]["attempt_id"] == attempt
    assert (
        db.connection.execute(
            "SELECT human_validated FROM evidence_mappings WHERE id=?", (receipt["evidence_id"],)
        ).fetchone()[0]
        == 0
    )
    db.connection.execute(
        "UPDATE training_items SET due='2000-01-01T00:00:00+00:00' WHERE id=?",
        (receipt["item_id"],),
    )
    db.connection.commit()
    plan = client.get("/plan", base_url=base, headers=headers)
    assert b"Execute the named fork." in plan.data
    assert (f'name="item_id" value="{receipt["item_id"]}"').encode() in plan.data
    reopened = client.post(
        "/unified/start",
        base_url=base,
        headers=headers | {"Origin": base},
        data={
            "csrf": token(plan, "csrf"),
            "source_type": "own-game",
            "version": MISS_VERSION,
            "key": str(evidence),
            "training": "1",
            "item_id": str(receipt["item_id"]),
        },
    )
    assert reopened.status_code == 303
    resumed = client.get(reopened.location, base_url=base, headers=headers)
    assert b"piece on b5" in resumed.data and b"piece on e8" in resumed.data

    source = dict(
        subject=SUBJECT,
        source_type="own-game",
        version=MISS_VERSION,
        key=str(evidence),
        training=True,
    )
    start(db, attempt_id="fork-learning-miss", **source)
    submit(db, "fork-learning-miss", SUBJECT, event_id="answer", move="e7d6")
    assert process(db, SUBJECT)["outcomes"] == {"incorrect": 1}
    missed = show(db, "fork-learning-miss", SUBJECT)["learning"]
    assert missed["outcome"] == "failure" and missed["rating"] == "again"
    start(db, attempt_id="fork-learning-assisted", **source)
    previous = tuple(
        db.connection.execute(
            "SELECT due,last_review FROM training_items WHERE id=?", (receipt["item_id"],)
        ).fetchone()
    )
    assert (
        submit(db, "fork-learning-assisted", SUBJECT, event_id="illegal", move="a1a2")["feedback"]
        == "illegal"
    )
    reveal(db, "fork-learning-assisted", SUBJECT, event_id="reveal")
    submit(db, "fork-learning-assisted", SUBJECT, event_id="answer", move="b5c7")
    assert process(db, SUBJECT)["outcomes"] == {"correct": 1}
    assisted = show(db, "fork-learning-assisted", SUBJECT)["learning"]
    assert assisted["assistance"] == "assisted"
    assert assisted["rating"] is None and assisted["evidence_id"] is None
    assert (
        tuple(
            db.connection.execute(
                "SELECT due,last_review FROM training_items WHERE id=?", (receipt["item_id"],)
            ).fetchone()
        )
        == previous
    )
    start(db, attempt_id="fork-learning-unknown", **source)
    submit(db, "fork-learning-unknown", SUBJECT, event_id="answer", move="f6g5")
    assert process(db, SUBJECT)["outcomes"] == {"unresolved": 1}
    assert show(db, "fork-learning-unknown", SUBJECT)["learning"]["state"] == "unresolved"
    with pytest.raises(ValueError):
        complete(db, "fork-learning-unknown", SUBJECT)
    with pytest.raises(ValueError):
        start(db, attempt_id="fork-learning-v1", **(source | {"version": VERSION}))
    with pytest.raises(ValueError):
        start(db, attempt_id="fork-other-owner", **(source | {"subject": "someone-else"}))
    return {"attempt": attempt, "evidence_id": receipt["evidence_id"]}


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
            ("harder", "3k3b/3B3p/2K5/2b3N1/8/8/8/8 b - - 0 1", "h7h6 g5f7 d8e7 f7h8", 1400),
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
        pending_harder = client.get(
            "/plan/forks/next?attempt=" + second_attempt + "&harder=1",
            base_url=base,
            headers=headers,
        )
        assert b"No harder certified unfamiliar fork" in pending_harder.data
        submit(db, second_attempt, SUBJECT, event_id="answer", move="g5f7")
        assert process(db, SUBJECT)["outcomes"] == {"correct": 1}
        second_page = client.get(second.location, base_url=base, headers=headers)
        assert b"Check whether a harder fork is available" in second_page.data
        harder = client.get(
            "/plan/forks/next?attempt=" + second_attempt + "&harder=1",
            base_url=base,
            headers=headers,
        )
        assert b"1400" in harder.data and b"1599" in harder.data
        hard_form = {
            "csrf": token(harder, "csrf"),
            "reference": token(harder, "reference"),
            "assessment": "1",
            "prior": "harder:" + second_attempt,
        }
        rejected = client.post(
            f"/evidence/{evidence}/related-forks/start",
            base_url=base,
            headers=headers | {"Origin": base},
            data={**hard_form, "prior": second_attempt},
        )
        assert rejected.status_code == 400
        from chess_coach import fork_difficulty_history

        with monkeypatch.context() as patch:
            patch.setattr(
                fork_difficulty_history,
                "_prior",
                lambda *_args: (_ for _ in ()).throw(ValueError()),
            )
            stale = client.post(
                f"/evidence/{evidence}/related-forks/start",
                base_url=base,
                headers=headers | {"Origin": base},
                data=hard_form,
            )
            assert stale.status_code == 400
        started = client.post(
            f"/evidence/{evidence}/related-forks/start",
            base_url=base,
            headers=headers | {"Origin": base},
            data=hard_form,
        )
        assert started.status_code == 303
        hard_page = client.get(started.location, base_url=base, headers=headers)
        hard_attempt = token(hard_page, "attempt")
        assert (
            db.connection.execute(
                "SELECT source_key FROM unified_sessions WHERE attempt_id=?", (hard_attempt,)
            ).fetchone()[0]
            == "harder"
        )

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

        assert latest(db, SUBJECT, "fork-fixture") == second_attempt
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
        b"3 unavailable or stale" if mode == "correct" else b"1 unavailable or stale"
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


def _daily_fork_workflow(tmp_path, monkeypatch):
    import io
    import sys
    from datetime import UTC, datetime, timedelta

    import chess.pgn

    import chess_coach.curriculum as curriculum
    from chess_coach.curriculum import daily_plan
    from chess_coach.curriculum_canonical_cursor import fields as canonical_fields
    from chess_coach.fork_detector import process_decision
    from chess_coach.ingest import ingest_pgn
    from chess_coach.pipeline_config import PipelineConfig
    from chess_coach.pipeline_inputs import engine_identity, game_input
    from chess_coach.pipeline_work import run_analysis

    root = tmp_path / "plan-project"
    data = root / ".runtime" / "data"
    data.mkdir(parents=True)
    planning = root / ".runtime" / "planning"
    planning.mkdir(mode=0o700)
    path = data / "fork-plan.sqlite"
    v6_new_state = curriculum.new_state

    def public_v5_state(*args):
        state = v6_new_state(*args)
        for field in canonical_fields():
            del state[field]
        state["v"] = 5
        state["family_turn"] = args[-1].date().toordinal() % 3
        return state

    monkeypatch.setattr(curriculum, "new_state", public_v5_state)
    db, _ = owned_fork(path, monkeypatch, "f6g5")
    source = db.connection.execute("SELECT pgn FROM games WHERE id=1").fetchone()[0]
    config = PipelineConfig(
        learner=SUBJECT, engine_path=sys.executable, nodes=100, deep_enabled=False
    )
    for index in (2, 3):
        game = chess.pgn.read_game(io.StringIO(source))
        assert game is not None
        game.headers["UTCDate"] = f"2026.01.0{index}"
        game.headers["UTCTime"] = "12:00:00"
        ingest_pgn(db, str(game))
        assert (
            run_analysis(db, index, game_input(db, index), config, engine_identity(sys.executable))[
                "status"
            ]
            == "complete"
        )
        position = db.connection.execute(
            "SELECT id FROM positions WHERE game_id=? ORDER BY ply LIMIT 1", (index,)
        ).fetchone()[0]
        process_decision(db, position, SUBJECT)
    # A second synthetic learner has a distinct qualified capture need; the
    # fork learner also has capture evidence so one plan can exercise the mix.
    from chess_coach.material_detector import process_decision as material_decision
    from tests.test_material_pipeline import LEARNER, make_game

    seed = make_game(tmp_path / "capture-plan-seed.sqlite", monkeypatch)
    material_pgn = seed.connection.execute("SELECT pgn FROM games WHERE id=1").fetchone()[0]
    seed.close()
    for owner in (SUBJECT, "capture_learner"):
        for day in ("01", "02"):
            game = chess.pgn.read_game(io.StringIO(material_pgn.replace(LEARNER, owner)))
            assert game is not None
            game.headers["UTCDate"] = f"2026.01.{day}"
            ingest_pgn(db, str(game))
            game_id = db.connection.execute("SELECT max(id) FROM games").fetchone()[0]
            material_config = PipelineConfig(learner=owner, engine_path=sys.executable, nodes=100)
            assert (
                run_analysis(
                    db,
                    game_id,
                    game_input(db, game_id),
                    material_config,
                    engine_identity(sys.executable),
                )["status"]
                == "complete"
            )
            position = db.connection.execute(
                "SELECT id FROM positions WHERE game_id=? ORDER BY ply LIMIT 1", (game_id,)
            ).fetchone()[0]
            material_decision(db, position, owner)
    from chess_coach.training import create_training_item, review_item

    corpus = db.connection.execute(
        "INSERT INTO puzzle_corpora(version,source,checksum,state) "
        "VALUES('fixture','fixture','checksum','staging')"
    ).lastrowid
    for name in ("one", "two"):
        db.connection.execute(
            """INSERT INTO puzzles(puzzle_id,corpus_id,fen,source,solution,rating,
            rating_deviation,themes_json,objective)
            VALUES(?,?,'7k/1p6/6K1/2Q5/8/8/8/8 b - - 17 14',
            'fixture','b7b6 c5f8',1200,80,'[]','unknown')""",
            (name, corpus),
        )
    db.connection.execute("UPDATE puzzle_corpora SET state='ready' WHERE id=?", (corpus,))
    db.connection.commit()
    now = datetime.now(UTC)
    # An absent optional public catalog is unavailable, not an empty learner need.
    no_catalog_time = now
    while no_catalog_time.date().toordinal() % 3 != 2:
        no_catalog_time -= timedelta(days=1)
    no_catalog = daily_plan(db, subject=SUBJECT, corpus_version="fixture", as_of=no_catalog_time)
    assert no_catalog["public_status"] == "unavailable"
    for name in ("one", "two"):
        item = create_training_item(
            db,
            source_type="puzzle",
            source_ref=json.dumps(["fixture", name]),
            skill="mate_in_one",
            operation="execute",
        )
        review_item(db, item, "good", reviewed_at=now)
    before = db.connection.total_changes
    plan = daily_plan(db, subject=SUBJECT, corpus_version="fixture", as_of=now)
    other = daily_plan(db, subject="capture_learner", corpus_version="fixture", as_of=now)
    assert db.connection.total_changes == before
    assert any(item["skill"] == "hanging_piece" for item in plan["items"])
    assert any(item["skill"] == "hanging_piece" for item in other["items"])
    assert all(item["skill"] != "fork" for item in other["items"])
    fork = next(item for item in plan["items"] if item["skill"] == "fork")
    assert fork["source_version"] == MISS_VERSION and fork["independent_games"] == 2
    assert fork["source_review"] == "unreviewed" and "Provisional" in fork["reason"]

    # Goal choice reorders only already qualified new sources; the signed
    # window uses server time independently of the plan's fixed as_of.
    import sqlite3

    import chess_coach.curriculum_window_scope as window_scope
    from chess_coach.curriculum_window_cursor import decode as decode_window
    from chess_coach.db import Database
    from chess_coach.unified_sessions import start

    with monkeypatch.context() as window_test:
        wall = [datetime.now(UTC)]
        window_test.setattr(window_scope, "clock", lambda: wall[0])
        capture_goal = daily_plan(
            db,
            subject=SUBJECT,
            corpus_version="fixture",
            as_of=now,
            limit=1,
            goal="capture",
            duration_minutes=1,
        )
        fork_goal = daily_plan(
            db,
            subject=SUBJECT,
            corpus_version="fixture",
            as_of=now,
            limit=1,
            goal="fork",
            duration_minutes=1,
        )
        capture_item = capture_goal["items"][0]
        fork_item = fork_goal["items"][0]
        assert capture_item["skill"] == "hanging_piece" and fork_item["skill"] == "fork"
        assert (
            capture_goal["window"]["goal_status"]
            == fork_goal["window"]["goal_status"]
            == "available"
        )
        assert capture_item["window_offer"] and fork_item["window_offer"]
        cursor = fork_goal["window_cursor"]
        original = decode_window(db, cursor)
        assert original["v"] == 7 and original["goal"] == "fork"
        assert original["state"]["as_of"] == now.isoformat()
        with pytest.raises(ValueError):
            daily_plan(
                db, subject="other", corpus_version="fixture", as_of=now, limit=1, cursor=cursor
            )
        with pytest.raises(ValueError):
            daily_plan(
                db,
                subject=SUBJECT,
                corpus_version="fixture",
                as_of=now,
                limit=1,
                cursor=cursor,
                goal="capture",
            )
        with pytest.raises(ValueError, match="unsupported"):
            daily_plan(db, subject=SUBJECT, corpus_version="fixture", goal="unknown")
        copy_path = tmp_path / "window-plan.sqlite"
        target = sqlite3.connect(copy_path)
        db.connection.backup(target)
        target.close()
        copy_db = Database(copy_path)
        wall[0] += timedelta(seconds=61)
        expired = daily_plan(
            db, subject=SUBJECT, corpus_version="fixture", as_of=now, limit=1, cursor=cursor
        )
        assert expired["window"]["expired"] and all(
            item["kind"] == "due" for item in expired["items"]
        )
        with pytest.raises(ValueError, match="expired"):
            start(
                copy_db,
                attempt_id="expired-window",
                subject=SUBJECT,
                source_type="own-game",
                version=fork_item["source_version"],
                key=fork_item["source_key"],
                training=True,
                window_offer=fork_item["window_offer"],
            )
        assert (
            copy_db.connection.execute("SELECT count(*) FROM unified_sessions").fetchone()[0] == 0
        )
        renewed = daily_plan(
            db,
            subject=SUBJECT,
            corpus_version="fixture",
            as_of=now,
            limit=1,
            cursor=expired["window_cursor"],
            renew=True,
        )
        renewed_state = decode_window(db, renewed["window_cursor"])
        assert not renewed["window"]["expired"]
        assert set(original["state"]["seen"]).issubset(renewed_state["state"]["seen"])
        assert all(item["prompt_key"] not in original["state"]["seen"] for item in renewed["items"])
        wall[0] -= timedelta(seconds=61)
        started = start(
            copy_db,
            attempt_id="active-window",
            subject=SUBJECT,
            source_type="own-game",
            version=fork_item["source_version"],
            key=fork_item["source_key"],
            training=True,
            window_offer=fork_item["window_offer"],
        )
        wall[0] += timedelta(seconds=61)
        assert show(copy_db, "active-window", SUBJECT)["status"] == started["status"]
        copy_db.close()

    # A partially checked fork conflict keeps its exact binding and position.
    from types import SimpleNamespace

    # Retain explicit coverage of signed v4 continuation behavior.
    import chess_coach.curriculum_capture_conflict as conflict
    import chess_coach.curriculum_family_mix as family_mix
    import chess_coach.fork_evidence_verify as fork_verify
    from chess_coach.curriculum_cursor_codec import decode_cursor
    from chess_coach.curriculum_public_cursor import fields as public_fields

    current_new_state = curriculum.new_state

    def legacy_new_state(*args):
        state = current_new_state(*args)
        for key in public_fields():
            state.pop(key)
        state["v"] = 4
        return state

    monkeypatch.setattr(curriculum, "new_state", legacy_new_state)
    fork_time = now
    while fork_time.date().toordinal() % 3 != 1:
        fork_time -= timedelta(days=1)

    def bounded(cursor=None):
        return daily_plan(
            db,
            subject=SUBJECT,
            corpus_version="fixture",
            as_of=fork_time,
            limit=5,
            scan_limit=1,
            cursor=cursor,
        )

    pending_page = bounded()
    assert pending_page["continuation_reason"] == "scheduled_scan_incomplete"
    pending = decode_cursor(db, pending_page["next_cursor"])
    assert pending["phase"] == "fork" and pending["fork_pending"] and pending["scheduled_after"]
    from chess_coach.evidence_review import review_evidence

    db.connection.execute("BEGIN")
    review_evidence(db, fork["source_evidence_id"], decision="reject", actor="fixture")
    with pytest.raises(ValueError, match="sources changed"):
        bounded(pending_page["next_cursor"])
    db.connection.rollback()
    clock = [0.0]
    visited = []

    def expire(observer, prepared, check):
        assert check is not None
        visited.append(True)
        clock[0] = 3.0
        check()

    with monkeypatch.context() as patch:
        patch.setattr(family_mix, "time", SimpleNamespace(monotonic=lambda: clock[0]))
        patch.setattr(fork_verify, "_observe", expire)
        interrupted = bounded(pending_page["next_cursor"])
    after = decode_cursor(db, interrupted["next_cursor"])
    assert visited and interrupted["continuation_reason"] == "fork_scan_incomplete"
    assert (after["fork_pending"], after["scheduled_after"]) == (
        pending["fork_pending"],
        pending["scheduled_after"],
    )
    resumed = bounded(interrupted["next_cursor"])
    assert any(item["skill"] == "fork" for item in resumed["items"])

    # An interrupted scheduled query has already bound the fork candidate.
    import sqlite3

    clock[0] = 0.0

    def interrupted_query(*_args, **_kwargs):
        clock[0] = 3.0
        raise sqlite3.OperationalError("synthetic interruption")

    with monkeypatch.context() as patch:
        patch.setattr(family_mix, "time", SimpleNamespace(monotonic=lambda: clock[0]))
        patch.setattr(conflict, "scheduled_page", interrupted_query)
        bound = bounded()
    bound_state = decode_cursor(db, bound["next_cursor"])
    assert bound["continuation_reason"] == "fork_scan_incomplete"
    assert bound_state["phase"] == "fork" and bound_state["fork_pending"]
    assert bounded(bound["next_cursor"])["next_cursor"]

    # A deadline before any candidate is bound defers this family once and
    # lets the next signed page check other families instead of starving them.
    clock[0] = 0.0
    with monkeypatch.context() as patch:
        patch.setattr(family_mix, "time", SimpleNamespace(monotonic=lambda: clock[0]))
        patch.setattr(fork_verify, "_observe", expire)
        deferred = bounded()
    assert deferred["fork_status"] == "deferred"
    assert deferred["continuation_reason"] == "family_scan_incomplete"
    next_state = decode_cursor(db, deferred["next_cursor"])
    assert next_state["phase"] != "fork" and next_state["fork_pending"] is None
    subsequent = deferred
    for _ in range(6):
        subsequent = bounded(subsequent["next_cursor"])
        if subsequent["items"]:
            break
        assert subsequent["next_cursor"]
    assert subsequent["items"]

    # A broad non-mate corpus yields after its first bounded page instead of
    # holding the owned families behind every unrelated corpus row.
    broad_corpus = db.connection.execute(
        "INSERT INTO puzzle_corpora(version,source,checksum,state) "
        "VALUES('broad','fixture','broad-checksum','staging')"
    ).lastrowid
    for name in ("a-nonmate", "b-nonmate"):
        db.connection.execute(
            """INSERT INTO puzzles(puzzle_id,corpus_id,fen,source,solution,rating,
            rating_deviation,themes_json,objective)
            VALUES(?,?,?,'fixture','e2e4 e7e5',1100,80,'[]','unknown')""",
            (name, broad_corpus, chess.STARTING_FEN),
        )
    for name, solution in (
        ("candidate", "b7b5 c5f8"),
        ("candidate2", "h8g8 c5c8"),
        ("three", "b7b6 c5f8"),
        ("four", "b7b6 c5f8"),
    ):
        db.connection.execute(
            """INSERT INTO puzzles(puzzle_id,corpus_id,fen,source,solution,rating,
            rating_deviation,themes_json,objective)
            VALUES(?,?,'7k/1p6/6K1/2Q5/8/8/8/8 b - - 17 14',
            'fixture',?,1200,80,'[]','unknown')""",
            (name, broad_corpus, solution),
        )
    db.connection.execute("UPDATE puzzle_corpora SET state='ready' WHERE id=?", (broad_corpus,))
    db.connection.commit()
    for name in ("three", "four"):
        item = create_training_item(
            db,
            source_type="puzzle",
            source_ref=json.dumps(["broad", name]),
            skill="mate_in_one",
            operation="execute",
        )
        review_item(db, item, "good", reviewed_at=now)

    corpus_time = now
    while corpus_time.date().toordinal() % 3 != 2:
        corpus_time -= timedelta(days=1)

    def corpus_page(cursor=None, scan_limit=1):
        return daily_plan(
            db,
            subject=SUBJECT,
            corpus_version="broad",
            as_of=corpus_time,
            limit=5,
            scan_limit=scan_limit,
            cursor=cursor,
        )

    broad = corpus_page()
    broad_state = decode_cursor(db, broad["next_cursor"])
    assert broad["continuation_reason"] == "family_scan_incomplete"
    assert broad_state["phase"] == "capture" and broad_state["new_after"] == [1100, "a-nonmate"]
    for _ in range(8):
        broad = corpus_page(broad["next_cursor"])
        if any(item["skill"] == "hanging_piece" for item in broad["items"]):
            break
        assert broad["next_cursor"]
    assert any(item["skill"] == "hanging_piece" for item in broad["items"])

    # On a later candidate, an interrupted conflict retains its coordinate,
    # candidate digest, and any previously scanned scheduled position together.
    import chess_coach.curriculum_consider as consider

    clock[0] = 0.0

    def expire_corpus(*_args, **kwargs):
        clock[0] = 3.0
        kwargs["check"]()

    with monkeypatch.context() as patch:
        patch.setattr(family_mix, "time", SimpleNamespace(monotonic=lambda: clock[0]))
        patch.setattr(consider, "scheduled_page", expire_corpus)
        corpus_interrupted = corpus_page(scan_limit=3)
    interrupted_state = decode_cursor(db, corpus_interrupted["next_cursor"])
    assert interrupted_state["phase"] == "new"
    assert interrupted_state["new_after"] == [1100, "b-nonmate"]
    assert interrupted_state["pending"][:2] == [1200, "candidate"]
    assert interrupted_state["scheduled_after"] == 0
    corpus_pending = corpus_page(corpus_interrupted["next_cursor"], scan_limit=3)
    pending_state = decode_cursor(db, corpus_pending["next_cursor"])
    assert corpus_pending["continuation_reason"] == "scheduled_scan_incomplete"
    assert pending_state["new_after"] == interrupted_state["new_after"]
    assert pending_state["pending"] == interrupted_state["pending"]
    assert pending_state["scheduled_after"] > 0
    clock[0] = 0.0
    with monkeypatch.context() as patch:
        patch.setattr(family_mix, "time", SimpleNamespace(monotonic=lambda: clock[0]))
        patch.setattr(consider, "scheduled_page", expire_corpus)
        interrupted_again = corpus_page(corpus_pending["next_cursor"], scan_limit=3)
    after_again = decode_cursor(db, interrupted_again["next_cursor"])
    assert tuple(after_again[key] for key in ("new_after", "pending", "scheduled_after")) == tuple(
        pending_state[key] for key in ("new_after", "pending", "scheduled_after")
    )
    resumed_corpus = corpus_page(interrupted_again["next_cursor"], scan_limit=3)
    assert any(item.get("puzzle_id") == "candidate" for item in resumed_corpus["items"])

    # Final corpus fill can publish an earlier candidate even if a later
    # bound candidate hits the shared deadline on the same page.
    from chess_coach.curriculum_cursor_codec import encode_cursor

    new_state = legacy_new_state
    fill_state = new_state(db, SUBJECT, "broad", 5, 200, corpus_time)
    fill_state.update(phase="new", family_index=3, new_after=[1100, "b-nonmate"])
    fill_cursor = encode_cursor(db, fill_state)
    original_scheduled = consider.scheduled_page
    calls = [0]
    clock[0] = 0.0

    def expire_second(*args, **kwargs):
        calls[0] += 1
        if calls[0] == 2:
            clock[0] = 3.0
            kwargs["check"]()
        return original_scheduled(*args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(family_mix, "time", SimpleNamespace(monotonic=lambda: clock[0]))
        patch.setattr(consider, "scheduled_page", expire_second)
        filled = corpus_page(fill_cursor, scan_limit=200)
    assert [item["puzzle_id"] for item in filled["items"]] == ["candidate"]
    fill_pending = decode_cursor(db, filled["next_cursor"])
    assert fill_pending["new_after"] == [1200, "candidate"]
    assert fill_pending["pending"][:2] == [1200, "candidate2"]
    assert filled["items"][0]["prompt_key"] in fill_pending["seen"]
    after_fill = corpus_page(filled["next_cursor"], scan_limit=200)
    assert any(item.get("puzzle_id") == "candidate2" for item in after_fill["items"])

    # Repeated one-item checkpoints retain one shared page work allowance.
    one_state = new_state(db, SUBJECT, "broad", 5, 1, corpus_time)
    one_state.update(phase="new", family_index=3, new_after=[1100, "b-nonmate"])
    page_cursor = encode_cursor(db, one_state)
    found = []
    for _ in range(12):
        next_page = corpus_page(page_cursor, scan_limit=1)
        assert next_page["scan"]["corpus_examined"] <= 1
        assert next_page["scan"]["scheduled_examined"] <= 1
        found.extend(item.get("puzzle_id") for item in next_page["items"])
        if "candidate2" in found:
            break
        page_cursor = next_page["next_cursor"]
        assert page_cursor
    assert found[:2] == ["candidate", "candidate2"]

    monkeypatch.setattr(curriculum, "new_state", current_new_state)

    # The current default offers an imported, licensed public mate alongside
    # both owned skills, and rechecks file-backed delivery at actual start.
    import os

    import chess_coach.curriculum_public_candidate as public_candidate
    from chess_coach.deep_selection_source import learner_key
    from chess_coach.fact_fingerprint import digest
    from chess_coach.public_mate_contract import OBJECTIVE as PUBLIC_MATE
    from chess_coach.public_training import import_collection
    from chess_coach.tactical_course_budget import PreviewUnavailable
    from chess_coach.tactical_study_exposure import VERSION as EXPOSURE_VERSION
    from tests.test_public_training import MATE, file_set

    public_dir = tmp_path / "public-fixture"
    public_dir.mkdir()
    white = chess.Board(MATE.replace(" 1 2", " 0 2"))
    black = white.mirror()
    content, manifest, _ = file_set(
        public_dir,
        rows=[
            ("a-other", MATE, "checkmate", ["c5f8"]),
            ("b-white", white.fen(), PUBLIC_MATE, ["c5f8"]),
            ("c-black", black.fen(), PUBLIC_MATE, ["c4f1"]),
        ],
    )
    assert (
        import_collection(db, content, content, manifest, project_root=public_dir)["accepted"] == 3
    )
    collection = db.connection.execute(
        "SELECT id FROM public_collections WHERE version='fixture'"
    ).fetchone()[0]

    # A separate small synthetic DB preserves this pre-enrollment state for
    # the v6 three-provenance workflow below.
    v6_root = tmp_path / "v6-plan-project"
    v6_data = v6_root / ".runtime" / "data"
    v6_data.mkdir(parents=True)
    v6_planning = v6_root / ".runtime" / "planning"
    v6_planning.mkdir(mode=0o700)
    v6_path = v6_data / "plan.sqlite"
    destination = sqlite3.connect(v6_path)
    db.connection.backup(destination)
    destination.close()

    mix_time = now
    while mix_time.date().toordinal() % 3 != 2:
        mix_time -= timedelta(days=1)

    def mixed(cursor=None):
        return daily_plan(
            db,
            subject=SUBJECT,
            corpus_version="fixture",
            as_of=mix_time,
            limit=5,
            scan_limit=20,
            cursor=cursor,
        )

    prior_changes = db.connection.total_changes
    mixed_page = mixed()
    assert db.connection.total_changes == prior_changes
    public_item = next(item for item in mixed_page["items"] if item.get("source_type") == "public")
    assert public_item["source_key"] == "b-white" and public_item["prerequisite_token"]
    assert {item["skill"] for item in mixed_page["items"]} >= {
        "hanging_piece",
        "fork",
        "mate_in_one",
    }

    # An unbound public scan yields to the two owned families, then returns
    # to the saved public coordinate instead of abandoning that source.
    first = daily_plan(
        db,
        subject=SUBJECT,
        corpus_version="fixture",
        as_of=mix_time,
        limit=5,
        scan_limit=1,
    )
    first_state = decode_cursor(db, first["next_cursor"])
    assert first_state["public_after"] == [collection, "a-other"]
    assert first_state["phase"] != "public" and first_state["public_status"] == "deferred"
    observed = list(first["items"])
    for _ in range(12):
        first = daily_plan(
            db,
            subject=SUBJECT,
            corpus_version="fixture",
            as_of=mix_time,
            limit=5,
            scan_limit=1,
            cursor=first["next_cursor"],
        )
        observed.extend(first["items"])
        if any(item.get("source_type") == "public" for item in observed):
            break
        assert first["next_cursor"]
    assert {item["skill"] for item in observed} >= {"hanging_piece", "fork", "mate_in_one"}

    # An interruption at a later public conflict keeps earlier owned items
    # and their seen keys on the same continuation.
    owned_time = now
    while owned_time.date().toordinal() % 3:
        owned_time -= timedelta(days=1)
    original_scheduled = conflict.scheduled_page

    def expire_public(db, prompt, *args, **kwargs):
        if prompt == public_item["prompt_key"]:
            raise PreviewUnavailable()
        return original_scheduled(db, prompt, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(conflict, "scheduled_page", expire_public)
        later = daily_plan(
            db,
            subject=SUBJECT,
            corpus_version="fixture",
            as_of=owned_time,
            limit=5,
            scan_limit=20,
        )
    later_state = decode_cursor(db, later["next_cursor"])
    assert {item["skill"] for item in later["items"]} >= {"hanging_piece", "fork"}
    assert later_state["public_pending"] and all(
        item["prompt_key"] in later_state["seen"] for item in later["items"]
    )
    resumed = daily_plan(
        db,
        subject=SUBJECT,
        corpus_version="fixture",
        as_of=owned_time,
        limit=5,
        scan_limit=20,
        cursor=later["next_cursor"],
    )
    assert any(item.get("source_type") == "public" for item in resumed["items"])

    # Interrupt before a public candidate is bound: the earlier keyset must
    # remain intact so the same candidate can be checked on continuation.
    probe = public_v5_state(db, SUBJECT, "fixture", 5, 20, mix_time)
    probe.update(
        phase="public",
        family_index=3,
        public_status="deferred",
        public_after=[collection, "a-other"],
    )
    probe_cursor = encode_cursor(db, probe)
    with monkeypatch.context() as patch:
        patch.setattr(
            public_candidate, "candidate", lambda *_: (_ for _ in ()).throw(PreviewUnavailable())
        )
        interrupted = mixed(probe_cursor)
    interrupted_state = decode_cursor(db, interrupted["next_cursor"])
    assert interrupted_state["public_after"] == [collection, "a-other"]
    assert interrupted_state["public_pending"] is None
    assert any(
        item.get("source_key") == "b-white" for item in mixed(interrupted["next_cursor"])["items"]
    )

    # A bound candidate remains ahead of later scheduled conflicts.
    with monkeypatch.context() as patch:
        patch.setattr(
            conflict,
            "scheduled_page",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(PreviewUnavailable()),
        )
        interrupted = mixed(probe_cursor)
    bound_state = decode_cursor(db, interrupted["next_cursor"])
    assert bound_state["public_after"] == [collection, "b-white"]
    assert bound_state["public_pending"] and bound_state["scheduled_after"] == 0
    assert any(
        item.get("source_key") == "b-white" for item in mixed(interrupted["next_cursor"])["items"]
    )

    # A completed public proof is still unpublished until the shared check
    # passes. Keep earlier rejected-row progress and retry this exact source.
    with monkeypatch.context() as patch:
        patch.setattr(
            family_mix,
            "_check_completed",
            lambda *_: (_ for _ in ()).throw(PreviewUnavailable()),
        )
        unpublished = mixed()
    unpublished_state = decode_cursor(db, unpublished["next_cursor"])
    assert unpublished_state["public_after"] == [collection, "a-other"]
    assert unpublished_state["public_examined"] == 1
    assert unpublished_state["public_binding"] is None
    assert "_public_before" not in unpublished["scan"]
    next_page = unpublished
    for _ in range(5):
        next_page = mixed(next_page["next_cursor"])
        if any(item.get("source_key") == "b-white" for item in next_page["items"]):
            break
        assert next_page["next_cursor"]
    assert any(item.get("source_key") == "b-white" for item in next_page["items"])

    # The same boundary can occur while resuming an already-bound conflict.
    with monkeypatch.context() as patch:
        patch.setattr(
            family_mix,
            "_check_completed",
            lambda *_: (_ for _ in ()).throw(PreviewUnavailable()),
        )
        unpublished_bound = mixed(interrupted["next_cursor"])
    rewound = decode_cursor(db, unpublished_bound["next_cursor"])
    assert (rewound["public_pending"], rewound["public_after"], rewound["scheduled_after"]) == (
        bound_state["public_pending"],
        bound_state["public_after"],
        bound_state["scheduled_after"],
    )
    assert any(
        item.get("source_key") == "b-white"
        for item in mixed(unpublished_bound["next_cursor"])["items"]
    )

    # Scope exit may happen after the family phase advances; completed owned
    # results survive while the unpublished public item remains retryable.
    from contextlib import contextmanager

    from chess_coach.opening_queue_budget import BrowserBudget

    original_scope = BrowserBudget.scope

    @contextmanager
    def expire_on_exit(self, *, snapshot):
        with original_scope(self, snapshot=snapshot):
            yield
        raise PreviewUnavailable()

    with monkeypatch.context() as patch:
        patch.setattr(BrowserBudget, "scope", expire_on_exit)
        scope_expired = daily_plan(
            db, subject=SUBJECT, corpus_version="fixture", as_of=owned_time, limit=5, scan_limit=20
        )
    scope_state = decode_cursor(db, scope_expired["next_cursor"])
    assert {item["skill"] for item in scope_expired["items"]} >= {"hanging_piece", "fork"}
    assert scope_state["public_after"] == [collection, "a-other"]
    assert scope_state["public_binding"] is None
    next_page = scope_expired
    for _ in range(5):
        next_page = daily_plan(
            db,
            subject=SUBJECT,
            corpus_version="fixture",
            as_of=owned_time,
            limit=5,
            scan_limit=20,
            cursor=next_page["next_cursor"],
        )
        if any(item.get("source_key") == "b-white" for item in next_page["items"]):
            break
        assert next_page["next_cursor"]
    assert any(item.get("source_key") == "b-white" for item in next_page["items"])

    # Public-first rotation can finish a fork just before scope exit and then
    # skip mate fill. That unpublished fork must be retried, not advanced past.
    with monkeypatch.context() as patch:
        patch.setattr(BrowserBudget, "scope", expire_on_exit)
        owned_expired = mixed()
    owned_state = decode_cursor(db, owned_expired["next_cursor"])
    assert {item["skill"] for item in owned_expired["items"]} >= {"mate_in_one", "hanging_piece"}
    assert all(item["skill"] != "fork" for item in owned_expired["items"])
    assert (
        owned_state["phase"] == "fork"
        and owned_expired["continuation_reason"] == "fork_scan_incomplete"
    )
    assert owned_state["public_binding"] and all(
        item["prompt_key"] in owned_state["seen"] for item in owned_expired["items"]
    )
    retried = mixed(owned_expired["next_cursor"])
    assert any(item["skill"] == "fork" for item in retried["items"])
    assert all(item["skill"] not in {"mate_in_one", "hanging_piece"} for item in retried["items"])

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
    page = client.get("/plan", base_url="https://coach.invalid", headers=headers)
    assert page.status_code == 200 and b"Move the piece on b5" in page.data
    form = {
        "csrf": token(page, "csrf"),
        "source_type": "public",
        "version": "fixture",
        "key": public_item["source_key"],
        "training": "1",
        "prerequisite_token": public_item["prerequisite_token"],
    }
    artifact = "a" * 64
    intent = {
        "course_sha256": artifact,
        "chapters": ["pending"],
        "tactical_delivery": {
            "version": EXPOSURE_VERSION,
            "owner": learner_key(SUBJECT),
            "chapters": {
                "0": {
                    "positions": [digest(public_item["prompt_key"])],
                    "pending_at": datetime.now(UTC).isoformat(),
                    "verified_at": None,
                }
            },
        },
    }
    intent_path = planning / f"tactical-study-{artifact}-intent.json"
    fd = os.open(intent_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as stream:
        json.dump(intent, stream)
    before = db.connection.execute("SELECT count(*) FROM unified_training_enrollments").fetchone()[
        0
    ]
    rejected = client.post(
        "/unified/start",
        base_url="https://coach.invalid",
        headers=headers | {"Origin": "https://coach.invalid"},
        data=form,
    )
    assert rejected.status_code == 400
    assert (
        db.connection.execute("SELECT count(*) FROM unified_training_enrollments").fetchone()[0]
        == before
    )

    black_key = " ".join(black.fen(en_passant="fen").split()[:4])
    db.connection.execute(
        """INSERT INTO tactical_exposures(subject,prompt_key,artifact_hash,chapter_index,
        chapter_hash,kind,occurred_at) VALUES(?,?,?,?,?,?,?)""",
        (
            SUBJECT,
            black_key,
            "b" * 64,
            0,
            "c" * 64,
            "historical_unknown",
            datetime.now(UTC).isoformat(),
        ),
    )
    db.connection.commit()
    replacement = next(item for item in mixed()["items"] if item.get("source_type") == "public")
    assert replacement["source_key"] == "c-black" and "unknown" in replacement["reason"]
    form.update(key=replacement["source_key"], prerequisite_token=replacement["prerequisite_token"])
    # Source-revision changes invalidate the offer even when its signed token is authentic.
    db.connection.execute("UPDATE curriculum_source_revision SET revision=revision+1 WHERE id=1")
    db.connection.commit()
    assert (
        client.post(
            "/unified/start",
            base_url="https://coach.invalid",
            headers=headers | {"Origin": "https://coach.invalid"},
            data=form,
        ).status_code
        == 400
    )
    replacement = next(item for item in mixed()["items"] if item.get("source_type") == "public")
    form["prerequisite_token"] = replacement["prerequisite_token"]
    started = client.post(
        "/unified/start",
        base_url="https://coach.invalid",
        headers=headers | {"Origin": "https://coach.invalid"},
        data=form,
    )
    assert started.status_code == 303
    public_attempt = started.location.rstrip("/").rsplit("/", 1)[-1]
    result = submit(db, public_attempt, SUBJECT, event_id="answer", move="c4c1")
    assert result["learning"]["outcome"] == "success"
    public_due = daily_plan(
        db, subject=SUBJECT, corpus_version="fixture", as_of=now + timedelta(days=2)
    )
    assert any(item.get("item_id") == result["learning"]["item_id"] for item in public_due["items"])

    # The other owned skill still has a real qualified enrollment, rather
    # than being displaced by the single public-mate opportunity.
    from chess_coach.unified_sessions import start
    from chess_coach.unified_sources import resolve_source

    capture_item = next(item for item in mixed_page["items"] if item["skill"] == "hanging_piece")
    capture_source = resolve_source(
        db, "own-game", capture_item["source_version"], capture_item["source_key"], subject=SUBJECT
    )
    start(
        db,
        attempt_id="mixed-capture",
        subject=SUBJECT,
        source_type="own-game",
        version=capture_item["source_version"],
        key=capture_item["source_key"],
        training=True,
    )
    submit(
        db, "mixed-capture", SUBJECT, event_id="answer", move=capture_source["lines"][0].split()[0]
    )
    assert process(db, SUBJECT)["outcomes"] == {"correct": 1}
    capture_learning = show(db, "mixed-capture", SUBJECT)["learning"]
    assert capture_learning["outcome"] == "success"

    posted = client.post(
        "/unified/start",
        base_url="https://coach.invalid",
        headers=headers | {"Origin": "https://coach.invalid"},
        data={
            "csrf": token(page, "csrf"),
            "source_type": "own-game",
            "version": MISS_VERSION,
            "key": fork["source_key"],
            "training": "1",
        },
    )
    assert posted.status_code == 303
    attempt = posted.location.rstrip("/").rsplit("/", 1)[-1]
    submit(db, attempt, SUBJECT, event_id="answer", move="b5d6")
    assert process(db, SUBJECT)["outcomes"] == {"correct": 1}
    learning = show(db, attempt, SUBJECT)["learning"]
    assert learning["rating"] == "good" and learning["evidence_id"] is not None
    due = daily_plan(db, subject=SUBJECT, corpus_version="fixture", as_of=now + timedelta(days=2))
    assert any(item.get("item_id") == learning["item_id"] for item in due["items"])
    review_evidence(db, fork["source_evidence_id"], decision="reject", actor="fixture")
    stale = client.post(
        "/unified/start",
        base_url="https://coach.invalid",
        headers=headers | {"Origin": "https://coach.invalid"},
        data={
            "csrf": token(page, "csrf"),
            "source_type": "own-game",
            "version": MISS_VERSION,
            "key": fork["source_key"],
            "training": "1",
        },
    )
    assert stale.status_code == 400
    db.close()
    monkeypatch.setattr(curriculum, "new_state", v6_new_state)
    _v6_source_mix(v6_path, v6_planning, now, monkeypatch)


def _v6_source_mix(path, planning, now, monkeypatch):
    import os
    from datetime import UTC, datetime, timedelta

    import chess

    import chess_coach.curriculum_canonical_launch as canonical_launch
    import chess_coach.curriculum_canonical_scan as canonical_scan
    import chess_coach.curriculum_capture_conflict as conflict
    import chess_coach.curriculum_family_mix as family_mix
    from chess_coach.curriculum import daily_plan
    from chess_coach.curriculum_cursor_codec import decode_cursor
    from chess_coach.db import Database
    from chess_coach.deep_selection_source import learner_key
    from chess_coach.fact_fingerprint import digest
    from chess_coach.public_training import import_collection
    from chess_coach.tactical_course_budget import PreviewUnavailable
    from chess_coach.tactical_study_exposure import VERSION as EXPOSURE_VERSION
    from chess_coach.unified_sessions import start
    from chess_coach.unified_sources import resolve_source
    from tests.test_objective_promotion import CONTENT, MANIFEST, ROOT, VERSION

    db = Database(path)
    assert import_collection(db, CONTENT, CONTENT, MANIFEST, project_root=ROOT)["accepted"] == 8
    start(
        db,
        attempt_id="prior-promotion",
        subject=SUBJECT,
        source_type="public",
        version=VERSION,
        key="direct-white",
        training=True,
    )
    submit(db, "prior-promotion", SUBJECT, event_id="answer", move="a7a8n")
    assert process(db, SUBJECT)["outcomes"] == {"correct": 1}
    assert show(db, "prior-promotion", SUBJECT)["learning"]["outcome"] == "success"

    as_of = now
    while as_of.date().toordinal() % 4:
        as_of -= timedelta(days=1)

    def plan(limit=10):
        page = daily_plan(
            db, subject=SUBJECT, corpus_version="fixture", as_of=as_of, limit=limit, scan_limit=200
        )
        items = list(page["items"])
        for _ in range(12):
            if not page["next_cursor"]:
                break
            page = daily_plan(
                db,
                subject=SUBJECT,
                corpus_version="fixture",
                as_of=as_of,
                limit=limit,
                scan_limit=200,
                cursor=page["next_cursor"],
            )
            items.extend(page["items"])
        return page, items

    small, small_items = plan(3)
    assert small["limit_reached"] and len(small_items) == 3
    assert sum(item["source_type"] == "own-game" for item in small_items) == 1
    assert {item["source_version"] for item in small_items if item["source_type"] == "public"} == {
        "fixture",
        VERSION,
    }
    full, items = plan(4)
    assert full["limit_reached"] and len(items) == 4
    assert {item["skill"] for item in items} >= {
        "hanging_piece",
        "fork",
        "mate_in_one",
        "promotion",
    }
    assert full["canonical_context"] == "continuation"
    rotated = daily_plan(
        db,
        subject=SUBJECT,
        corpus_version="fixture",
        as_of=as_of - timedelta(days=3),
        limit=3,
        scan_limit=200,
    )
    assert sum(item["source_type"] == "own-game" for item in rotated["items"]) == 1
    assert any(item["skill"] == "fork" for item in rotated["items"])
    assert {
        item["source_version"] for item in rotated["items"] if item["source_type"] == "public"
    } == {"fixture", VERSION}

    # Expiry immediately after a canonical proof must not discard the item
    # while retaining the advanced task coordinate.
    original_issue = canonical_launch.issue
    original_completed = family_mix._check_completed
    issued = [False]

    def mark_issued(*args):
        token = original_issue(*args)
        issued[0] = True
        return token

    def expire_after_canonical(reason, budget, check):
        if issued[0]:
            raise PreviewUnavailable()
        return original_completed(reason, budget, check)

    with monkeypatch.context() as patch:
        patch.setattr(canonical_launch, "issue", mark_issued)
        patch.setattr(family_mix, "_check_completed", expire_after_canonical)
        unpublished = daily_plan(
            db, subject=SUBJECT, corpus_version="fixture", as_of=as_of, limit=5, scan_limit=200
        )
    unpublished_state = decode_cursor(db, unpublished["next_cursor"])
    assert unpublished_state["canonical_after"] == 0
    assert unpublished_state["canonical_binding"] is None
    assert {item["skill"] for item in unpublished["items"]} >= {"hanging_piece", "mate_in_one"}
    for _ in range(8):
        unpublished = daily_plan(
            db,
            subject=SUBJECT,
            corpus_version="fixture",
            as_of=as_of,
            limit=5,
            scan_limit=200,
            cursor=unpublished["next_cursor"],
        )
        if any(item.get("source_version") == VERSION for item in unpublished["items"]):
            break
        assert unpublished["next_cursor"]
    assert any(item.get("source_version") == VERSION for item in unpublished["items"])

    # The enclosing scope can expire after that completed phase has advanced.
    from contextlib import contextmanager

    from chess_coach.opening_queue_budget import BrowserBudget

    original_scope = BrowserBudget.scope

    @contextmanager
    def expire_on_exit(self, *, snapshot):
        with original_scope(self, snapshot=snapshot):
            yield
        raise PreviewUnavailable()

    with monkeypatch.context() as patch:
        patch.setattr(BrowserBudget, "scope", expire_on_exit)
        scope_expired = daily_plan(
            db, subject=SUBJECT, corpus_version="fixture", as_of=as_of, limit=3, scan_limit=200
        )
    scope_state = decode_cursor(db, scope_expired["next_cursor"])
    assert scope_state["canonical_after"] == 0 and scope_state["canonical_binding"] is None
    assert {item["skill"] for item in scope_expired["items"]} >= {"hanging_piece", "mate_in_one"}
    for _ in range(8):
        scope_expired = daily_plan(
            db,
            subject=SUBJECT,
            corpus_version="fixture",
            as_of=as_of,
            limit=3,
            scan_limit=200,
            cursor=scope_expired["next_cursor"],
        )
        if any(item.get("source_version") == VERSION for item in scope_expired["items"]):
            break
        assert scope_expired["next_cursor"]
    assert any(item.get("source_version") == VERSION for item in scope_expired["items"])

    # An unbound canonical deadline yields to other categories and is then
    # retried from the signed canonical state, rather than labeled absent.
    canonical_first = now
    while canonical_first.date().toordinal() % 4 != 3:
        canonical_first -= timedelta(days=1)
    with monkeypatch.context() as patch:
        patch.setattr(
            canonical_scan, "context", lambda *_: (_ for _ in ()).throw(PreviewUnavailable())
        )
        deferred = daily_plan(
            db,
            subject=SUBJECT,
            corpus_version="fixture",
            as_of=canonical_first,
            limit=5,
            scan_limit=200,
        )
    deferred_state = decode_cursor(db, deferred["next_cursor"])
    assert deferred_state["canonical_status"] == "deferred"
    observed = list(deferred["items"])
    for _ in range(8):
        deferred = daily_plan(
            db,
            subject=SUBJECT,
            corpus_version="fixture",
            as_of=canonical_first,
            limit=5,
            scan_limit=200,
            cursor=deferred["next_cursor"],
        )
        observed.extend(deferred["items"])
        if any(item.get("source_version") == VERSION for item in observed):
            break
        assert deferred["next_cursor"]
    assert any(item.get("source_version") == VERSION for item in observed)
    assert any(item["source_type"] == "own-game" for item in observed)

    # Earlier public/owned items survive a later interrupted bound canonical
    # conflict; the same canonical source must resume before later work.
    canonical_item = next(item for item in items if item.get("source_version") == VERSION)
    original_scheduled = conflict.scheduled_page

    def interrupt_canonical(db, prompt, *args, **kwargs):
        if prompt == canonical_item["prompt_key"]:
            raise PreviewUnavailable()
        return original_scheduled(db, prompt, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(conflict, "scheduled_page", interrupt_canonical)
        interrupted = daily_plan(
            db, subject=SUBJECT, corpus_version="fixture", as_of=as_of, limit=5, scan_limit=200
        )
    interrupted_state = decode_cursor(db, interrupted["next_cursor"])
    assert interrupted_state["canonical_pending"]
    assert {item["skill"] for item in interrupted["items"]} >= {"hanging_piece", "mate_in_one"}
    assert all(item["prompt_key"] in interrupted_state["seen"] for item in interrupted["items"])
    resumed = daily_plan(
        db,
        subject=SUBJECT,
        corpus_version="fixture",
        as_of=as_of,
        limit=5,
        scan_limit=200,
        cursor=interrupted["next_cursor"],
    )
    assert any(item.get("source_version") == VERSION for item in resumed["items"])

    # Due reviews remain ahead of every new provenance category.
    row = db.connection.execute(
        "SELECT id,due FROM training_items WHERE source_type='puzzle' ORDER BY id LIMIT 1"
    ).fetchone()
    db.connection.execute(
        "UPDATE training_items SET due='2000-01-01T00:00:00+00:00' WHERE id=?", (row["id"],)
    )
    db.connection.commit()
    _, due = plan(2)
    assert due[0]["item_id"] == row["id"] and due[0]["kind"] == "due"
    due_full = daily_plan(
        db, subject=SUBJECT, corpus_version="fixture", as_of=as_of, limit=1, scan_limit=200
    )
    assert len(due_full["items"]) == 1 and due_full["items"][0]["kind"] == "due"
    assert due_full["limit_reached"]
    db.connection.execute("UPDATE training_items SET due=? WHERE id=?", (row["due"], row["id"]))
    db.connection.commit()

    # An offer cannot outlive a change in its signed source policy.
    import chess_coach.unified_canonical_forced_learning as forced_policy

    _, items = plan()
    canonical_item = next(item for item in items if item.get("source_version") == VERSION)
    with monkeypatch.context() as patch:
        patch.setattr(forced_policy, "POLICY", forced_policy.POLICY + "-changed")
        with pytest.raises(ValueError, match="canonical plan changed"):
            start(
                db,
                attempt_id="changed-policy",
                subject=SUBJECT,
                source_type="public",
                version=VERSION,
                key=canonical_item["source_key"],
                training=True,
                diagnostic=canonical_item["prerequisite_token"],
            )

    # A pending Study send created after the offer is checked in the start
    # transaction even when it has not changed the database revision.
    _, items = plan()
    canonical_item = next(item for item in items if item.get("source_version") == VERSION)
    assert canonical_item["source_key"] == "direct-black"
    artifact = "d" * 64
    intent = {
        "course_sha256": artifact,
        "chapters": ["pending"],
        "tactical_delivery": {
            "version": EXPOSURE_VERSION,
            "owner": learner_key(SUBJECT),
            "chapters": {
                "0": {
                    "positions": [digest(canonical_item["prompt_key"])],
                    "pending_at": datetime.now(UTC).isoformat(),
                    "verified_at": None,
                }
            },
        },
    }
    fd = os.open(
        planning / f"tactical-study-{artifact}-intent.json",
        os.O_WRONLY | os.O_CREAT | os.O_EXCL,
        0o600,
    )
    with os.fdopen(fd, "w") as stream:
        json.dump(intent, stream)
    with pytest.raises(ValueError, match="exposure"):
        start(
            db,
            attempt_id="late-canonical",
            subject=SUBJECT,
            source_type="public",
            version=VERSION,
            key=canonical_item["source_key"],
            training=True,
            diagnostic=canonical_item["prerequisite_token"],
        )

    # Replan before each actual enrollment because an enrollment legitimately
    # advances the plan revision. The fresh offers bind the same real owner.
    item_ids = []
    for skill in ("hanging_piece", "fork", "mate_in_one", "promotion"):
        _, items = plan()
        item = next(item for item in items if item["kind"] == "new" and item["skill"] == skill)
        source = resolve_source(
            db, item["source_type"], item["source_version"], item["source_key"], subject=SUBJECT
        )
        attempt = "v6-" + skill
        start(
            db,
            attempt_id=attempt,
            subject=SUBJECT,
            source_type=item["source_type"],
            version=item["source_version"],
            key=item["source_key"],
            training=True,
            diagnostic=item.get("prerequisite_token"),
        )
        first = source["lines"][0].split()[0]
        result = submit(db, attempt, SUBJECT, event_id="root", move=first)
        if result["status"] == "needs_verification":
            assert process(db, SUBJECT)["outcomes"] == {"correct": 1}
            state = show(db, attempt, SUBJECT)
            if state.get("promotion_continuation"):
                board = chess.Board(state["fen"])
                final = next(move.uci() for move in board.legal_moves if move.promotion)
                submit(db, attempt, SUBJECT, event_id="final", move=final)
        learning = show(db, attempt, SUBJECT)["learning"]
        assert learning["state"] == "completed" and learning["outcome"] == "success"
        item_ids.append(learning["item_id"])

    due_page = daily_plan(
        db,
        subject=SUBJECT,
        corpus_version="fixture",
        as_of=datetime.now(UTC) + timedelta(days=3),
        limit=20,
    )
    assert set(item_ids) <= {item.get("item_id") for item in due_page["items"]}
    for source in ("unified_canonical_promotion", "unified_canonical_forced_promotion"):
        due_query = """EXPLAIN QUERY PLAN SELECT id FROM training_items
            INDEXED BY idx_curriculum_source_due
            WHERE source_type=? AND skill='promotion' AND operation='execute'
            AND lower(due) != 'now' AND julianday(due) <= julianday(?)
            ORDER BY julianday(due),id LIMIT ?"""
        scheduled_query = """EXPLAIN QUERY PLAN SELECT id FROM training_items
            INDEXED BY idx_curriculum_source_scheduled WHERE id>? AND source_type=?
            AND skill='promotion' AND operation='execute' ORDER BY id LIMIT ?"""
        assert any(
            "idx_curriculum_source_due" in row[3]
            for row in db.connection.execute(due_query, (source, datetime.now(UTC).isoformat(), 4))
        )
        assert any(
            "idx_curriculum_source_scheduled" in row[3]
            for row in db.connection.execute(scheduled_query, (0, source, 4))
        )
    db.close()

    # First-recorded is established only after a bounded all-status activity
    # check; an assisted attempt is not an unassisted result or a miss.
    from chess_coach.unified_session_events import hint

    cold = Database(path.parent / "cold.sqlite")
    cold.initialize()
    assert import_collection(cold, CONTENT, CONTENT, MANIFEST, project_root=ROOT)["accepted"] == 8
    # A promotion diagnostic is not, by itself, a reason to offer generic mate practice.
    corpus = cold.connection.execute(
        "INSERT INTO puzzle_corpora(version,source,checksum,state) "
        "VALUES('fixture','fixture','checksum','staging')"
    ).lastrowid
    cold.connection.execute(
        """INSERT INTO puzzles(puzzle_id,corpus_id,fen,source,solution,rating,
        rating_deviation,themes_json,objective)
        VALUES('generic',?,?,'','g8h8 c5f8',500,80,'[]','execute')""",
        (corpus, "6k1/8/6K1/2Q5/8/8/8/8 b - - 0 1"),
    )
    cold.connection.execute("UPDATE puzzle_corpora SET state='ready' WHERE id=?", (corpus,))
    cold.connection.commit()
    from chess_coach.curriculum_query import corpus_status

    assert corpus_status(cold, "fixture")[0] == "available"
    first = daily_plan(cold, subject="cold_synthetic", corpus_version="fixture")
    assert first["canonical_context"] == "first_recorded"
    assert first["public_status"] != "offered"
    assert any(item["skill"] == "promotion" for item in first["items"])
    assert all(item["skill"] != "mate_in_one" for item in first["items"])
    # Unrelated recorded public work does not erase a first opportunity in
    # this exact canonical catalog or imply a general beginner state.
    from chess_coach.public_mate_contract import OBJECTIVE as PUBLIC_MATE
    from tests.test_public_training import MATE, file_set

    unrelated_dir = path.parent.parent.parent / "unrelated-public"
    unrelated_dir.mkdir()
    public_board = chess.Board(MATE.replace(" 1 2", " 0 2"))
    content, manifest, _ = file_set(
        unrelated_dir, rows=[("unrelated", public_board.fen(), PUBLIC_MATE, ["c5f8"])]
    )
    assert (
        import_collection(cold, content, content, manifest, project_root=unrelated_dir)["accepted"]
        == 1
    )
    start(
        cold,
        attempt_id="unrelated",
        subject="cold_synthetic",
        source_type="public",
        version="fixture",
        key="unrelated",
        training=True,
    )
    unrelated = submit(cold, "unrelated", "cold_synthetic", event_id="answer", move="c5f8")
    assert unrelated["learning"]["outcome"] == "success"
    # Many unrelated attempts must not exhaust the exact-catalog activity bound.
    for number in range(26):
        start(
            cold,
            attempt_id=f"unrelated-{number}",
            subject="cold_synthetic",
            source_type="public",
            version="fixture",
            key="unrelated",
        )
    cold_page = daily_plan(cold, subject="cold_synthetic", corpus_version="fixture")
    cold_item = next(item for item in cold_page["items"] if item["skill"] == "promotion")
    assert cold_page["canonical_context"] == "first_recorded"
    assert (
        "first recorded practice" in cold_item["reason"]
        and "Earlier practice isn't known" in cold_item["reason"]
    )
    start(
        cold,
        attempt_id="assisted",
        subject="Cold_Synthetic",
        source_type="public",
        version=VERSION,
        key=cold_item["source_key"],
        training=True,
        diagnostic=cold_item["prerequisite_token"],
    )
    hint(cold, "assisted", "Cold_Synthetic", event_id="hint")
    pending_page = daily_plan(cold, subject="cold_synthetic", corpus_version="fixture")
    assert pending_page["canonical_context"] != "first_recorded"
    submit(cold, "assisted", "Cold_Synthetic", event_id="answer", move="a7a8n")
    assert process(cold, "Cold_Synthetic")["outcomes"] == {"correct": 1}
    assisted = show(cold, "assisted", "Cold_Synthetic")["learning"]
    assert assisted["assistance"] == "assisted" and assisted["evidence_id"] is None
    assert assisted["rating"] is None
    assert (
        daily_plan(cold, subject="cold_synthetic", corpus_version="fixture")["canonical_context"]
        != "first_recorded"
    )
    # This is the existing explicit same-item retry route, not an inferred miss.
    start(
        cold,
        attempt_id="retry",
        subject="Cold_Synthetic",
        source_type="public",
        version=VERSION,
        key=cold_item["source_key"],
        training=True,
        item_id=assisted["item_id"],
    )
    submit(cold, "retry", "Cold_Synthetic", event_id="answer", move="a7a8n")
    assert process(cold, "Cold_Synthetic")["outcomes"] == {"correct": 1}
    assert show(cold, "retry", "Cold_Synthetic")["learning"]["outcome"] == "success"
    assert (
        daily_plan(cold, subject="cold_synthetic", corpus_version="fixture")["canonical_context"]
        == "continuation"
    )
    cold.close()
