from __future__ import annotations

import json
import sqlite3
import subprocess
import sys

import chess
import chess.pgn
import pytest

from chess_coach.classification_schema import add_classification_lineage
from chess_coach.db import SCHEMA, Database
from chess_coach.evidence import evidence_report, record_evidence, validate_evidence
from chess_coach.evidence_review import inspect_evidence, list_evidence, review_evidence
from chess_coach.evidence_schema import add_evidence_lineage
from chess_coach.fact_runs import record_fact_run
from chess_coach.fact_schema import add_fact_lineage
from chess_coach.ingest import ingest_pgn
from chess_coach.lichess_schema import add_sync_turn
from chess_coach.mastery import mastery_report, update_mastery
from chess_coach.puzzle_session_schema import add_puzzle_sessions
from chess_coach.tactical_opportunities import record_game_opportunities

WHITE = "8/8/8/8/4Q3/2K5/8/2k5 w - - 0 1"


def candidate_db(path=":memory:") -> tuple[Database, int]:
    board = chess.Board(WHITE)
    game = chess.pgn.Game()
    game.setup(board)
    game.headers["White"] = "SyntheticWhite"
    game.headers["Black"] = "SyntheticBlack"
    game.add_variation(board.parse_uci("e4c2"))
    db = Database(path)
    db.initialize()
    ingest_pgn(db, str(game))
    result = record_game_opportunities(db, 1, learner="SyntheticWhite")
    evidence_ids = result[0]["evidence_ids"]
    assert isinstance(evidence_ids, list)
    return db, evidence_ids[0]


def test_review_lifecycle_replay_and_mastery_invalidation() -> None:
    db, evidence_id = candidate_db()
    before = inspect_evidence(db, evidence_id)
    assert before["review_status"] == "unreviewed" and before["lifecycle_status"] == "active"
    assert before["decision_fen"] == WHITE and before["position_fen"] != WHITE
    assert before["facts"][0]["fact_type"] == "mate_in_one"
    assert before["facts"][0]["detector_version"] and before["mapper_version"]
    assert before["reviews"] == []
    assert (
        update_mastery(db, skill="mate_in_one", operation="execute", subject="syntheticwhite")[
            "status"
        ]
        == "insufficient"
    )

    accepted = review_evidence(
        db, evidence_id, decision="accept", actor="fixture-reviewer", rationale="checked"
    )
    assert accepted["review_status"] == "accepted"
    assert accepted["review_actor"] == "fixture-reviewer" and accepted["reviewed_at"]
    assert accepted["reviews"][0]["rationale"] == "checked"
    replay = record_game_opportunities(db, 1, learner="SyntheticWhite")[0]
    assert replay["evidence_ids"] == [evidence_id] and replay["human_validated"] is True
    assert update_mastery(db, skill="mate_in_one", operation="execute", subject="syntheticwhite")

    rejected = review_evidence(db, evidence_id, decision="reject", actor="fixture-reviewer")
    assert rejected["review_status"] == "rejected"
    assert mastery_report(db, subject="syntheticwhite")[0]["exclusions"]["rejected"] == 1
    assert evidence_report(db) == []
    revoked = review_evidence(db, evidence_id, decision="revoke", actor="fixture-reviewer")
    assert revoked["review_status"] == "revoked"
    corrected = review_evidence(db, evidence_id, decision="accept", actor="fixture-reviewer")
    assert corrected["review_status"] == "accepted"
    assert [event["decision"] for event in corrected["reviews"]] == [
        "accept",
        "reject",
        "revoke",
        "accept",
    ]
    assert db.connection.execute("SELECT COUNT(*) FROM evidence_mappings").fetchone()[0] == 1


