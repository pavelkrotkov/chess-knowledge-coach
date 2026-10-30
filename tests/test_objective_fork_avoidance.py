"""Created-fork owned decisions receive independent bounded verdicts."""

import json

import pytest

from chess_coach.objective_fork_avoidance_contract import OBJECTIVE, VERSION
from chess_coach.objective_fork_avoidance_list import candidates
from chess_coach.objective_status import inspect
from chess_coach.objective_worker import process
from chess_coach.unified_session_events import show, submit
from chess_coach.unified_sessions import start
from tests.related_protection_support import learning_counts
from tests.test_fork_defense import mirror
from tests.test_fork_defense_pipeline import LEARNER
from tests.test_related_fork_avoidance import created_fixture


def begin(db, evidence, subject=LEARNER):
    return start(
        db,
        attempt_id="avoid-created",
        subject=subject,
        source_type="own-game",
        version=VERSION,
        key=str(evidence),
    )


@pytest.mark.parametrize("black", [False, True])
def test_created_source_queues_fresh_alternative_without_learning_writes(
    tmp_path, monkeypatch, black
):
    db, evidence = created_fixture(tmp_path / "avoid.sqlite", monkeypatch, black)
    before = learning_counts(db)
    assert candidates(db, LEARNER)["candidates"] == [{"key": str(evidence)}]
    state = begin(db, evidence)
    good = mirror("b1b3") if black else "b1b3"
    assert state["objective"] == "avoid_created_knight_fork"
    assert good not in json.dumps(state)
    event = submit(db, "avoid-created", LEARNER, event_id="answer", move=good)
    assert event["feedback"] == "needs_verification"
    report = process(db, LEARNER)
    assert report["fork_defense_work_limit"] == {"requests": 1, "fork_proof_units_cap": 112}
    result = inspect(db, LEARNER, "avoid-created", "answer")
    assert result["status"] == "correct"
    stored = json.loads(
        db.connection.execute("SELECT result_json FROM objective_results").fetchone()[0]
    )
    assert stored["objective_version"] == OBJECTIVE
    assert stored["verifier"] == "fork-avoidance-verifier-v1"
    assert stored["limits"]["hypothetical_checks_per_source_refresh"] == 2
    assert stored["limits"]["worker_hypothetical_checks_limit"] == 4
    assert stored["limits"]["hypothetical_legal_list_admission_limit"] == 128
    assert "source_anchor_moves_each" not in stored["limits"]
    assert show(db, "avoid-created", LEARNER)["verification"]["status"] == "correct"
    assert submit(db, "avoid-created", LEARNER, event_id="answer", move=good) == event
    assert learning_counts(db) == before
    db.close()


def test_budget_reserves_before_both_source_checks_and_answer(tmp_path, monkeypatch):
    from chess_coach import objective_fork_avoidance_source as source
    from chess_coach import objective_fork_defense_assess as assess

    db, evidence = created_fixture(tmp_path / "budget.sqlite", monkeypatch)
    begin(db, evidence)
    submit(db, "avoid-created", LEARNER, event_id="answer", move="b1b3")
    seen = []
    source_reserve, answer_reserve = source.reserve, assess.reserve
    monkeypatch.setattr(source, "reserve", lambda n: (seen.append(n), source_reserve(n))[1])
    monkeypatch.setattr(assess, "reserve", lambda n: (seen.append(n), answer_reserve(n))[1])
    assert process(db, LEARNER)["outcomes"] == {"correct": 1}
    assert seen == [48, 16, 48]
    db.close()


def test_wrong_owner_origin_and_stale_review_fail_closed(tmp_path, monkeypatch):
    from chess_coach.objective_fork_defense_contract import VERSION as ANCHORED

    db, evidence = created_fixture(tmp_path / "stale.sqlite", monkeypatch)
    with pytest.raises(ValueError):
        begin(db, evidence, subject="foreign")
    with pytest.raises(ValueError):
        start(
            db,
            attempt_id="wrong",
            subject=LEARNER,
            source_type="own-game",
            version=ANCHORED,
            key=str(evidence),
        )
    begin(db, evidence)
    submit(db, "avoid-created", LEARNER, event_id="answer", move="b1b3")
    from chess_coach.evidence_review import review_evidence

    review_evidence(db, evidence, decision="reject", actor="fixture_reviewer")
    assert process(db, LEARNER)["outcomes"] == {"unresolved": 1}
    assert inspect(db, LEARNER, "avoid-created", "answer")["reason"] == "source_unavailable"
    db.close()


