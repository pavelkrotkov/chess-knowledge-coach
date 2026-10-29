"""Synthetic coverage of staged corpus visibility, recovery and provenance."""

import csv
import hashlib
import json
import multiprocessing
import sqlite3
import sys

import pytest

from chess_coach.cli import main
from chess_coach.curriculum_cursor import revision
from chess_coach.curriculum_prompt_reference import referenced_prompt
from chess_coach.curriculum_query import corpus_status
from chess_coach.curriculum_reference import referenced_candidate
from chess_coach.db import Database
from chess_coach.puzzle_import import stage_puzzles
from chess_coach.puzzle_import_lock import import_lock
from chess_coach.puzzle_import_report import corpus_report
from chess_coach.puzzle_query import _query, query_puzzles
from chess_coach.puzzle_sessions import start_attempt
from chess_coach.puzzles import import_puzzles
from chess_coach.training_feedback import puzzle_training_ref
from chess_coach.web import create_app

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


def test_changed_source_conflict_and_malformed_records_never_publish(tmp_path):
    path = tmp_path / "source.csv"
    digest = fixture_csv(path)
    db = db_at(tmp_path)
    stage(db, path, digest, max_rows=1)
    changed = tmp_path / "changed.csv"
    other = fixture_csv(changed, ids=("different",))
    with pytest.raises(ValueError):
        stage(db, changed, other)
    assert corpus_report(db)[0]["state"] == "staging"
    bad = tmp_path / "broken.csv"
    bad.write_text(
        ",".join(FIELDS)
        + "\n"
        + f"good,{FEN},g8h8 c5f8,1200,80,90,12,mate,,\n"
        + 'bad,"unterminated\n',
        encoding="utf-8",
    )
    bad_sha = hashlib.sha256(bad.read_bytes()).hexdigest()
    db2 = Database(tmp_path / "broken.sqlite")
    db2.initialize()
    stage(db2, bad, bad_sha, max_rows=1)
    with pytest.raises(ValueError, match="import stopped"):
        stage(db2, bad, bad_sha, max_rows=0)
    status = corpus_report(db2)[0]
    assert status["state"] == "failed" and status["accepted"] == 1 and status["error"]
    assert query_puzzles(db2, version="bulk") == []


def test_duplicate_puzzle_ids_are_not_silently_accepted(tmp_path):
    path = tmp_path / "source.csv"
    digest = fixture_csv(path, ids=("same", "same"))
    db = db_at(tmp_path)
    stage(db, path, digest, max_rows=1)
    with pytest.raises(ValueError, match="duplicate"):
        stage(db, path, digest, max_rows=0)
    assert corpus_report(db)[0]["state"] == "failed"
    assert query_puzzles(db, version="bulk") == []


def hold_lock(db_path, root, ready, done):
    with import_lock(db_path, root):
        ready.set()
        done.wait(10)


def test_import_lock_coordinates_processes(tmp_path):
    path = tmp_path / "coach.sqlite"
    db = Database(path)
    db.initialize()
    ready, done = multiprocessing.Event(), multiprocessing.Event()
    proc = multiprocessing.Process(target=hold_lock, args=(path, tmp_path, ready, done))
    proc.start()
    try:
        assert ready.wait(5)
        with pytest.raises(RuntimeError, match="already running"), import_lock(path, tmp_path):
            pass
    finally:
        done.set()
        proc.join(5)
    assert proc.exitcode == 0


def test_theme_query_uses_index_and_browser_status_is_private(tmp_path, monkeypatch, capsys):
    path = tmp_path / "source.csv"
    digest = fixture_csv(path)
    db = db_at(tmp_path)
    stage(db, path, digest, max_rows=0)
    query, params = _query(1, "ready", "mate", None, 0, None)
    plan = db.connection.execute(
        "EXPLAIN QUERY PLAN " + query + " LIMIT ?", [*params, 10]
    ).fetchall()
    assert any("idx_puzzle_themes_search" in row[3] for row in plan)
    monkeypatch.setattr(
        sys, "argv", ["chess-coach", "--db", str(tmp_path / "coach.sqlite"), "corpus-status"]
    )
    main()
    assert json.loads(capsys.readouterr().out)[0]["state"] == "ready"
    app = create_app(
        db_path=tmp_path / "coach.sqlite",
        subject="learner",
        actor="operator",
        corpus="bulk",
        login="fixture",
        origin="https://coach.invalid",
    )
    client = app.test_client()
    assert client.get("/library", base_url="https://coach.invalid").status_code == 403
    response = client.get(
        "/library", base_url="https://coach.invalid", headers={"Tailscale-User-Login": "fixture"}
    )
    assert response.status_code == 200 and response.headers["Cache-Control"] == "no-store"
    assert b"bulk" in response.data and b"mateIn1" in response.data


