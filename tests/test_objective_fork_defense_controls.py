"""Proof-budget, unsupported-move and currentness controls for fork defense."""

import json

import pytest

from chess_coach.evidence_review import review_evidence
from chess_coach.objective_fork_defense_contract import VERSION
from chess_coach.objective_status import inspect
from chess_coach.objective_worker import process
from chess_coach.unified_session_events import submit
from chess_coach.unified_sessions import start
from tests.test_fork_defense_pipeline import LEARNER
from tests.test_objective_fork_defense import begin, fixture
from tests.test_related_fork_avoidance import created_fixture


def test_worker_reserves_two_source_checks_and_one_answer_scan(tmp_path, monkeypatch):
    from chess_coach import objective_fork_defense_assess as judge
    from chess_coach import objective_fork_defense_source as source

    db, evidence = fixture(tmp_path / "budget.sqlite", monkeypatch)
    begin(db, evidence)
    submit(db, "fork-defense", LEARNER, event_id="answer", move="a1b1")
    reservations, checks, scans = [], [], []
    source_reserve, answer_reserve, current, scan = (
        source.reserve,
        judge.reserve,
        source.current,
        judge.scan,
    )

    def reserve_source(units):
        reservations.append(units)
        return source_reserve(units)

    def reserve_answer(units):
        reservations.append(units)
        return answer_reserve(units)

    def count_current(*args):
        checks.append(1)
        return current(*args)

    def count_scan(*args):
        scans.append(1)
        return scan(*args)

    monkeypatch.setattr(source, "reserve", reserve_source)
    monkeypatch.setattr(judge, "reserve", reserve_answer)
    monkeypatch.setattr(source, "current", count_current)
    monkeypatch.setattr(judge, "scan", count_scan)
    report = process(db, LEARNER)
    assert report["outcomes"] == {"correct": 1}
    assert report["fork_defense_work_limit"] == {"requests": 1, "fork_proof_units_cap": 112}
    assert reservations == [48, 16, 48]
    assert len(checks) == 2 and len(scans) == 1
    payload = json.loads(
        db.connection.execute("SELECT result_json FROM objective_results").fetchone()[0]
    )
    assert payload["limits"]["worker_fork_proof_units"] == 112
    assert payload["limits"]["answer_scan_units"] == 16
    db.close()


def test_exhausted_budget_is_unresolved_without_answer_scan(tmp_path, monkeypatch):
    from chess_coach import objective_fork_defense_assess as judge
    from chess_coach import objective_fork_defense_budget as budget

    db, evidence = fixture(tmp_path / "exhausted.sqlite", monkeypatch)
    begin(db, evidence)
    submit(db, "fork-defense", LEARNER, event_id="answer", move="a1b1")
    monkeypatch.setattr(budget, "LIMIT", 63)
    monkeypatch.setattr(judge, "scan", lambda board: pytest.fail("unreserved scan"))
    assert process(db, LEARNER)["outcomes"] == {"unresolved": 1}
    result = inspect(db, LEARNER, "fork-defense", "answer")
    assert result == {
        "status": "unresolved",
        "reason": "fork_proof_budget_exhausted",
    }
    db.close()


@pytest.mark.parametrize("move", ["h2h3", "a1a8"])
def test_fork_remaining_or_checking_move_is_unresolved_not_incorrect(tmp_path, monkeypatch, move):
    db, evidence = fixture(tmp_path / "unknown.sqlite", monkeypatch, failure=True)
    if move == "h2h3":
        import chess

        from chess_coach.fork_defense_safety import quiet_after
        from chess_coach.fork_defense_scan import scan

        board = chess.Board("7k/6p1/8/8/1n6/8/7P/R3K3 w - - 0 1")
        assert "b4c2" in scan(quiet_after(board, chess.Move.from_uci(move)))["proven"]
    begin(db, evidence)
    assert (
        submit(db, "fork-defense", LEARNER, event_id="answer", move=move)["status"]
        == "needs_verification"
    )
    assert process(db, LEARNER)["outcomes"] == {"unresolved": 1}
    assert inspect(db, LEARNER, "fork-defense", "answer")["status"] == "unresolved"
    db.close()