def test_review_change_between_compute_and_publication_is_unresolved(tmp_path, monkeypatch):
    from chess_coach.evidence_review import review_evidence
    from chess_coach.objective_verify import compute

    db, evidence = created_fixture(tmp_path / "race.sqlite", monkeypatch)
    begin(db, evidence)
    submit(db, "avoid-created", LEARNER, event_id="answer", move="b1b3")

    def revoke_before_publication(db, request, clock, *, seconds):
        result = compute(db, request, clock, seconds=seconds)
        assert result["status"] == "correct"
        review_evidence(db, evidence, decision="reject", actor="fixture_reviewer")
        return result

    assert process(db, LEARNER, verifier=revoke_before_publication)["outcomes"] == {"unresolved": 1}
    stored = json.loads(
        db.connection.execute("SELECT result_json FROM objective_results").fetchone()[0]
    )
    assert stored["reason"] == "source_unavailable"
    db.close()


def test_existing_result_does_not_bypass_revocation(tmp_path, monkeypatch):
    from chess_coach.evidence_review import review_evidence
    from chess_coach.objective_publication import publish

    db, evidence = created_fixture(tmp_path / "existing.sqlite", monkeypatch)
    begin(db, evidence)
    submit(db, "avoid-created", LEARNER, event_id="answer", move="b1b3")
    assert process(db, LEARNER)["outcomes"] == {"correct": 1}
    request = db.connection.execute("SELECT * FROM objective_requests").fetchone()
    original = db.connection.execute("SELECT result_json FROM objective_results").fetchone()[0]
    review_evidence(db, evidence, decision="reject", actor="fixture_reviewer")
    assert publish(db, request, json.loads(original))["reason"] == "source_unavailable"
    assert (
        db.connection.execute("SELECT result_json FROM objective_results").fetchone()[0] == original
    )
    db.close()


def test_bad_move_and_exhausted_budget_remain_unresolved(tmp_path, monkeypatch):
    from chess_coach import objective_fork_defense_budget as budget

    db, evidence = created_fixture(tmp_path / "unknown.sqlite", monkeypatch)
    begin(db, evidence)
    submit(db, "avoid-created", LEARNER, event_id="answer", move="b1a1")
    assert process(db, LEARNER)["outcomes"] == {"unresolved": 1}
    assert inspect(db, LEARNER, "avoid-created", "answer")["status"] == "unresolved"
    db.close()

    db, evidence = created_fixture(tmp_path / "exhausted.sqlite", monkeypatch)
    begin(db, evidence)
    submit(db, "avoid-created", LEARNER, event_id="answer", move="b1b3")
    monkeypatch.setattr(budget, "LIMIT", 15)
    assert process(db, LEARNER)["outcomes"] == {"unresolved": 1}
    stored = json.loads(
        db.connection.execute("SELECT result_json FROM objective_results").fetchone()[0]
    )
    assert stored["reason"] == "fork_proof_budget_exhausted"
    db.close()


def test_uncertain_other_fork_and_wrong_origin_do_not_pass():
    import chess

    from chess_coach.objective_fork_avoidance_judge import verify
    from chess_coach.objective_fork_defense_budget import scope

    board = chess.Board("7k/6p1/8/8/1n6/8/1R5P/R3K3 w - - 0 1")
    move = board.parse_uci("a1b1")
    with scope():
        result = verify(
            board,
            move,
            {"learner_color": "white"},
            [],
            lambda: 0,
            0,
            1,
            {},
            {"threat_origin": "created_by_played_move"},
        )
    assert result["status"] == "unresolved"
    assert result["reason"] == "fork_or_consequence_unresolved"
    with scope():
        result = verify(
            board,
            move,
            {"learner_color": "white"},
            [],
            lambda: 0,
            0,
            1,
            {},
            {"threat_origin": "positional_before_played"},
        )
    assert result["reason"] == "objective_binding_unavailable"


def test_concurrent_workers_publish_once(tmp_path, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    from chess_coach.db import Database
    from chess_coach.objective_verify import compute

    path = tmp_path / "concurrent.sqlite"
    db, evidence = created_fixture(path, monkeypatch)
    begin(db, evidence)
    submit(db, "avoid-created", LEARNER, event_id="answer", move="b1b3")
    db.close()
    barrier = Barrier(2)

    def simultaneous(db, request, clock, *, seconds):
        barrier.wait(timeout=5)
        return compute(db, request, clock, seconds=seconds)

    def work(_):
        db = Database(path)
        try:
            return process(db, LEARNER, verifier=simultaneous)
        finally:
            db.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(work, range(2)))
    assert all(result["outcomes"] == {"correct": 1} for result in results)
    db = Database(path)
    assert db.connection.execute("SELECT COUNT(*) FROM objective_results").fetchone()[0] == 1
    db.close()


def test_created_source_identity_rejects_type_version_or_goal_collisions():
    from chess_coach.objective_fork_avoidance_contract import GOAL, is_source

    row = {"source_type": "own-game", "source_version": VERSION, "objective": GOAL}
    assert is_source(row)
    assert not is_source(row | {"source_type": "public"})
    assert not is_source(row | {"source_version": "fork-defense-own-v1"})
    assert not is_source(row | {"objective": "execute_named_fork"})
