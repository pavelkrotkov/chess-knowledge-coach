"""End-to-end practice evidence in the mastery policy."""

from datetime import UTC, datetime, timedelta

import chess
import pytest

from chess_coach.db import Database
from chess_coach.evidence_review import review_evidence
from chess_coach.mastery import mastery_report
from chess_coach.puzzle_sessions import request_hint, start_attempt
from chess_coach.training import create_training_item
from chess_coach.training_feedback import puzzle_training_ref, submit_training_move

FEN = "6k1/8/6K1/2Q5/8/8/8/8 b - - 0 1"
LINE = "g8h8 c5f8"


def transformed(variant):
    board = chess.Board(FEN)
    if variant & 1:
        board = board.transform(chess.flip_horizontal)
    if variant & 2:
        board = board.mirror()

    def translate(text):
        move = chess.Move.from_uci(text)
        mask = (7 if variant & 1 else 0) ^ (56 if variant & 2 else 0)
        return chess.Move(move.from_square ^ mask, move.to_square ^ mask).uci()

    return board.fen(), " ".join(map(translate, LINE.split())), translate


def make_attempt(
    db,
    number,
    variant=0,
    *,
    version="v1",
    move="c5c8",
    accept=True,
    hint=False,
    counters=False,
    skill="mate_in_one",
):
    fen, line, translate = transformed(variant)
    if counters:
        fen = " ".join([*fen.split()[:4], "12", "23"])
    puzzle = f"p{number}"
    db.connection.execute(
        'INSERT OR IGNORE INTO puzzle_corpora(version,source,checksum) VALUES (?,"fixture",?)',
        (version, version),
    )
    corpus = db.connection.execute(
        "SELECT id FROM puzzle_corpora WHERE version=?", (version,)
    ).fetchone()[0]
    db.connection.execute(
        """INSERT INTO puzzles
        (puzzle_id,corpus_id,fen,source,solution,rating,rating_deviation,themes_json,objective)
        VALUES (?,?,?,\"fixture\",?,1200,80,\"[]\",\"fixture\")""",
        (puzzle, corpus, fen, line),
    )
    db.connection.commit()
    attempt = f"attempt-{number}"
    start_attempt(db, attempt_id=attempt, version=version, puzzle_id=puzzle)
    item = create_training_item(
        db,
        source_type="puzzle",
        source_ref=puzzle_training_ref(version, puzzle),
        skill=skill,
        operation="execute",
    )
    if hint:
        request_hint(db, attempt, event_id="hint")
    result = submit_training_move(
        db, attempt, event_id="terminal", move=translate(move), item_id=item, subject="learner"
    )
    evidence = result["training"]["evidence_id"]
    if evidence is not None and accept:
        review_evidence(db, evidence, decision="accept", actor="fixture-reviewer")
    return evidence


def report(db):
    return mastery_report(db, subject="learner", as_of=datetime.now(UTC) + timedelta(seconds=1))[0]


def test_verified_prompt_dedup_latest_failure_and_review_revoke():
    db = Database(":memory:")
    db.initialize()
    first = make_attempt(db, 1)
    second = make_attempt(db, 2, variant=1)
    third = make_attempt(db, 3, variant=2)
    result = report(db)
    assert result["status"] == "sufficient" and result["mastery"] == 1
    assert result["context_count"] == 3 and result["training_context_supported"] is True
    newer = make_attempt(db, 4, version="v2", move="c5a5", counters=True)
    result = report(db)
    assert result["context_count"] == 3 and result["mastery"] == pytest.approx(2 / 3)
    assert result["exclusions"]["duplicate_context"] == 1
    assert (
        newer in result["supporting_evidence_ids"]
        and first not in result["supporting_evidence_ids"]
    )
    review_evidence(db, newer, decision="revoke", actor="fixture-reviewer")
    result = report(db)
    assert result["mastery"] == 1 and result["exclusions"]["revoked"] == 1
    assert result["supporting_evidence_ids"] == [first, second, third]
    assert db.connection.execute("SELECT COUNT(*) FROM mastery_events").fetchone()[0] == 3


def test_unreviewed_and_hinted_completions_do_not_count():
    db = Database(":memory:")
    db.initialize()
    first = make_attempt(db, 1, accept=False)
    assert make_attempt(db, 2, variant=1, hint=True) is None
    result = report(db)
    assert result["status"] == "insufficient" and result["context_count"] == 0
    assert result["exclusions"] == {"unreviewed_or_invalid_review": 1}
    review_evidence(db, first, decision="accept", actor="fixture-reviewer")
    assert report(db)["context_count"] == 1