def test_unlisted_supported_defense_is_independently_verified(tmp_path, monkeypatch):
    db, evidence = fixture(tmp_path / "alternative.sqlite", monkeypatch, failure=True)
    begin(db, evidence)
    assert (
        submit(db, "fork-defense", LEARNER, event_id="answer", move="e1f2")["status"]
        == "needs_verification"
    )
    assert process(db, LEARNER)["outcomes"] == {"correct": 1}
    db.close()


def test_rejected_review_and_foreign_or_created_source_are_unavailable(tmp_path, monkeypatch):
    db, evidence = fixture(tmp_path / "review.sqlite", monkeypatch)
    with pytest.raises(ValueError):
        start(
            db,
            attempt_id="foreign",
            subject="fixture_other",
            source_type="own-game",
            version=VERSION,
            key=str(evidence),
        )
    begin(db, evidence)
    submit(db, "fork-defense", LEARNER, event_id="answer", move="a1b1")
    review_evidence(db, evidence, decision="reject", actor="fixture_reviewer")
    assert process(db, LEARNER)["outcomes"] == {"unresolved": 1}
    assert inspect(db, LEARNER, "fork-defense", "answer")["reason"] == "source_unavailable"
    db.close()
    db, created = created_fixture(tmp_path / "created.sqlite", monkeypatch)
    with pytest.raises(ValueError):
        begin(db, created)
    db.close()


def test_another_uncertain_fork_remains_after_named_fork_is_avoided():
    import chess

    from chess_coach.fork_defense_safety import quiet_after
    from chess_coach.fork_defense_scan import scan
    from chess_coach.objective_fork_defense_budget import scope
    from chess_coach.objective_fork_defense_judge import verify

    board = chess.Board("7k/6p1/8/8/1n6/8/1R5P/R3K3 w - - 0 1")
    move = chess.Move.from_uci("a1b1")
    after = quiet_after(board, move)
    found = scan(after)
    assert "b4c2" not in found["proven"] and "b4d3" in found["uncertain"]
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
    assert result["status"] == "unresolved"
    assert result["reason"] == "fork_or_consequence_unresolved"


def test_hint_is_accounted_and_does_not_change_original_answer(tmp_path, monkeypatch):
    from chess_coach.unified_session_events import hint

    db, evidence = fixture(tmp_path / "hint.sqlite", monkeypatch)
    begin(db, evidence)
    assert hint(db, "fork-defense", LEARNER, event_id="hint")["assistance_kind"] == "hinted"
    answer = submit(db, "fork-defense", LEARNER, event_id="answer", move="a1b1")
    assert process(db, LEARNER)["outcomes"] == {"correct": 1}
    result = inspect(db, LEARNER, "fork-defense", "answer")
    assert result["assistance"] == "hinted"
    assert submit(db, "fork-defense", LEARNER, event_id="answer", move="a1b1") == answer
    db.close()


def test_source_type_and_objective_version_must_both_match():
    from chess_coach.objective_fork_defense_contract import GOAL, is_source

    row = {"source_type": "own-game", "source_version": VERSION, "objective": GOAL}
    assert is_source(row)
    assert not is_source(row | {"source_type": "public"})
    assert not is_source(row | {"source_version": "fork-execution-own-v1"})
    assert not is_source(row | {"objective": "execute_named_fork"})


def test_ep_history_and_forcing_captures_remain_unresolved():
    import chess

    from chess_coach.objective_fork_defense_budget import scope
    from chess_coach.objective_fork_defense_judge import verify

    cases = [
        ("7k/8/8/3pP3/8/8/8/7K w - d6 0 1", "e5e6", "history_or_root_unresolved"),
        ("7k/8/8/8/n7/8/8/R3K3 w - - 0 1", "a1a4", "defense_or_counterplay_unresolved"),
    ]
    for fen, text, reason in cases:
        board = chess.Board(fen)
        move = board.parse_uci(text)
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
        assert result["status"] == "unresolved" and result["reason"] == reason
