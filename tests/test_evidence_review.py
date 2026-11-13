from __future__ import annotations

import sqlite3

import chess
import chess.pgn
import pytest

from chess_coach.db import Database
from chess_coach.evidence import evidence_report, validate_evidence
from chess_coach.evidence_review import inspect_evidence, review_evidence
from chess_coach.ingest import ingest_pgn
from chess_coach.mastery import mastery_report, update_mastery
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


def test_review_lifecycle_replay_and_mastery_invalidation(monkeypatch) -> None:
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

    # A newer no-fact result retires the current mapping without rewriting history.
    from chess_coach import tactical_opportunities

    with monkeypatch.context() as patch:
        patch.setattr(tactical_opportunities, "mate_in_one_fact", lambda *_: None)
        assert (
            record_game_opportunities(db, 1, learner="SyntheticWhite", detector_version="v2") == []
        )
        assert (
            record_game_opportunities(db, 1, learner="SyntheticWhite", detector_version="v2") == []
        )
    assert db.connection.execute("SELECT COUNT(*) FROM mapping_runs").fetchone()[0] == 1
    assert db.connection.execute("SELECT status FROM mapping_runs").fetchone()[0] == "superseded"
    old = inspect_evidence(db, evidence_id)
    assert old["review_status"] == "accepted" and old["lifecycle_status"] == "superseded"
    assert db.connection.execute("SELECT COUNT(*) FROM detector_runs").fetchone()[0] == 2
    assert (
        db.connection.execute(
            "SELECT COUNT(*) FROM detector_facts f JOIN detector_runs r ON r.id=f.run_id WHERE r.status='active'"
        ).fetchone()[0]
        == 0
    )
    restored = record_game_opportunities(db, 1, learner="SyntheticWhite", detector_version="v3")[0]
    restored_ids = restored["evidence_ids"]
    assert isinstance(restored_ids, list) and restored_ids != [evidence_id]
    with monkeypatch.context() as patch:
        patch.setattr(tactical_opportunities, "mate_in_one_fact", lambda *_: None)
        assert (
            record_game_opportunities(db, 1, learner="SyntheticWhite", detector_version="v2") == []
        )
    assert inspect_evidence(db, restored_ids[0])["lifecycle_status"] == "active"
    assert inspect_evidence(db, evidence_id)["review_status"] == "accepted"
    # A fresh no-fact stage remains complete and restartable after interruption.
    from chess_coach import pipeline_stage

    game = chess.pgn.Game()
    game.headers["White"], game.headers["Black"] = "SyntheticWhite", "SyntheticBlack"
    game.add_variation(chess.Move.from_uci("e2e4"))
    ingest_pgn(db, str(game))
    game_id = db.connection.execute("SELECT MAX(id) FROM games").fetchone()[0]

    def scan(generation):
        record_game_opportunities(
            db, game_id, learner="SyntheticWhite", pipeline_generation=generation
        )

    with monkeypatch.context() as patch:
        patch.setattr(
            pipeline_stage,
            "checkpoint",
            lambda *_a, **_k: (_ for _ in ()).throw(KeyboardInterrupt()),
        )
        with pytest.raises(KeyboardInterrupt):
            pipeline_stage.run_stage(db, game_id, "tactical", "fixture", scan, generated=True)
    result = pipeline_stage.run_stage(db, game_id, "tactical", "fixture", scan, generated=True)
    assert result["status"] == "complete"
    assert pipeline_stage.run_stage(db, game_id, "tactical", "fixture", scan, generated=True)[
        "replayed"
    ]
    assert (
        db.connection.execute(
            "SELECT COUNT(*) FROM mapping_runs m JOIN positions p ON p.id=m.position_id WHERE p.game_id=?",
            (game_id,),
        ).fetchone()[0]
        == 0
    )
    # Retain an exact legacy empty scope, but retire it after its detector changes.
    from chess_coach.learner_context import decision_contexts
    from chess_coach.mapping_transaction import mapping_transaction
    from chess_coach.tactical_mapping import map_decision
    from chess_coach.tactical_pipeline_replay import fact_run

    context = next(decision_contexts(db, game_id, learner="SyntheticWhite"))
    db.connection.execute("UPDATE digest_settings SET compact=1 WHERE id=1")
    db.connection.commit()
    with mapping_transaction(db):
        run = fact_run(db, context, tactical_opportunities.PRODUCER, "1.0.0", [], None)
        legacy = map_decision(db, context, run, None, "tactical-mate-v1")
    legacy_id = legacy["mapping_run_id"]
    assert (
        db.connection.execute(
            "SELECT typeof(output_hash) FROM mapping_runs WHERE id=?", (legacy_id,)
        ).fetchone()[0]
        == "blob"
    )
    assert record_game_opportunities(db, game_id, learner="SyntheticWhite") == []
    assert (
        db.connection.execute(
            "SELECT status FROM mapping_runs WHERE id=?", (legacy_id,)
        ).fetchone()[0]
        == "active"
    )
    assert (
        record_game_opportunities(db, game_id, learner="SyntheticWhite", detector_version="v2")
        == []
    )
    assert (
        db.connection.execute(
            "SELECT status FROM mapping_runs WHERE id=?", (legacy_id,)
        ).fetchone()[0]
        == "superseded"
    )


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