def crash_after_batch(db_path, root, path, digest):
    import os

    db = Database(db_path)
    db.initialize()
    stage(db, path, digest, max_rows=1, batch_size=1)
    os._exit(77)


def test_crash_restart_and_backup_during_staging(tmp_path):
    from chess_coach.recovery import backup_database

    path = tmp_path / "source.csv"
    digest = fixture_csv(path)
    db = db_at(tmp_path)
    proc = multiprocessing.Process(
        target=crash_after_batch, args=(tmp_path / "coach.sqlite", tmp_path, path, digest)
    )
    proc.start()
    proc.join(15)
    assert proc.exitcode == 77
    assert corpus_report(db)[0]["accepted"] == 1
    backup = tmp_path / "backup.sqlite"
    backup_database(tmp_path / "coach.sqlite", backup, project_root=tmp_path)
    restored = Database(backup)
    restored.initialize()
    assert corpus_status(restored, "bulk")[0] == "unknown_corpus"
    assert stage(restored, path, digest, max_rows=0)["accepted"] == 3
    assert corpus_status(restored, "bulk")[0] == "available"
    assert corpus_report(db)[0]["state"] == "staging"
    assert stage(db, path, digest, max_rows=0)["state"] == "ready"


def test_source_replacement_fails_closed_and_exact_restore_resumes(tmp_path):
    path = tmp_path / "source.csv"
    digest = fixture_csv(path)
    original = path.read_bytes()
    db = db_at(tmp_path)
    stage(db, path, digest, max_rows=1)
    path.write_text("changed\n", encoding="utf-8")
    with pytest.raises(ValueError, match="checksum"):
        stage(db, path, digest)
    assert corpus_report(db)[0]["state"] == "failed"
    assert query_puzzles(db, version="bulk") == []
    path.write_bytes(original)
    result = stage(db, path, digest, max_rows=0)
    assert result["state"] == "ready" and result["accepted"] == 3


def test_legacy_sessions_survive_new_import_and_wal(tmp_path):
    source = tmp_path / "legacy.csv"
    digest = fixture_csv(source, ids=("old",))
    db = db_at(tmp_path)
    assert import_puzzles(db, source, version="old") == 1
    assert corpus_report(db)[0]["state"] == "legacy_ready"
    assert (
        start_attempt(db, attempt_id="old-attempt", version="old", puzzle_id="old")["status"]
        == "active"
    )
    fresh = tmp_path / "new.csv"
    new_digest = fixture_csv(fresh, ids=("new",))
    result = stage(db, fresh, new_digest, max_rows=0, enable_wal=True)
    assert db.connection.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    assert result["state"] == "ready" and result["csv_sha256"] != digest
    assert (
        start_attempt(db, attempt_id="old-attempt", version="old", puzzle_id="old")["status"]
        == "active"
    )
    assert query_puzzles(db, version="old")[0]["puzzle_id"] == "old"


def test_black_prompt_orientation_and_material_features(tmp_path):
    path = tmp_path / "black.csv"
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(FIELDS)
        writer.writerow(
            [
                "black",
                "8/8/8/8/2q5/6k1/8/6K1 w - - 0 1",
                "g1h1 c4f1",
                1200,
                80,
                91,
                14,
                "mate mateIn1",
                "",
                "",
            ]
        )
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    db = db_at(tmp_path)
    result = stage(db, path, digest, max_rows=0)
    assert result["state"] == "ready"
    row = db.connection.execute(
        "SELECT prompt_fen,prompt_turn,prompt_material FROM puzzles"
    ).fetchone()
    assert row["prompt_turn"] == "black" and row["prompt_fen"].split()[1] == "b"
    assert row["prompt_material"] == "0,0,0,0,0,0,0,0,0,1"


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


