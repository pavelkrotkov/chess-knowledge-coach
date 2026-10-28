from __future__ import annotations

import json

import chess
import chess.pgn
import pytest

from chess_coach.db import Database
from chess_coach.evidence import evidence_report, validate_evidence
from chess_coach.fact_runs import record_fact_run
from chess_coach.ingest import ingest_pgn
from chess_coach.motifs import detect_motifs
from chess_coach.ontology import seed_ontology, skill_descendants
from chess_coach.tactical_ontology import seed_tactical_ontology
from chess_coach.tactical_opportunities import record_game_opportunities
from chess_coach.tactical_rules import mate_in_one_fact

WHITE = "8/8/8/8/4Q3/2K5/8/2k5 w - - 0 1"
BLACK = "2K5/8/2k5/4q3/8/8/8/8 b - - 0 1"
PINNED = "k3r3/8/8/8/8/3qR3/8/4K3 w - - 0 1"


def game_db(fen: str, moves: list[str], *, with_utc: bool = False) -> tuple[Database, str]:
    board = chess.Board(fen)
    game = chess.pgn.Game()
    game.setup(board)
    game.headers["White"] = "SyntheticWhite"
    game.headers["Black"] = "SyntheticBlack"
    if with_utc:
        game.headers["UTCDate"] = "2025.02.03"
        game.headers["UTCTime"] = "12:34:56"
    node = game
    for uci in moves:
        move = board.parse_uci(uci)
        node = node.add_variation(move)
        board.push(move)
    raw = str(game)
    db = Database(":memory:")
    db.initialize()
    ingest_pgn(db, raw)
    return db, raw


@pytest.mark.parametrize(
    ("fen", "learner", "move", "expected"),
    [
        (WHITE, "syntheticwhite", "e4c2", "success"),
        (WHITE, "SYNTHETICWHITE", "e4h1", "success"),
        (WHITE, "SyntheticWhite", "e4d3", "failure"),
        (WHITE, "SyntheticWhite", "e4e8", "ambiguous"),
        (BLACK, "SyntheticBlack", "e5c7", "success"),
        (BLACK, "SyntheticBlack", "e5h8", "success"),
        (BLACK, "SyntheticBlack", "e5d6", "failure"),
        (BLACK, "SyntheticBlack", "e5e1", "ambiguous"),
    ],
)
def test_mate_candidates_are_legal_learner_decisions(fen, learner, move, expected) -> None:
    db, raw = game_db(fen, [move])
    result = record_game_opportunities(db, 1, learner=learner)
    assert len(result) == 1
    candidate = result[0]
    assert candidate["pre_move_fen"] == fen
    assert candidate["played_move"] == move
    assert candidate["outcome"] == expected
    expected_mates = {"e4c2", "e4h1", "e4e1"} if fen == WHITE else {"e5c7", "e5h8", "e5e8"}
    assert isinstance(candidate["mating_moves"], list)
    assert set(candidate["mating_moves"]) == expected_mates
    assert candidate["skill"] == "mate_in_one" and candidate["operation"] == "execute"
    assert candidate["mapping_status"] == "active" and candidate["human_validated"] is False
    assert candidate["confidence_rationale"]
    assert candidate["source_fact_ids"] and candidate["detector_run_id"]
    assert "SyntheticWhite" not in json.dumps(candidate)
    assert "SyntheticBlack" not in json.dumps(candidate)
    assert db.connection.execute("SELECT pgn FROM games").fetchone()[0] == raw
    evidence = db.connection.execute("SELECT * FROM evidence_mappings").fetchone()
    assert evidence["subject"] == learner.casefold()
    assert (evidence["skill"], evidence["operation"], evidence["outcome"]) == (
        "mate_in_one",
        "execute",
        expected,
    )
    assert evidence["human_validated"] == 0 and evidence["observation_at"] is None
    assert evidence["source_provenance"] == "linked"
    assert json.loads(evidence["source_facts_json"]) == candidate["source_fact_ids"]
    assert json.loads(evidence["context_json"])["ontology_version"] == "tactical-mate-v1"
    assert evidence["confidence"] == (0.0 if expected == "ambiguous" else 1.0)
    assert db.connection.execute("SELECT COUNT(*) FROM mastery_states").fetchone()[0] == 0
    again = record_game_opportunities(db, 1, learner=learner)
    assert again == result
    assert db.connection.execute("SELECT COUNT(*) FROM detector_facts").fetchone()[0] == 1


