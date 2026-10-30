"""Synthetic coverage of staged corpus visibility, recovery and provenance."""

import csv
import hashlib
import sqlite3

import pytest

from chess_coach.curriculum_cursor import revision
from chess_coach.curriculum_prompt_reference import referenced_prompt
from chess_coach.curriculum_query import corpus_status
from chess_coach.curriculum_reference import referenced_candidate
from chess_coach.db import Database
from chess_coach.puzzle_import import stage_puzzles
from chess_coach.puzzle_import_report import corpus_report
from chess_coach.puzzle_query import query_puzzles
from chess_coach.puzzle_sessions import start_attempt
from chess_coach.puzzles import import_puzzles
from chess_coach.training_feedback import puzzle_training_ref

FEN = "6k1/8/6K1/2Q5/8/8/8/8 b - - 0 1"
FIELDS = [
    "PuzzleId",
    "FEN",
    "Moves",
    "Rating",
    "RatingDeviation",
    "Popularity",
    "NbPlays",
    "Themes",
    "GameUrl",
    "OpeningTags",
]


def fixture_csv(path, ids=("p1", "p2", "p3"), *, invalid=()):
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(FIELDS)
        for i, name in enumerate(ids):
            writer.writerow(
                [
                    name,
                    "bad" if name in invalid else FEN,
                    "g8h8 c5f8",
                    1200 + i,
                    80,
                    90,
                    12,
                    "mate mateIn1",
                    "https://example.invalid/game,synthetic\nline",
                    "Italian_Game",
                ]
            )
    return hashlib.sha256(path.read_bytes()).hexdigest()


def db_at(root):
    db = Database(root / "coach.sqlite")
    db.initialize()
    return db


def stage(db, path, digest, **kwargs):
    kwargs.setdefault("min_free_bytes", 0)
    return stage_puzzles(
        db,
        path,
        project_root=path.parent,
        version="bulk",
        csv_sha256=digest,
        archive_sha256="a" * 64,
        **kwargs,
    )


def test_staged_rows_hidden_resume_publish_once_and_reopen(tmp_path):
    path = tmp_path / "source.csv"
    digest = fixture_csv(path, invalid={"p2"})
    db = db_at(tmp_path)
    before = revision(db)
    first = stage(db, path, digest, max_rows=2, batch_size=1)
    assert first["state"] == "staging" and (first["accepted"], first["rejected"]) == (1, 1)
    assert first["csv_sha256"] == digest and first["archive_sha256"] == "a" * 64
    assert first["rejections"][0]["puzzle_id"] == "p2"
    assert revision(db) == before
    assert query_puzzles(db, version="bulk") == []
    assert corpus_status(db, "bulk")[0] == "unknown_corpus"
    ref = puzzle_training_ref("bulk", "p1")
    assert referenced_candidate(db, ref) is None and referenced_prompt(db, ref) is None
    with pytest.raises(ValueError, match="unknown versioned puzzle"):
        start_attempt(db, attempt_id="staged", version="bulk", puzzle_id="p1")
    db.close()
    db = db_at(tmp_path)
    assert revision(db) == before
    result = stage(db, path, digest, max_rows=0, batch_size=1)
    assert result["state"] == "ready" and (result["accepted"], result["rejected"]) == (2, 1)
    assert result["themes"] == {"mate": 2, "mateIn1": 2}
    assert revision(db) == before + 1
    row = db.connection.execute(
        "SELECT * FROM puzzles WHERE puzzle_id='p1' AND corpus_id=(SELECT id FROM puzzle_corpora WHERE version='bulk')"
    ).fetchone()
    assert row["prompt_turn"] == "white" and row["prompt_fen"].split()[1] == "w"
    assert row["popularity"] == 90 and row["play_count"] == 12
    assert row["rating_deviation"] == 80 and row["objective"] == "unknown"
    assert query_puzzles(db, version="bulk", theme="mateIn1")[0]["puzzle_id"] == "p1"
    page = query_puzzles(db, version="bulk", theme="mateIn1", limit=1)
    assert isinstance(page[0]["rating"], int) and isinstance(page[0]["puzzle_id"], str)
    next_page = query_puzzles(
        db,
        version="bulk",
        theme="mateIn1",
        limit=1,
        after_rating=page[0]["rating"],
        after_id=page[0]["puzzle_id"],
    )
    assert next_page[0]["puzzle_id"] == "p3"
    with pytest.raises(ValueError, match="keyset"):
        query_puzzles(db, version="bulk", offset=1001)
    assert (
        start_attempt(db, attempt_id="ready", version="bulk", puzzle_id="p1")["status"] == "active"
    )
    assert db.connection.execute("SELECT count(*) FROM evidence_mappings").fetchone()[0] == 0
    assert stage(db, path, digest)["state"] == "ready"
    assert revision(db) == before + 2  # starting the attempt is a separate source change
    with pytest.raises(sqlite3.IntegrityError, match="immutable"):
        db.connection.execute("UPDATE puzzles SET rating=99 WHERE puzzle_id='p1'")
    db.connection.rollback()
    assert import_puzzles(db, path, version="bulk") == 2


def test_failed_batch_rolls_back_checkpoint_and_retries(tmp_path, monkeypatch):
    from chess_coach import puzzle_import_store

    path = tmp_path / "source.csv"
    digest = fixture_csv(path)
    db = db_at(tmp_path)
    original = puzzle_import_store.insert_themes

    def fail(*args):
        raise RuntimeError("synthetic interruption")

    monkeypatch.setattr(puzzle_import_store, "insert_themes", fail)
    with pytest.raises(RuntimeError, match="synthetic interruption"):
        stage(db, path, digest, max_rows=1)
    status = corpus_report(db)[0]
    assert status["accepted"] == 0
    assert db.connection.execute("SELECT count(*) FROM puzzles").fetchone()[0] == 0
    monkeypatch.setattr(puzzle_import_store, "insert_themes", original)
    assert stage(db, path, digest, max_rows=0)["accepted"] == 3
