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


def test_pgn_variations_and_malformed_game_quarantined(tmp_path):
    pgn = f"""[Event "fixture"]
[SetUp "1"]
[FEN "{MATE}"]
[TaskId "mate"]
[Objective "checkmate"]

1. Qf8# (1. Qc8#) *

[Event "broken"]
[TaskId "broken"]
[Objective "legal_line"]

1. e9 *
"""
    path, manifest, _ = file_set(tmp_path, fmt="pgn", text=pgn)
    db = Database(tmp_path / "coach.sqlite")
    db.initialize()
    result = import_collection(db, path, path, manifest, project_root=tmp_path)
    assert result["accepted"] == 1 and result["excluded"] == 1
    assert set(tasks(db, "fixture")[0]["lines"]) == {"c5f8", "c5c8"}


def test_v20_upgrade_is_atomic_and_keeps_legacy_data(tmp_path, monkeypatch):
    from chess_coach import db_recent

    db = Database(tmp_path / "old.sqlite")
    with monkeypatch.context() as patch:
        patch.setattr(db_recent, "add_public_training", lambda connection: None)
        db.initialize()
    db.connection.execute("PRAGMA user_version=20")
    db.connection.execute(
        "INSERT INTO puzzle_corpora(version,source,checksum) VALUES(\u0027old\u0027,\u0027fixture\u0027,\u0027hash\u0027)"
    )
    db.connection.commit()
    original = db_recent.add_public_training

    def fail(connection):
        original(connection)
        raise ValueError("synthetic migration failure")

    with monkeypatch.context() as patch:
        patch.setattr(db_recent, "add_public_training", fail)
        with pytest.raises(ValueError, match="synthetic migration failure"):
            db.initialize()
    assert db.connection.execute("PRAGMA user_version").fetchone()[0] == 20
    assert not db.connection.execute(
        "SELECT 1 FROM sqlite_master WHERE name=\u0027public_tasks\u0027"
    ).fetchone()
    db.initialize()
    assert db.connection.execute("PRAGMA user_version").fetchone()[0] == 29
    assert db.connection.execute("SELECT version FROM puzzle_corpora").fetchone()[0] == "old"


def test_mutated_source_is_never_published(tmp_path, monkeypatch):
    from chess_coach import public_training

    path, manifest, _ = file_set(tmp_path, rows=[("mate", MATE, "checkmate", ["c5f8"])])
    db = Database(tmp_path / "coach.sqlite")
    db.initialize()
    original = public_training.collect

    def mutate(*args):
        result = original(*args)
        path.write_text(path.read_text() + "\n")
        return result

    monkeypatch.setattr(public_training, "collect", mutate)
    with pytest.raises(ValueError, match="changed"):
        import_collection(db, path, path, manifest, project_root=tmp_path)
    assert collections(db) == []


def test_bad_mit_notice_is_not_redistributable(tmp_path):
    path, manifest, metadata = file_set(
        tmp_path, rows=[("mate", MATE, "checkmate", ["c5f8"])], license="MIT"
    )
    metadata["license_notice"] = "Copyright Example; permission granted"
    manifest.write_text(json.dumps(metadata))
    db = Database(tmp_path / "coach.sqlite")
    db.initialize()
    with pytest.raises(ValueError, match="MIT notice"):
        import_collection(db, path, path, manifest, project_root=tmp_path)
    assert collections(db) == []


def test_all_unsupported_records_remain_visible_as_exclusions(tmp_path):
    path, manifest, _ = file_set(tmp_path, rows=[("u", MATE, "unverified_source", ["c5f8"])])
    db = Database(tmp_path / "coach.sqlite")
    db.initialize()
    result = import_collection(db, path, path, manifest, project_root=tmp_path)
    assert result["accepted"] == 0 and result["excluded"] == 1
    assert collections(db)[0]["excluded"] == 1
    assert tasks(db, "fixture") == []
    with pytest.raises(sqlite3.IntegrityError):
        import_collection(db, path, path, manifest, project_root=tmp_path)
    assert collections(db)[0]["excluded"] == 1


def test_pgn_rejects_unconsumed_tokens_after_and_between_valid_moves(tmp_path):
    pgn = """[TaskId "valid"]
[Objective "legal_line"]

1. e4 {multi-line comment

continues} e5 $1 (1... c5 {variation}) 2. Nf3!? *

[TaskId "prefix"]
[Objective "legal_line"]

nonsense 1. d4 *

[TaskId "middle"]
[Objective "legal_line"]

1. e4 e9 e5 *

[TaskId "trailing"]
[Objective "legal_line"]

1. e4 e9 *
"""
    path, manifest, _ = file_set(tmp_path, fmt="pgn", text=pgn)
    db = Database(tmp_path / "strict.sqlite")
    db.initialize()
    result = import_collection(db, path, path, manifest, project_root=tmp_path)
    assert result["accepted"] == 1 and result["excluded"] == 3
    result_tasks = tasks(db, "fixture")
    assert len(result_tasks) == 1 and result_tasks[0]["task_id"] == "valid"
    assert set(result_tasks[0]["lines"]) == {"e2e4 e7e5 g1f3", "e2e4 c7c5"}


@pytest.mark.parametrize(
    "movetext",
    ["1. e4e9 *", "1. e4 $x *", "1. e4 (1. d4 *", "1. e4 {unterminated", "1. e4 * garbage"],
)
def test_pgn_lexical_boundary_rejects_partial_or_unbalanced_text(movetext):
    from chess_coach.public_training_pgn_lex import valid_movetext

    assert not valid_movetext(movetext)