def test_missing_completion_link_fails_closed():
    db = Database(":memory:")
    db.initialize()
    evidence = make_attempt(db, 1)
    db.connection.execute("DROP TRIGGER training_completion_no_delete")
    db.connection.execute("DELETE FROM training_completions WHERE evidence_id=?", (evidence,))
    db.connection.commit()
    assert report(db)["exclusions"] == {"invalid_training_lineage": 1}


def test_invalid_snapshot_fails_closed():
    db = Database(":memory:")
    db.initialize()
    evidence = make_attempt(db, 1)
    db.connection.execute("DROP TRIGGER puzzle_session_snapshot_no_update")
    db.connection.execute("DROP TRIGGER completed_puzzle_no_update")
    db.connection.execute(
        'UPDATE puzzle_sessions SET initial_fen="bad" WHERE attempt_id="attempt-1"'
    )
    db.connection.commit()
    result = report(db)
    assert result["status"] == "insufficient"
    assert result["exclusions"] == {"invalid_training_snapshot": 1}
    assert evidence is not None


def test_mixed_game_and_practice_repeat_position_counts_once():
    import chess.pgn

    from chess_coach.ingest import ingest_pgn
    from chess_coach.tactical_opportunities import record_game_opportunities

    db = Database(":memory:")
    db.initialize()
    repeated = make_attempt(db, 1)
    failure = make_attempt(db, 2, variant=1, move="c5a5")
    unique = make_attempt(db, 3, variant=2)
    board = chess.Board(FEN)
    board.push_uci("g8h8")
    game = chess.pgn.Game()
    game.setup(board)
    game.headers["White"] = "Learner"
    game.headers["Black"] = "Opponent"
    now = datetime.now(UTC)
    game.headers["UTCDate"] = now.strftime("%Y.%m.%d")
    game.headers["UTCTime"] = now.strftime("%H:%M:%S")
    game.add_variation(board.parse_uci("c5c8"))
    ingest_pgn(db, str(game))
    game_ids = record_game_opportunities(db, 1, learner="learner")[0]["evidence_ids"]
    assert isinstance(game_ids, list)
    game_evidence = game_ids[0]
    review_evidence(db, game_evidence, decision="accept", actor="fixture-reviewer")
    db.connection.execute('UPDATE evidence_mappings SET context_json="{}" WHERE id=?', (repeated,))
    db.connection.commit()
    result = report(db)
    assert result["status"] == "sufficient" and result["context_count"] == 3
    assert result["mastery"] == pytest.approx(2 / 3)
    assert result["exclusions"] == {"repeated_position": 1}
    assert set(result["supporting_evidence_ids"]) == {failure, unique, game_evidence}


def test_forged_evidence_subject_does_not_inherit_another_learners_completion():
    db = Database(":memory:")
    db.initialize()
    evidence = make_attempt(db, 1)
    db.connection.execute('UPDATE evidence_mappings SET subject="another" WHERE id=?', (evidence,))
    db.connection.commit()
    result = mastery_report(db, subject="another", as_of=datetime.now(UTC) + timedelta(seconds=1))[
        0
    ]
    assert result["status"] == "insufficient" and result["context_count"] == 0
    assert result["exclusions"] == {"invalid_training_lineage": 1}


def test_missing_training_attempt_foreign_key_is_not_evidence():
    db = Database(":memory:")
    db.initialize()
    make_attempt(db, 1)
    db.connection.execute("PRAGMA foreign_keys = OFF")
    db.connection.execute("DELETE FROM training_attempts")
    db.connection.commit()
    db.connection.execute("PRAGMA foreign_keys = ON")
    result = report(db)
    assert result["context_count"] == 0
    assert result["exclusions"] == {"invalid_training_lineage": 1}


def test_unsupported_task_produces_no_mastery_evidence():
    db = Database(":memory:")
    db.initialize()
    assert make_attempt(db, 1, skill="fork") is None
    assert mastery_report(db, subject="learner") == []


def test_previous_mapper_version_accepts_only_independently_verified_mate(monkeypatch):
    from chess_coach import training_feedback_storage

    db = Database(":memory:")
    db.initialize()
    monkeypatch.setattr(training_feedback_storage, "MAPPER_VERSION", "verified-puzzle-mate-v1")
    evidence = make_attempt(db, 1)
    result = report(db)
    assert result["context_count"] == 1 and result["supporting_evidence_ids"] == [evidence]


def test_malformed_session_identity_fails_closed():
    db = Database(":memory:")
    db.initialize()
    make_attempt(db, 1)
    db.connection.execute("DROP TRIGGER puzzle_session_snapshot_no_update")
    db.connection.execute("DROP TRIGGER completed_puzzle_no_update")
    db.connection.execute("UPDATE puzzle_sessions SET corpus_version=?", (b"invalid",))
    db.connection.commit()
    assert report(db)["exclusions"] == {"invalid_training_lineage": 1}