def test_legacy_flag_has_unknown_reviewer_and_no_fabricated_event() -> None:
    db = Database(":memory:")
    db.connection.executescript(SCHEMA)
    add_sync_turn(db.connection)
    add_puzzle_sessions(db.connection)
    add_fact_lineage(db.connection)
    add_evidence_lineage(db.connection)
    add_classification_lineage(db.connection)
    db.connection.execute(
        """INSERT INTO evidence_mappings
        (skill, operation, outcome, confidence, human_validated, context_json, source_facts_json)
        VALUES ('fork', 'execute', 'success', 1, 1, 'legacy-invalid-json', '[17]')"""
    )
    db.connection.execute(
        "INSERT INTO evidence_mappings (skill, operation, outcome, confidence, human_validated) "
        "VALUES ('fork', 'execute', 'success', 1, 2)"
    )
    db.connection.execute("PRAGMA user_version = 8")
    db.connection.commit()
    db.initialize()
    db.initialize()
    result = inspect_evidence(db, 1)
    assert result["review_status"] == "legacy_accepted"
    assert result["review_actor"] is None and result["reviewed_at"] is None
    assert result["reviews"] == [] and result["source_provenance"] == "unknown"
    assert result["legacy_validation"] == {"accepted": True, "actor": None, "reviewed_at": None}
    assert result["context"] == "legacy-invalid-json" and result["decision_fen"] is None
    assert result["source_facts"] == [17] and result["facts"] == []
    unknown = inspect_evidence(db, 2)
    assert unknown["review_status"] == "legacy_unknown"
    assert unknown["legacy_validation"] == {
        "accepted": None,
        "actor": None,
        "reviewed_at": None,
        "raw_flag": 2,
    }
    assert db.connection.execute("PRAGMA user_version").fetchone()[0] == 26
    revoked = review_evidence(db, 1, decision="revoke", actor="fixture-reviewer")
    assert revoked["review_status"] == "revoked" and len(revoked["reviews"]) == 1
    assert revoked["legacy_validation"] == result["legacy_validation"]


def test_review_is_savepoint_safe_and_outer_transaction_remains_owned() -> None:
    db, evidence_id = candidate_db()
    db.connection.execute("BEGIN")
    db.connection.execute(
        "INSERT INTO games (pgn, white, black, result) VALUES ('pending', 'A', 'B', '*')"
    )
    review_evidence(db, evidence_id, decision="accept", actor="fixture-reviewer")
    assert db.connection.in_transaction
    db.connection.rollback()
    assert inspect_evidence(db, evidence_id)["review_status"] == "unreviewed"
    assert db.connection.execute("SELECT COUNT(*) FROM games").fetchone()[0] == 1


def test_review_failure_rolls_back_only_its_savepoint() -> None:
    db, evidence_id = candidate_db()
    db.connection.execute(
        """INSERT INTO mastery_states
        (subject, skill, operation, mastery, uncertainty, evidence_weight, trend_30d, updated_at, model_version)
        VALUES ('syntheticwhite', 'mate_in_one', 'execute', 0.5, 0.2, 1, 0, 'test', 'test')"""
    )
    db.connection.execute(
        """CREATE TRIGGER fail_review BEFORE UPDATE ON mastery_states
        BEGIN SELECT RAISE(ABORT, 'injected failure'); END"""
    )
    db.connection.commit()
    db.connection.execute("BEGIN")
    db.connection.execute(
        "INSERT INTO games (pgn, white, black, result) VALUES ('pending', 'A', 'B', '*')"
    )
    with pytest.raises(sqlite3.IntegrityError, match="injected failure"):
        review_evidence(db, evidence_id, decision="accept", actor="fixture-reviewer")
    assert db.connection.in_transaction
    assert db.connection.execute("SELECT COUNT(*) FROM games").fetchone()[0] == 2
    assert inspect_evidence(db, evidence_id)["review_status"] == "unreviewed"
    assert db.connection.execute("SELECT COUNT(*) FROM evidence_review_events").fetchone()[0] == 0
    db.connection.rollback()