def test_migration_rollback_from_real_v17_and_reopen(tmp_path, monkeypatch):
    from chess_coach import db_recent

    db = Database(tmp_path / "old.sqlite")
    with monkeypatch.context() as patch:
        patch.setattr(db_recent, "add_corpus_staging", lambda connection: None)
        patch.setattr(db_recent, "add_puzzle_selection", lambda connection: None)
        db.initialize()
    db.connection.execute("PRAGMA user_version=17")
    db.connection.execute(
        "INSERT INTO puzzle_corpora(version,source,checksum) VALUES('legacy','fixture','hash')"
    )
    db.connection.commit()
    original = db_recent.add_corpus_staging

    def fail(connection):
        original(connection)
        raise RuntimeError("synthetic migration failure")

    with monkeypatch.context() as patch:
        patch.setattr(db_recent, "add_corpus_staging", fail)
        with pytest.raises(RuntimeError, match="synthetic migration failure"):
            db.initialize()
    assert db.connection.execute("PRAGMA user_version").fetchone()[0] == 17
    assert "state" not in {
        row[1] for row in db.connection.execute("PRAGMA table_info(puzzle_corpora)")
    }
    db.initialize()
    assert db.connection.execute("PRAGMA user_version").fetchone()[0] == 27
    assert corpus_report(db)[0]["state"] == "legacy_ready"
    db.close()
    reopened = Database(tmp_path / "old.sqlite")
    reopened.initialize()
    assert reopened.connection.execute("PRAGMA user_version").fetchone()[0] == 27
    sql = reopened.connection.execute(
        "SELECT sql FROM sqlite_master WHERE type='trigger' AND name='curriculum_revision_puzzles_insert'"
    ).fetchone()[0]
    assert "legacy_ready" in sql and "state IN" in sql


def test_storage_reserve_failure_is_reported_and_resumable(tmp_path, monkeypatch):
    from chess_coach import puzzle_import_budget

    path = tmp_path / "source.csv"
    digest = fixture_csv(path)
    db = db_at(tmp_path)
    stage(db, path, digest, max_rows=1)
    original = puzzle_import_budget.shutil.disk_usage

    def no_space(directory):
        return type("Disk", (), {"free": 1})()

    monkeypatch.setattr(puzzle_import_budget.shutil, "disk_usage", no_space)
    with pytest.raises(ValueError, match="storage reserve"):
        stage(db, path, digest, max_rows=0, min_free_bytes=10)
    assert corpus_report(db)[0]["state"] == "failed"
    assert corpus_report(db)[0]["error"] == "project storage reserve reached"
    monkeypatch.setattr(puzzle_import_budget.shutil, "disk_usage", original)
    assert stage(db, path, digest, max_rows=0)["state"] == "ready"


def race_import(db_path, root, path, digest, start, outcomes):
    db = Database(db_path)
    db.initialize()
    start.wait(10)
    try:
        result = stage(db, path, digest, max_rows=0, batch_size=1)
        outcomes.put(result["state"])
    except RuntimeError:
        outcomes.put("locked")


def test_concurrent_publish_is_unique_and_idempotent(tmp_path):
    path = tmp_path / "source.csv"
    digest = fixture_csv(path, ids=tuple(f"p{i}" for i in range(30)))
    db = db_at(tmp_path)
    start, outcomes = multiprocessing.Event(), multiprocessing.Queue()
    workers = [
        multiprocessing.Process(
            target=race_import,
            args=(tmp_path / "coach.sqlite", tmp_path, path, digest, start, outcomes),
        )
        for _ in range(2)
    ]
    for worker in workers:
        worker.start()
    start.set()
    for worker in workers:
        worker.join(20)
        assert worker.exitcode == 0
    assert sorted([outcomes.get(timeout=2), outcomes.get(timeout=2)]) in (
        ["locked", "ready"],
        ["ready", "ready"],
    )
    assert corpus_report(db)[0]["accepted"] == 30
    assert db.connection.execute("SELECT count(*) FROM puzzles").fetchone()[0] == 30