def test_pinned_pseudo_capture_is_not_a_proven_tactical_opportunity() -> None:
    board = chess.Board(PINNED)
    capture = chess.Move.from_uci("e3d3")
    assert board.is_pseudo_legal(capture) and not board.is_legal(capture)
    assert any(f["motif"] == "hanging_piece" and f["square"] == "d3" for f in detect_motifs(board))
    assert mate_in_one_fact(PINNED, "e3e4") is None
    db, _ = game_db(PINNED, ["e3e4"])
    assert record_game_opportunities(db, 1, learner="SyntheticWhite") == []
    assert db.connection.execute("SELECT COUNT(*) FROM evidence_mappings").fetchone()[0] == 0
    with pytest.raises(ValueError, match="invalid tactical decision"):
        mate_in_one_fact(PINNED, "e3d3")


def test_no_mate_and_unmatched_or_opponent_learner_do_not_create_candidates() -> None:
    db, _ = game_db(chess.STARTING_FEN, ["e2e4"])
    assert record_game_opportunities(db, 1, learner="unknown") == []
    assert record_game_opportunities(db, 1, learner="SyntheticBlack") == []
    assert db.connection.execute("SELECT COUNT(*) FROM detector_runs").fetchone()[0] == 0
    assert record_game_opportunities(db, 1, learner="SyntheticWhite") == []
    assert db.connection.execute("SELECT COUNT(*) FROM detector_runs").fetchone()[0] == 1
    assert db.connection.execute("SELECT COUNT(*) FROM detector_facts").fetchone()[0] == 0
    assert db.connection.execute("SELECT COUNT(*) FROM mapping_runs").fetchone()[0] == 1
    assert db.connection.execute("SELECT COUNT(*) FROM evidence_mappings").fetchone()[0] == 0


def test_engine_disagreement_is_ambiguous_without_changing_fact_identity() -> None:
    db, _ = game_db(WHITE, ["e4c2"])
    before = record_game_opportunities(db, 1, learner="SyntheticWhite")[0]
    assert isinstance(before["evidence_ids"], list)
    evidence_id = before["evidence_ids"][0]
    validate_evidence(db, evidence_id, actor="fixture-reviewer")
    reviewed = record_game_opportunities(db, 1, learner="SyntheticWhite")[0]
    assert reviewed["evidence_ids"] == [evidence_id] and reviewed["human_validated"] is True
    db.connection.execute(
        "INSERT INTO analysis_runs (game_id, engine, engine_version, config_json) "
        "VALUES (1, 'fixture', 'v1', '{}')"
    )
    db.connection.execute(
        """INSERT INTO engine_outputs
        (run_id, position_id, best_move, multipv, decision_fen, score_pov)
        VALUES (1, 1, 'e4e8', 1, ?, 'white')""",
        (WHITE,),
    )
    db.connection.commit()
    result = record_game_opportunities(db, 1, learner="SyntheticWhite")[0]
    assert result["outcome"] == "ambiguous"
    assert result["engine_conflict_ids"] == [1]
    assert result["engine_conflicts"] == [{"id": 1, "best_move": "e4e8"}]
    assert record_game_opportunities(db, 1, learner="SyntheticWhite")[0] == result
    assert result["source_fact_ids"] == before["source_fact_ids"]
    assert result["detector_run_id"] == before["detector_run_id"]
    assert result["evidence_ids"] != before["evidence_ids"]
    assert result["human_validated"] is False
    old = db.connection.execute(
        "SELECT human_validated FROM evidence_mappings WHERE id = ?", (evidence_id,)
    ).fetchone()
    assert old[0] == 1
    assert evidence_report(db)[0]["ambiguous"] == 1
    assert db.connection.execute("SELECT COUNT(*) FROM evidence_mappings").fetchone()[0] == 2


def test_invalid_later_position_rolls_back_all_facts() -> None:
    board = chess.Board(WHITE)
    board.push_uci("e4e8")
    opponent = next(iter(board.legal_moves)).uci()
    db, _ = game_db(WHITE, ["e4e8", opponent])
    db.connection.execute("UPDATE positions SET fen = 'invalid' WHERE ply = 2")
    db.connection.commit()
    with pytest.raises(ValueError, match="stored position"):
        record_game_opportunities(db, 1, learner="SyntheticWhite")
    assert db.connection.execute("SELECT COUNT(*) FROM detector_runs").fetchone()[0] == 0
    assert db.connection.execute("SELECT COUNT(*) FROM detector_facts").fetchone()[0] == 0


def test_explicit_versioned_mate_concept_is_idempotent() -> None:
    db = Database(":memory:")
    db.initialize()
    seed_ontology(db, "legacy-v1")
    seed_tactical_ontology(db, version="tactical-v1")
    seed_tactical_ontology(db, version="tactical-v1")
    assert "mate_in_one" not in skill_descendants(db, "tactics", version="legacy-v1")
    assert "mate_in_one" in skill_descendants(db, "tactics", version="tactical-v1")
    assert (
        db.connection.execute(
            "SELECT COUNT(*) FROM skills WHERE skill = 'mate_in_one' AND ontology_version = ?",
            ("tactical-v1",),
        ).fetchone()[0]
        == 1
    )


