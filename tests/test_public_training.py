"""Licensed direct-prompt material remains explicit, bounded and immutable."""

import csv
import hashlib
import json
import sqlite3

import pytest

from chess_coach.db import Database
from chess_coach.public_training import import_collection
from chess_coach.public_training_query import collections, tasks
from chess_coach.public_training_query import task as get_task
from chess_coach.web import create_app

MATE = "7k/8/6K1/2Q5/8/8/8/8 w - - 1 2"


def file_set(root, *, rows=None, license="CC0-1.0", fmt="fen_csv", text=None):
    source = root / "collection.data"
    if text is None:
        with source.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow(["id", "fen", "objective", "lines"])
            for row in rows or []:
                writer.writerow([row[0], row[1], row[2], json.dumps(row[3])])
    else:
        source.write_text(text)
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    manifest = {
        "version": "fixture",
        "source_url": "https://example.invalid/source",
        "source_revision": "v1",
        "source_sha256": digest,
        "content_sha256": digest,
        "content_format": fmt,
        "license": license,
        "attribution": "Fixture author",
        "license_notice": "CC0 1.0 https://creativecommons.org/publicdomain/zero/1.0/",
    }
    file = root / "manifest.json"
    file.write_text(json.dumps(manifest))
    return source, file, manifest


def test_direct_prompt_alternatives_exclusions_export_and_private_view(tmp_path):
    rows = [
        ("mate", MATE, "checkmate", ["c5f8", "c5c8"]),
        ("bad", MATE, "checkmate", ["c5b5"]),
        ("unknown", MATE, "unverified_source", ["c5f8"]),
    ]
    path, manifest, metadata = file_set(tmp_path, rows=rows)
    db = Database(tmp_path / "coach.sqlite")
    db.initialize()
    result = import_collection(db, path, path, manifest, project_root=tmp_path)
    assert result == {"version": "fixture", "accepted": 1, "excluded": 2}
    task = tasks(db, "fixture")[0]
    assert task["prompt_fen"] == MATE
    assert task["lines"] == ["c5f8", "c5c8"]
    assert task["attribution"] == metadata["attribution"]
    assert task["license_notice"] == metadata["license_notice"]
    assert get_task(db, "fixture", "mate") == task
    assert get_task(db, "other", "mate") is None
    assert collections(db)[0]["excluded"] == 2
    with pytest.raises(sqlite3.IntegrityError, match="immutable"):
        db.connection.execute("UPDATE public_tasks SET prompt_fen=\u0027changed\u0027")
    db.connection.rollback()
    app = create_app(
        db_path=db.path,
        subject="learner",
        actor="operator",
        corpus="fixture",
        login="fixture",
        origin="https://coach.invalid",
    )
    client = app.test_client()
    assert client.get("/library", base_url="https://coach.invalid").status_code == 403
    response = client.get(
        "/library", base_url="https://coach.invalid", headers={"Tailscale-User-Login": "fixture"}
    )
    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert "<title>Library — Chess coach</title>" in page
    assert page.count("Licensed direct-prompt collections") == 1
    assert b"1 supported" in response.data and b"2 excluded" in response.data
    assert b"Fixture author" in response.data and b"mate" in response.data
    assert b"unsupported objective" in response.data
    assert b"invalid prompt or solution line" in response.data


def test_unlicensed_source_and_duplicate_ids_fail_atomically(tmp_path):
    rows = [("same", MATE, "checkmate", ["c5f8"]), ("same", MATE, "checkmate", ["c5c8"])]
    path, manifest, metadata = file_set(tmp_path, rows=rows, license="unknown")
    db = Database(tmp_path / "coach.sqlite")
    db.initialize()
    with pytest.raises(ValueError, match="license"):
        import_collection(db, path, path, manifest, project_root=tmp_path)
    manifest.write_text(json.dumps(metadata | {"license": "CC0-1.0"}))
    with pytest.raises(ValueError, match="duplicate"):
        import_collection(db, path, path, manifest, project_root=tmp_path)
    assert collections(db) == []
