from __future__ import annotations

import json

import chess
import chess.pgn
import pytest

from chess_coach.db import Database
from chess_coach.ingest import ingest_pgn
from chess_coach.motifs import detect_motifs
from chess_coach.ontology import seed_ontology, skill_descendants
from chess_coach.tactical_ontology import seed_tactical_ontology
from chess_coach.tactical_opportunities import record_game_opportunities
from chess_coach.tactical_rules import mate_in_one_fact

WHITE = "8/8/8/8/4Q3/2K5/8/2k5 w - - 0 1"
BLACK = "2K5/8/2k5/4q3/8/8/8/8 b - - 0 1"
PINNED = "k3r3/8/8/8/8/3qR3/8/4K3 w - - 0 1"


def game_db(fen: str, moves: list[str]) -> tuple[Database, str]:
    board = chess.Board(fen)
    game = chess.pgn.Game()
    game.setup(board)
    game.headers["White"] = "SyntheticWhite"
    game.headers["Black"] = "SyntheticBlack"
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
    assert candidate["mapping_status"] == "preview" and candidate["human_validated"] is False
    assert candidate["confidence_rationale"]
    assert candidate["source_fact_ids"] and candidate["detector_run_id"]
    assert "SyntheticWhite" not in json.dumps(candidate)
    assert "SyntheticBlack" not in json.dumps(candidate)
    assert db.connection.execute("SELECT pgn FROM games").fetchone()[0] == raw
    assert db.connection.execute("SELECT COUNT(*) FROM evidence_mappings").fetchone()[0] == 0
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


def test_engine_disagreement_is_ambiguous_without_changing_fact_identity() -> None:
    db, _ = game_db(WHITE, ["e4c2"])
    before = record_game_opportunities(db, 1, learner="SyntheticWhite")[0]
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
    assert result["source_fact_ids"] == before["source_fact_ids"]
    assert result["detector_run_id"] == before["detector_run_id"]


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