def test_tactical_ontology_rejects_existing_different_version() -> None:
    db = Database(":memory:")
    db.initialize()
    seed_ontology(db, "existing")
    before = [tuple(row) for row in db.connection.execute("SELECT * FROM skills ORDER BY id")]
    with pytest.raises(ValueError, match="different contents"):
        seed_tactical_ontology(db, version="existing")
    assert [
        tuple(row) for row in db.connection.execute("SELECT * FROM skills ORDER BY id")
    ] == before


def test_stale_engine_and_alternative_mate_do_not_create_disagreement() -> None:
    db, _ = game_db(WHITE, ["e4c2"])
    db.connection.execute(
        "INSERT INTO analysis_runs (game_id, engine, engine_version, config_json) "
        "VALUES (1, 'fixture', 'v1', '{}')"
    )
    db.connection.executemany(
        """INSERT INTO engine_outputs
        (run_id, position_id, best_move, multipv, decision_fen, score_pov)
        VALUES (1, 1, ?, 1, ?, ?)""",
        [("e4e8", None, None), ("e4e8", WHITE, "black"), ("e4h1", WHITE, "white")],
    )
    db.connection.commit()
    candidate = record_game_opportunities(db, 1, learner="SyntheticWhite")[0]
    assert candidate["outcome"] == "success"
    assert candidate["engine_conflict_ids"] == []


def test_tactical_decision_input_errors_are_generic() -> None:
    for fen, move in (("bad-fen", "e4c2"), (WHITE, "not-uci"), (WHITE, "0000")):
        with pytest.raises(ValueError, match="invalid tactical decision"):
            mate_in_one_fact(fen, move)


def test_descriptive_fork_does_not_become_a_scored_opportunity() -> None:
    fen = "4k3/8/5b2/2r5/4N3/2N5/8/4K3 w - - 0 1"
    board = chess.Board(fen)
    assert any(fact["motif"] == "fork" for fact in detect_motifs(board))
    db, _ = game_db(fen, ["e4c5"])
    assert record_game_opportunities(db, 1, learner="SyntheticWhite") == []
    assert db.connection.execute("SELECT COUNT(*) FROM detector_facts").fetchone()[0] == 0
    assert db.connection.execute("SELECT COUNT(*) FROM evidence_mappings").fetchone()[0] == 0


def test_observation_time_is_source_time_and_preserved_on_replay() -> None:
    db, _ = game_db(WHITE, ["e4c2"], with_utc=True)
    first = record_game_opportunities(db, 1, learner="SyntheticWhite")[0]
    row = db.connection.execute("SELECT observation_at FROM evidence_mappings").fetchone()
    assert row[0] == "2025-02-03T12:34:56+00:00"
    assert (
        record_game_opportunities(db, 1, learner="SyntheticWhite")[0]["evidence_ids"]
        == first["evidence_ids"]
    )


def test_mapping_failure_rolls_back_facts_and_ontology() -> None:
    import sqlite3

    db, _ = game_db(WHITE, ["e4c2"])
    db.connection.execute(
        """CREATE TRIGGER reject_tactical BEFORE INSERT ON evidence_mappings
        BEGIN SELECT RAISE(ABORT, 'injected mapping failure'); END"""
    )
    db.connection.commit()
    with pytest.raises(sqlite3.IntegrityError, match="injected mapping failure"):
        record_game_opportunities(db, 1, learner="SyntheticWhite")
    for table in ("skills", "detector_runs", "detector_facts", "mapping_runs", "evidence_mappings"):
        assert db.connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0


def test_old_detector_replay_does_not_reactivate_superseded_mapping() -> None:
    db, _ = game_db(WHITE, ["e4c2"])
    original = record_game_opportunities(db, 1, learner="SyntheticWhite")[0]
    fact = mate_in_one_fact(WHITE, "e4c2")
    record_fact_run(
        db,
        position_id=1,
        producer="mate-in-one",
        detector_version="2.0.0",
        input_data={"pre_move_fen": WHITE, "played_move": "e4c2"},
        facts=[{"fact_type": "mate_in_one", "payload": fact}],
    )
    replay = record_game_opportunities(db, 1, learner="SyntheticWhite")[0]
    assert replay["detector_status"] == "superseded"
    assert replay["mapping_status"] == "superseded_detector" and replay["evidence_ids"] == []
    assert evidence_report(db) == []
    assert (
        db.connection.execute(
            "SELECT status FROM mapping_runs WHERE id = ?", (original["mapping_run_id"],)
        ).fetchone()[0]
        == "superseded"
    )


