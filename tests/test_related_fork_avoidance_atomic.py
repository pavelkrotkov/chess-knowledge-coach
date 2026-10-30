"""Atomic admission and public source freshness for created-fork practice."""

import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest

from chess_coach.db import Database
from chess_coach.puzzle_session_validate import validate_line
from chess_coach.related_fork_avoidance import preview
from chess_coach.related_fork_avoidance_start import start_related
from chess_coach.unified_session_events import show
from tests.test_fork_defense_pipeline import LEARNER
from tests.test_related_fork_avoidance import PRE, created_fixture


def test_two_concurrent_starts_admit_at_most_one_familiar_prompt(tmp_path, monkeypatch):
    path = tmp_path / "atomic.sqlite"
    db, evidence = created_fixture(path, monkeypatch)
    reference = preview(db, LEARNER, evidence, "test")["items"][0]["reference"]
    db.close()
    barrier = Barrier(2)

    def start(attempt):
        session = Database(path)
        try:
            barrier.wait(timeout=5)
            start_related(
                session,
                attempt_id=attempt,
                subject=LEARNER,
                evidence_id=evidence,
                corpus_version="test",
                reference=reference,
            )
            return "started"
        except ValueError:
            return "stale"
        finally:
            session.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(start, ["a", "b"]))
    assert sorted(results) == ["stale", "started"]
    db = Database(path)
    assert db.connection.execute("SELECT COUNT(*) FROM unified_sessions").fetchone()[0] == 1
    db.close()


def test_public_license_change_invalidates_session(tmp_path, monkeypatch):
    db, evidence = created_fixture(tmp_path / "public.sqlite", monkeypatch)
    db.connection.execute("""INSERT INTO public_collections(version,source_url,source_revision,source_sha256,
        content_sha256,content_format,license,attribution,license_notice,accepted,excluded,state)
        VALUES('public-fixture','https://example.invalid','v1','a','b','fen_csv','CC0-1.0','fixture','notice',1,0,'staging')""")
    collection = db.connection.execute(
        "SELECT id FROM public_collections WHERE version='public-fixture'"
    ).fetchone()[0]
    pre = PRE.replace("P6P", "P2P3P")
    prompt = validate_line(pre, "g7g6 b1b3 h8g8 e1f1")
    db.connection.execute(
        "INSERT INTO public_tasks VALUES(?,?,?,?,?)",
        (collection, "fixture", prompt, "legal_line", json.dumps(["b1b3 h8g8 e1f1"])),
    )
    db.connection.execute("UPDATE public_collections SET state='ready' WHERE id=?", (collection,))
    db.connection.commit()
    item = next(
        item for item in preview(db, LEARNER, evidence, "test")["items"] if item["type"] == "public"
    )
    start_related(
        db,
        attempt_id="public",
        subject=LEARNER,
        evidence_id=evidence,
        corpus_version="test",
        reference=item["reference"],
    )
    with pytest.raises(sqlite3.IntegrityError, match="immutable"):
        db.connection.execute(
            "UPDATE public_collections SET license='changed' WHERE id=?", (collection,)
        )
    db.connection.rollback()
    db.connection.execute("DROP TRIGGER immutable_update_public_collections")
    db.connection.execute(
        "UPDATE public_collections SET license='changed' WHERE id=?", (collection,)
    )
    db.connection.commit()
    with pytest.raises(ValueError, match=r"stale|unavailable"):
        show(db, "public", LEARNER)
    db.close()