def test_review_events_are_immutable_and_actor_is_required() -> None:
    db, evidence_id = candidate_db()
    with pytest.raises(ValueError, match="actor"):
        review_evidence(db, evidence_id, decision="accept", actor=" ")
    import inspect

    with pytest.raises(TypeError):
        inspect.signature(validate_evidence).bind(db, evidence_id)
    with pytest.raises(ValueError, match="no decision"):
        review_evidence(db, evidence_id, decision="revoke", actor="fixture-reviewer")
    with pytest.raises(ValueError, match="unknown evidence"):
        review_evidence(db, 999, decision="accept", actor="fixture-reviewer")
    review_evidence(db, evidence_id, decision="accept", actor="fixture-reviewer")
    with pytest.raises(sqlite3.IntegrityError, match="immutable"):
        db.connection.execute("UPDATE evidence_review_events SET decision = 'reject'")
    with pytest.raises(sqlite3.IntegrityError, match="immutable"):
        db.connection.execute("DELETE FROM evidence_review_events")
    assert inspect_evidence(db, evidence_id)["review_status"] == "accepted"


def test_list_pagination_and_nullable_position() -> None:
    db = Database(":memory:")
    db.initialize()
    ids = [
        record_evidence(db, skill="fork", operation="execute", outcome="ambiguous", confidence=0)
        for _ in range(3)
    ]
    assert [row["id"] for row in list_evidence(db, limit=2)] == ids[:2]
    assert [row["id"] for row in list_evidence(db, after_id=ids[1])] == ids[2:]
    result = inspect_evidence(db, ids[0])
    assert result["position_id"] is None and result["game_id"] is None
    assert result["review_status"] == "unreviewed" and result["lifecycle_status"] == "unscoped"
    with pytest.raises(ValueError):
        list_evidence(db, limit=0)


def test_cli_list_inspect_accept_reject_and_rerun(tmp_path) -> None:
    path = tmp_path / "coach.sqlite"
    db, evidence_id = candidate_db(path)
    db.close()

    def run(*args):
        result = subprocess.run(
            [sys.executable, "-m", "chess_coach.cli", "--db", str(path), *args],
            text=True,
            capture_output=True,
            check=True,
        )
        return json.loads(result.stdout)

    listed = run("list-evidence")
    assert listed[0]["id"] == evidence_id and listed[0]["review_status"] == "unreviewed"
    assert listed[0]["facts"][0]["detector_version"]
    inspected = run("inspect-evidence", str(evidence_id))
    assert inspected["decision_fen"] == WHITE and inspected["facts"]
    accepted = run(
        "review-evidence",
        str(evidence_id),
        "--decision",
        "accept",
        "--actor",
        "fixture-reviewer",
        "--rationale",
        "checked",
    )
    assert accepted["review_status"] == "accepted"
    db = Database(path)
    again = record_game_opportunities(db, 1, learner="SyntheticWhite")[0]
    assert again["evidence_ids"] == [evidence_id] and again["human_validated"] is True
    db.close()
    rejected = run(
        "review-evidence", str(evidence_id), "--decision", "reject", "--actor", "fixture-reviewer"
    )
    assert rejected["review_status"] == "rejected"
    assert [item["decision"] for item in rejected["reviews"]] == ["accept", "reject"]
    revoked = run(
        "review-evidence", str(evidence_id), "--decision", "revoke", "--actor", "fixture-reviewer"
    )
    assert revoked["review_status"] == "revoked"
    assert run("validate-evidence", str(evidence_id), "--actor", "fixture-reviewer") == {
        "validated": evidence_id
    }
    assert run("inspect-evidence", str(evidence_id))["review_status"] == "accepted"


def test_review_and_supersession_are_separate_states() -> None:
    db, evidence_id = candidate_db()
    review_evidence(db, evidence_id, decision="accept", actor="fixture-reviewer")
    fact = inspect_evidence(db, evidence_id)["facts"][0]
    record_fact_run(
        db,
        position_id=1,
        producer="mate-in-one",
        detector_version="v2",
        input_data={"pre_move_fen": WHITE, "played_move": "e4c2"},
        facts=[{"fact_type": fact["fact_type"], "payload": fact["payload"]}],
    )
    old = inspect_evidence(db, evidence_id)
    assert old["lifecycle_status"] == "superseded"
    assert old["review_status"] == "accepted" and len(old["reviews"]) == 1
    assert old["facts"][0]["detector_status"] == "superseded"
    assert evidence_report(db) == []