def test_stage_cli_exposes_separate_snapshot_digests(tmp_path, monkeypatch, capsys):
    path = tmp_path / "source.csv"
    digest = fixture_csv(path, ids=("p1",))
    args = [
        "chess-coach",
        "--db",
        str(tmp_path / "coach.sqlite"),
        "stage-puzzles",
        str(path),
        "--project-root",
        str(tmp_path),
        "--version",
        "bulk",
        "--csv-sha256",
        digest,
        "--archive-sha256",
        "a" * 64,
        "--max-rows",
        "0",
        "--min-free-bytes",
        "0",
    ]
    monkeypatch.setattr(sys, "argv", args)
    main()
    result = json.loads(capsys.readouterr().out)
    assert result["state"] == "ready"
    assert result["csv_sha256"] == digest and result["archive_sha256"] == "a" * 64


def test_live_cursor_survives_staging_but_invalidates_on_publication(tmp_path):
    import chess

    from chess_coach.curriculum import daily_plan

    db = db_at(tmp_path)
    db.connection.execute(
        "INSERT INTO puzzle_corpora(version,source,checksum) VALUES('legacy','fixture','hash')"
    )
    db.connection.executemany(
        """INSERT INTO puzzles(puzzle_id,corpus_id,fen,source,solution,rating,rating_deviation,themes_json,objective)
        VALUES(?,1,?,'',?, ?,80,'[]','execute')""",
        [("bad", chess.STARTING_FEN, "e2e4 e7e5", 100), ("valid", FEN, "g8h8 c5f8", 200)],
    )
    db.connection.commit()
    page = daily_plan(db, subject="learner", corpus_version="legacy", scan_limit=1)
    cursor = page["next_cursor"]
    assert cursor
    path = tmp_path / "source.csv"
    digest = fixture_csv(path)
    stage(db, path, digest, max_rows=1, batch_size=1)
    continued = daily_plan(
        db, subject="learner", corpus_version="legacy", scan_limit=1, cursor=cursor
    )
    assert continued["items"][0]["puzzle_id"] == "valid"
    stage(db, path, digest, max_rows=0, batch_size=1)
    with pytest.raises(ValueError, match="sources changed"):
        daily_plan(db, subject="learner", corpus_version="legacy", scan_limit=1, cursor=cursor)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("Rating", str(2**63)),
        ("Rating", "-1"),
        ("RatingDeviation", str(2**63)),
        ("RatingDeviation", "-1"),
        ("NbPlays", str(2**63)),
        ("NbPlays", "-1"),
        ("Popularity", str(2**63)),
        ("Popularity", "101"),
        ("Popularity", "-101"),
    ],
)
def test_numeric_out_of_range_fails_without_publishing(tmp_path, field, value):
    path = tmp_path / "numbers.csv"
    valid = ["good", FEN, "g8h8 c5f8", "1200", "80", "90", "12", "mate", "", ""]
    invalid = valid.copy()
    invalid[0] = "invalid"
    invalid[FIELDS.index(field)] = value
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(FIELDS)
        writer.writerow(valid)
        writer.writerow(invalid)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    db = db_at(tmp_path)
    stage(db, path, digest, max_rows=1)
    with pytest.raises(ValueError, match="invalid numeric fields"):
        stage(db, path, digest, max_rows=0)
    report = corpus_report(db)[0]
    assert report["state"] == "failed" and report["accepted"] == 1
    assert report["error"] == "CSV record has invalid numeric fields"
    assert query_puzzles(db, version="bulk") == []
    with pytest.raises(ValueError, match="unknown versioned puzzle"):
        start_attempt(db, attempt_id="hidden", version="bulk", puzzle_id="good")


@pytest.mark.parametrize("popularity", [-100, 100])
def test_numeric_boundaries_fit_sqlite(tmp_path, popularity):
    path = tmp_path / "boundaries.csv"
    maximum = str(2**63 - 1)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(FIELDS)
        writer.writerow(
            ["edge", FEN, "g8h8 c5f8", maximum, maximum, popularity, maximum, "mate", "", ""]
        )
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    db = db_at(tmp_path)
    assert stage(db, path, digest, max_rows=0)["state"] == "ready"
    row = db.connection.execute(
        "SELECT rating,rating_deviation,play_count,popularity FROM puzzles"
    ).fetchone()
    assert tuple(row) == (2**63 - 1, 2**63 - 1, 2**63 - 1, popularity)
