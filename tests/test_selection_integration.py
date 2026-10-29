"""Durable selection identity, publication and private display."""

import csv
import hashlib
import json
import sqlite3
import sys

import pytest

from chess_coach.cli import main
from chess_coach.db import Database
from chess_coach.puzzle_import import stage_puzzles
from chess_coach.puzzle_import_report import corpus_report
from chess_coach.puzzle_query import query_puzzles
from chess_coach.recovery import backup_database, restore_database
from chess_coach.web import create_app

FEN = "6k1/8/6K1/2Q5/8/8/8/8 b - - 0 1"


def source(root, *, selected=3):
    path = root / "source.csv"
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["PuzzleId", "FEN", "Moves", "Rating", "RatingDeviation", "Themes"])
        for name in ("p1", "p2", "p3"):
            writer.writerow([name, FEN, "g8h8 c5f8", 1200, 80, "mate mateIn1"])
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    metadata = {
        "policy": "source_order_prefix",
        "fullsource_count": 100,
        "selected_count": selected,
        "parent_csv_sha256": "a" * 64,
        "parent_archive_sha256": "b" * 64,
        "derived_csv_sha256": digest,
        "representative": False,
    }
    manifest = root / "selection.json"
    manifest.write_text(json.dumps(metadata))
    return path, digest, manifest, metadata


def stage(db, root, path, digest, manifest, max_rows):
    return stage_puzzles(
        db,
        path,
        project_root=root,
        version="prefix",
        csv_sha256=digest,
        archive_sha256="b" * 64,
        selection_manifest=manifest,
        min_free_bytes=0,
        max_rows=max_rows,
        batch_size=1,
    )


def test_manifest_survives_backup_resume_and_private_views(tmp_path, monkeypatch, capsys):
    path, digest, manifest, metadata = source(tmp_path)
    db = Database(tmp_path / "coach.sqlite")
    db.initialize()
    first = stage(db, tmp_path, path, digest, manifest, 1)
    assert first["state"] == "staging" and first["selection"] == metadata
    assert query_puzzles(db, version="prefix") == []
    manifest.write_text(json.dumps(metadata | {"fullsource_count": 101}))
    with pytest.raises(ValueError, match="different source or import identity"):
        stage(db, tmp_path, path, digest, manifest, 1)
    manifest.write_text(json.dumps(metadata))
    backup_database(db.path, tmp_path / "backup.sqlite", project_root=tmp_path)
    restore_database(
        tmp_path / "backup.sqlite", tmp_path / "restored.sqlite", project_root=tmp_path
    )
    restored = Database(tmp_path / "restored.sqlite")
    restored.initialize()
    assert corpus_report(restored)[0]["selection"] == metadata
    result = stage(restored, tmp_path, path, digest, manifest, 0)
    assert result["state"] == "ready" and result["accepted"] == 3
    assert len(query_puzzles(restored, version="prefix")) == 3
    with pytest.raises(sqlite3.IntegrityError, match="immutable"):
        restored.connection.execute("UPDATE puzzle_imports SET selection_json=NULL")
    restored.connection.rollback()
    monkeypatch.setattr(sys, "argv", ["chess-coach", "--db", str(restored.path), "corpus-status"])
    main()
    assert json.loads(capsys.readouterr().out)[0]["selection"] == metadata
    app = create_app(
        db_path=restored.path,
        subject="learner",
        actor="operator",
        corpus="prefix",
        login="fixture",
        origin="https://coach.invalid",
    )
    response = app.test_client().get(
        "/library", base_url="https://coach.invalid", headers={"Tailscale-User-Login": "fixture"}
    )
    assert response.status_code == 200
    assert b"3 of 100 source records" in response.data
    assert b"not representative" in response.data


def test_declared_count_mismatch_fails_and_stays_hidden(tmp_path):
    path, digest, manifest, _ = source(tmp_path, selected=4)
    db = Database(tmp_path / "coach.sqlite")
    db.initialize()
    with pytest.raises(ValueError, match="corpus import stopped"):
        stage(db, tmp_path, path, digest, manifest, 0)
    assert corpus_report(db)[0]["state"] == "failed"
    assert query_puzzles(db, version="prefix") == []


def test_v19_upgrade_preserves_legacy_and_rolls_back_failure(tmp_path, monkeypatch):
    from chess_coach import db_recent

    db = Database(tmp_path / "old.sqlite")
    db.initialize()
    db.connection.execute("ALTER TABLE puzzle_imports DROP COLUMN selection_json")
    db.connection.execute("PRAGMA user_version=19")
    db.connection.execute(
        "INSERT INTO puzzle_corpora(version,source,checksum) VALUES(\u0027legacy\u0027,\u0027fixture\u0027,\u0027hash\u0027)"
    )
    db.connection.commit()
    original = db_recent.add_puzzle_selection

    def fail(connection):
        original(connection)
        raise ValueError("synthetic migration failure")

    with monkeypatch.context() as patch:
        patch.setattr(db_recent, "add_puzzle_selection", fail)
        with pytest.raises(ValueError, match="synthetic migration failure"):
            db.initialize()
    assert db.connection.execute("PRAGMA user_version").fetchone()[0] == 19
    assert "selection_json" not in {
        row[1] for row in db.connection.execute("PRAGMA table_info(puzzle_imports)")
    }
    db.initialize()
    db.initialize()
    assert db.connection.execute("PRAGMA user_version").fetchone()[0] == 23
    assert corpus_report(db)[0]["selection"] is None


def test_cli_stages_selection_and_rejects_outside_manifest(tmp_path, monkeypatch, capsys):
    path, digest, manifest, metadata = source(tmp_path)
    args = [
        "chess-coach",
        "--db",
        str(tmp_path / "cli.sqlite"),
        "stage-puzzles",
        str(path),
        "--project-root",
        str(tmp_path),
        "--version",
        "prefix",
        "--csv-sha256",
        digest,
        "--archive-sha256",
        "b" * 64,
        "--selection-manifest",
        str(manifest),
        "--min-free-bytes",
        "0",
        "--max-rows",
        "1",
    ]
    monkeypatch.setattr(sys, "argv", args)
    main()
    result = json.loads(capsys.readouterr().out)
    assert result["selection"] == metadata and result["state"] == "staging"
    outside = tmp_path.parent / "outside-selection-test.json"
    outside.write_text(json.dumps(metadata))
    args[args.index(str(manifest))] = str(outside)
    with pytest.raises(ValueError, match="inside the project"):
        main()


def test_invalid_or_oversized_manifest_is_rejected(tmp_path):
    path, digest, manifest, _ = source(tmp_path)
    db = Database(tmp_path / "coach.sqlite")
    db.initialize()
    manifest.write_text("{" + " " * 8192)
    with pytest.raises(ValueError, match="too large"):
        stage(db, tmp_path, path, digest, manifest, 0)
    manifest.write_text("not json")
    with pytest.raises(ValueError, match="invalid"):
        stage(db, tmp_path, path, digest, manifest, 0)
    assert corpus_report(db) == []