def test_v8_review_migration_rolls_back_without_losing_legacy_flag(monkeypatch) -> None:
    from chess_coach import db_recent
    from chess_coach.evidence_review_schema import add_evidence_reviews

    db = Database(":memory:")
    db.connection.executescript(SCHEMA)
    add_sync_turn(db.connection)
    add_puzzle_sessions(db.connection)
    add_fact_lineage(db.connection)
    add_evidence_lineage(db.connection)
    add_classification_lineage(db.connection)
    db.connection.execute(
        "INSERT INTO evidence_mappings (skill, operation, outcome, confidence, human_validated) "
        "VALUES ('fork', 'execute', 'success', 1, 1)"
    )
    db.connection.execute("PRAGMA user_version = 8")
    db.connection.commit()

    def fail_after_schema(connection):
        add_evidence_reviews(connection)
        raise RuntimeError("injected migration failure")

    with monkeypatch.context() as patch:
        patch.setattr(db_recent, "add_evidence_reviews", fail_after_schema)
        with pytest.raises(RuntimeError, match="injected migration failure"):
            db.initialize()
    assert db.connection.execute("PRAGMA user_version").fetchone()[0] == 8
    assert "legacy_validated" not in {
        row[1] for row in db.connection.execute("PRAGMA table_info(evidence_mappings)")
    }
    assert db.connection.execute("SELECT human_validated FROM evidence_mappings").fetchone()[0] == 1
    assert (
        db.connection.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type = 'table' AND name = 'evidence_review_events'"
        ).fetchone()[0]
        == 0
    )
    db.initialize()
    assert inspect_evidence(db, 1)["review_status"] == "legacy_accepted"


def _seed_cached_mastery(db):
    db.connection.execute(
        "INSERT INTO mastery_states (subject,skill,operation,mastery,uncertainty,evidence_weight,trend_30d,updated_at,model_version,is_stale) VALUES (?, ?, ?, 0.5, 0.5, 1, NULL, ?, ?, 0)",
        ("fixture-subject", "fork", "execute", "2026-01-01T00:00:00+00:00", "old"),
    )
    db.connection.commit()


def _is_stale(db):
    return db.connection.execute("SELECT is_stale FROM mastery_states").fetchone()[0]


def test_only_changed_active_review_eligibility_stales_mastery() -> None:
    db = Database(":memory:")
    db.initialize()
    accepted = record_evidence(
        db,
        skill="fork",
        operation="execute",
        outcome="success",
        confidence=1,
        subject="fixture-subject",
    )
    validate_evidence(db, accepted, actor="fixture-reviewer")
    _seed_cached_mastery(db)
    review_evidence(db, accepted, decision="accept", actor="fixture-reviewer")
    assert _is_stale(db) == 0
    unreviewed = record_evidence(
        db,
        skill="fork",
        operation="execute",
        outcome="failure",
        confidence=1,
        subject="fixture-subject",
    )
    review_evidence(db, unreviewed, decision="reject", actor="fixture-reviewer")
    review_evidence(db, unreviewed, decision="revoke", actor="fixture-reviewer")
    assert _is_stale(db) == 0
    review_evidence(db, accepted, decision="reject", actor="fixture-reviewer")
    assert _is_stale(db) == 1


def test_nonstandard_legacy_flag_acceptance_changes_eligibility() -> None:
    db = Database(":memory:")
    db.initialize()
    unusual = record_evidence(
        db,
        skill="fork",
        operation="execute",
        outcome="failure",
        confidence=1,
        subject="fixture-subject",
    )
    db.connection.execute(
        "UPDATE evidence_mappings SET human_validated = 2 WHERE id = ?", (unusual,)
    )
    db.connection.commit()
    _seed_cached_mastery(db)
    assert inspect_evidence(db, unusual)["review_status"] == "legacy_unknown"
    review_evidence(db, unusual, decision="accept", actor="fixture-reviewer")
    assert _is_stale(db) == 1