def test_new_ontology_version_supersedes_mapping_without_transferring_review() -> None:
    db, _ = game_db(WHITE, ["e4c2"])
    first = record_game_opportunities(db, 1, learner="SyntheticWhite")[0]
    assert isinstance(first["evidence_ids"], list)
    old_id = first["evidence_ids"][0]
    validate_evidence(db, old_id, actor="fixture-reviewer")
    second = record_game_opportunities(
        db, 1, learner="SyntheticWhite", ontology_version="tactical-mate-v2"
    )[0]
    assert second["evidence_ids"] != first["evidence_ids"]
    assert second["source_fact_ids"] == first["source_fact_ids"]
    assert second["human_validated"] is False and second["mapping_status"] == "active"
    assert (
        db.connection.execute(
            "SELECT human_validated FROM evidence_mappings WHERE id = ?", (old_id,)
        ).fetchone()[0]
        == 1
    )
    old = record_game_opportunities(db, 1, learner="SyntheticWhite")[0]
    assert old["mapping_status"] == "superseded" and old["evidence_ids"] == [old_id]
    active = db.connection.execute(
        "SELECT id FROM mapping_runs WHERE status = 'active'"
    ).fetchone()[0]
    assert active == second["mapping_run_id"]


def test_cross_producer_collision_does_not_overwrite_prior_evidence() -> None:
    from chess_coach.mapping_runs import record_mapping_run_in_transaction
    from chess_coach.mapping_transaction import mapping_transaction

    db, _ = game_db(WHITE, ["e4c2"])
    fact = mate_in_one_fact(WHITE, "e4c2")
    source = record_fact_run(
        db,
        position_id=1,
        producer="mate-in-one",
        detector_version="1.0.0",
        input_data={"pre_move_fen": WHITE, "played_move": "e4c2"},
        facts=[{"fact_type": "mate_in_one", "payload": fact}],
    )
    with mapping_transaction(db):
        prior = record_mapping_run_in_transaction(
            db,
            position_id=1,
            producer="independent",
            mapper_version="v1",
            subject="syntheticwhite",
            operation="execute",
            scope_key="other",
            input_data={},
            mappings=[
                {
                    "skill": "mate_in_one",
                    "outcome": "ambiguous",
                    "confidence": 0.0,
                    "fact_ids": source["fact_ids"],
                    "context": {},
                    "observation_at": None,
                }
            ],
        )
    with pytest.raises(ValueError, match="already mapped"):
        record_game_opportunities(db, 1, learner="SyntheticWhite")
    assert db.connection.execute("SELECT COUNT(*) FROM mapping_runs").fetchone()[0] == 1
    assert (
        db.connection.execute(
            "SELECT status FROM mapping_runs WHERE id = ?", (prior["run_id"],)
        ).fetchone()[0]
        == "active"
    )
    assert db.connection.execute("SELECT COUNT(*) FROM skills").fetchone()[0] == 0


def test_unrelated_reviewed_evidence_is_preserved() -> None:
    from chess_coach.mapping_runs import record_mapping_run_in_transaction
    from chess_coach.mapping_transaction import mapping_transaction

    db, _ = game_db(WHITE, ["e4c2"])
    unrelated = record_fact_run(
        db,
        position_id=1,
        producer="other-detector",
        detector_version="v1",
        input_data={},
        facts=[{"fact_type": "fork", "payload": {"description": "fixture"}}],
    )
    with mapping_transaction(db):
        mapping = record_mapping_run_in_transaction(
            db,
            position_id=1,
            producer="other-mapper",
            mapper_version="v1",
            subject="syntheticwhite",
            operation="execute",
            scope_key="fork",
            input_data={},
            mappings=[
                {
                    "skill": "fork",
                    "outcome": "ambiguous",
                    "confidence": 0.0,
                    "fact_ids": unrelated["fact_ids"],
                    "context": {},
                    "observation_at": None,
                }
            ],
        )
    evidence_id = mapping["evidence_ids"][0]
    validate_evidence(db, evidence_id, actor="fixture-reviewer")
    candidate = record_game_opportunities(db, 1, learner="SyntheticWhite")[0]
    assert candidate["evidence_ids"] != [evidence_id]
    assert (
        db.connection.execute(
            "SELECT human_validated FROM evidence_mappings WHERE id = ?", (evidence_id,)
        ).fetchone()[0]
        == 1
    )
    assert (
        db.connection.execute(
            "SELECT status FROM mapping_runs WHERE id = ?", (mapping["run_id"],)
        ).fetchone()[0]
        == "active"
    )
