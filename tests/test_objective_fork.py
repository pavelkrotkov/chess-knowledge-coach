"""Owned fork objectives verify equivalent moves without inventing game results."""

import json

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
    assert page.status_code == 200 and "b5c7" not in page.get_data(as_text=True)
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
    assert {
        table: db.connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        for table in before
    } == before


@pytest.mark.parametrize("mode", ["correct", "assisted", "unresolved"])
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
    db.connection.execute("UPDATE puzzle_corpora SET state='ready' WHERE id=?", (corpus,))
    db.connection.commit()
    assert certificate(db, "fork-fixture", "synthetic-key")["proof"]["move"] == "b5c7"
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
    page = client.get(
        f"/evidence/{evidence}/related-forks/find-verified", base_url=base, headers=headers
    )
    assert page.status_code == 200 and b"Start fork assessment" in page.data
    assert b"synthetic-key" not in page.data and b"b5c7" not in page.data
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
    page = client.get(posted.location, base_url=base, headers=headers)
    assert page.status_code == 200 and b"b5c7" not in page.data
    attempt = token(page, "attempt")
    db = Database(path)
    if mode == "assisted":
        from chess_coach.unified_session_events import reveal

        reveal(db, attempt, SUBJECT, event_id="reveal")
    move = "b5a3" if mode == "unresolved" else "b5c7"
    result = submit(db, attempt, SUBJECT, event_id="answer", move=move)
    assert result["status"] == "needs_verification"
    expected = "unresolved" if mode == "unresolved" else "correct"
    assert process(db, SUBJECT)["outcomes"] == {expected: 1}
    assert inspect(db, SUBJECT, attempt, "answer")["status"] == expected
    state = show(db, attempt, SUBJECT)
    assert state["verification"]["status"] == expected
    output = json.loads(
        db.connection.execute("SELECT result_json FROM objective_results").fetchone()[0]
    )
    assert not output["learning_eligible"]
    assert output["assistance"] == ("revealed" if mode == "assisted" else "unassisted")
    review_evidence(db, evidence, decision="reject", actor="fixture_reviewer")
    with pytest.raises(ValueError):
        show(db, attempt, SUBJECT)
    db.close()
