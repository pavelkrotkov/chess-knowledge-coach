"""Private browser security and real review-to-practice flow."""

import re
from pathlib import Path
from typing import Any, cast

import chess
import chess.pgn
import pytest

from chess_coach.db import Database
from chess_coach.evidence_review import review_evidence
from chess_coach.ingest import ingest_pgn
from chess_coach.tactical_opportunities import record_game_opportunities
from chess_coach.web import create_app

ORIGIN = "https://coach.invalid"
LOGIN = "fixture-login"
HEADERS = {"Tailscale-User-Login": LOGIN}
FEN = "6k1/8/6K1/2Q5/8/8/8/8 b - - 0 1"


@pytest.fixture
def setup(tmp_path):
    path = tmp_path / "coach.sqlite"
    db = Database(path)
    db.initialize()
    db.connection.execute(
        "INSERT INTO puzzle_corpora(version,source,checksum) VALUES('fixture-v1','fixture','hash')"
    )
    db.connection.execute(
        """INSERT INTO puzzles(puzzle_id,corpus_id,fen,source,solution,rating,
        rating_deviation,themes_json,objective)
        VALUES ('puzzle',1,?,'','g8h8 c5f8',500,80,'[]','execute')""",
        (FEN,),
    )
    db.connection.commit()
    game = chess.pgn.Game()
    board = chess.Board("8/8/8/8/4Q3/2K5/8/2k5 w - - 0 1")
    game.setup(board)
    game.headers["White"] = "Learner"
    game.headers["Black"] = "Opponent"
    game.add_variation(board.parse_uci("e4d3"))
    ingest_pgn(db, str(game))
    game_id = db.connection.execute("SELECT MAX(id) FROM games").fetchone()[0]
    results = record_game_opportunities(db, game_id, learner="learner")
    evidence_id = cast(list[int], results[0]["evidence_ids"])[0]
    db.close()
    app = create_app(
        db_path=path,
        subject="learner",
        actor="fixture-reviewer",
        corpus="fixture-v1",
        login=LOGIN,
        origin=ORIGIN,
    )
    app.testing = True
    return path, app, evidence_id


def token(response, name="csrf"):
    match = re.search(rb'name="' + name.encode() + rb'" value="([^"]+)"', response.data)
    assert match
    return match.group(1).decode()


def post(client, path, csrf, **values):
    return client.post(
        path, base_url=ORIGIN, headers={**HEADERS, "Origin": ORIGIN}, data={"csrf": csrf, **values}
    )


def test_private_access_and_csrf(setup, tmp_path, monkeypatch):
    path, app, evidence_id = setup
    client = app.test_client()
    assert client.get("/", base_url=ORIGIN).status_code == 403
    assert (
        client.get("/", base_url=ORIGIN, headers={"Tailscale-User-Login": "other"}).status_code
        == 403
    )
    assert client.get("/", base_url="https://other.invalid", headers=HEADERS).status_code == 403
    page = client.get(f"/evidence/{evidence_id}", base_url=ORIGIN, headers=HEADERS)
    assert page.status_code == 200
    cookie = page.headers["Set-Cookie"]
    assert cookie.startswith("__Host-chess_coach_session=")
    assert "Secure" in cookie and "HttpOnly" in cookie and "SameSite=Strict" in cookie
    assert "Path=/" in cookie and "Domain=" not in cookie
    assert page.headers["Cache-Control"] == "no-store"
    assert page.headers["Referrer-Policy"] == "same-origin"
    csrf = token(page)
    endpoint = f"/evidence/{evidence_id}/review"
    assert (
        client.post(
            endpoint, base_url=ORIGIN, headers=HEADERS, data={"csrf": csrf, "decision": "accept"}
        ).status_code
        == 403
    )
    assert (
        client.post(
            endpoint,
            base_url=ORIGIN,
            headers={**HEADERS, "Origin": "https://other.invalid"},
            data={"csrf": csrf, "decision": "accept"},
        ).status_code
        == 403
    )
    assert (
        client.post(
            endpoint,
            base_url=ORIGIN,
            headers={**HEADERS, "Origin": "null"},
            data={"csrf": csrf, "decision": "accept"},
        ).status_code
        == 403
    )
    assert post(client, endpoint, "wrong", decision="accept").status_code == 403
    db = Database(path)
    assert db.connection.execute("SELECT COUNT(*) FROM evidence_review_events").fetchone()[0] == 0
    db.close()

    # A separately attested legacy DB remains schema 32 for browser and inline writes.
    import sqlite3

    from chess_coach import schema_compat_identity
    from chess_coach.fact_runs import record_fact_run
    from chess_coach.schema_compat import attest
    from chess_coach.schema_compat_layout import TABLES, VIEWS

    root = tmp_path / "compat"
    data = root / ".runtime" / "data"
    data.mkdir(parents=True)
    (root / ".runtime" / "planning").mkdir(mode=0o700)
    legacy = data / "legacy.sqlite"
    source = sqlite3.connect(path)
    destination = sqlite3.connect(legacy)
    source.backup(destination)
    source.close()
    destination.execute("PRAGMA foreign_keys=OFF")
    for name in VIEWS:
        destination.execute(f"DROP VIEW {name}")
    for name in TABLES:
        destination.execute(f"DROP TABLE {name}")
    destination.execute("DROP INDEX IF EXISTS idx_engine_outputs_position_id")
    destination.execute("DROP INDEX IF EXISTS idx_curriculum_capture_due")
    destination.execute("DROP INDEX IF EXISTS idx_curriculum_capture_scheduled")
    destination.execute("DROP INDEX IF EXISTS idx_curriculum_fork_due")
    destination.execute("DROP INDEX IF EXISTS idx_curriculum_fork_scheduled")
    destination.execute("DROP INDEX IF EXISTS idx_curriculum_unified_due")
    destination.execute("DROP INDEX IF EXISTS idx_curriculum_unified_scheduled")
    destination.execute("DROP TRIGGER IF EXISTS unified_completed_training_attempt_no_update")
    destination.execute("DROP TRIGGER IF EXISTS unified_completed_session_no_update")
    destination.execute("PRAGMA user_version=32")
    destination.execute(
        "INSERT INTO puzzle_corpora(version,source,checksum,state) VALUES('compat-mate','fixture','hash','staging')"
    )
    destination.execute("""INSERT INTO puzzles(puzzle_id,corpus_id,fen,source,solution,rating,
        rating_deviation,themes_json,objective) VALUES('mate',(SELECT id FROM puzzle_corpora WHERE version='compat-mate'),
        '7k/1p6/6K1/2Q5/8/8/8/8 b - - 17 14','fixture','b7b6 c5f8',1200,80,'[]','unknown')""")
    destination.execute("UPDATE puzzle_corpora SET state='ready' WHERE version='compat-mate'")
    destination.execute(
        "INSERT INTO analysis_runs(game_id,engine,engine_version,config_json) "
        "VALUES(1,'fixture','v1','{}')"
    )
    destination.commit()
    # A large but valid inline value must not be loaded merely to test emptiness.
    from chess_coach.schema_compat_scan import inspect

    destination.execute("UPDATE analysis_runs SET config_json=? WHERE id=1", ("x" * 131072,))
    destination.execute("UPDATE detector_runs SET input_json=? WHERE id=1", ("x" * 131072,))
    destination.execute("UPDATE mapping_runs SET input_json=? WHERE id=1", ("x" * 131072,))
    old_limit = destination.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, 65536)
    try:
        assert inspect(destination) == destination.execute("PRAGMA schema_version").fetchone()[0]
        for column in ("nnue", "compatibility_json"):
            destination.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, old_limit)
            destination.execute(
                "UPDATE analysis_runs SET config_json=?,nnue=?,compatibility_json=? WHERE id=1",
                ("", "", ""),
            )
            destination.execute(f"UPDATE analysis_runs SET {column}=? WHERE id=1", ("x" * 131072,))
            destination.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, 65536)
            inspect(destination)
    finally:
        destination.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, old_limit)
    destination.execute(
        "UPDATE analysis_runs SET config_json=?,nnue=?,compatibility_json=? WHERE id=1",
        ("\x00", "", ""),
    )
    for table in ("detector_runs", "mapping_runs"):
        assert (
            destination.execute(f"UPDATE {table} SET input_json=? WHERE id=1", ("\x00",)).rowcount
            == 1
        )
    inspect(destination)  # Embedded NUL is nonempty text.
    for table in ("detector_runs", "mapping_runs"):
        for value in ("", b"non-text"):
            destination.execute(f"UPDATE {table} SET input_json=? WHERE id=1", (value,))
            with pytest.raises(ValueError, match="representation"):
                inspect(destination)
        destination.execute(f"UPDATE {table} SET input_json=? WHERE id=1", ("ok",))
    destination.execute(
        "UPDATE analysis_runs SET config_json=?,nnue=?,compatibility_json=? WHERE id=1",
        ("", "", ""),
    )
    with pytest.raises(ValueError, match="representation"):
        inspect(destination)
    destination.execute("UPDATE analysis_runs SET config_json=? WHERE id=1", (b"non-text",))
    with pytest.raises(ValueError, match="representation"):
        inspect(destination)
    destination.rollback()
    destination.close()
    monkeypatch.setenv("CHESS_PROJECT_ROOT", str(root))
    monkeypatch.setenv("CHESS_DB", str(legacy))
    monkeypatch.setenv("CHESS_SUBJECT", "learner")
    monkeypatch.setenv("CHESS_SCHEMA_COMPAT", "32")
    monkeypatch.setattr(
        schema_compat_identity,
        "release_info",
        lambda: {
            "commit": "a" * 40,
            "module_path": str(root / ".runtime" / "releases" / ("a" * 40) / "module.py"),
        },
    )
    read = sqlite3.connect(legacy.as_uri() + "?mode=ro", uri=True)
    read.execute("PRAGMA query_only=ON")
    from chess_coach import db_recent

    def newer_migration(_connection):
        raise AssertionError("future migration used by legacy preflight")

    with monkeypatch.context() as preflight:
        preflight.setattr(db_recent, "add_digest_storage", newer_migration)
        preflight.setattr(db_recent, "add_engine_output_position_index", newer_migration)
        preflight.setattr(db_recent, "add_unified_training", newer_migration)
        preflight.setattr(db_recent, "add_tactical_exposure", newer_migration)
        preflight.setattr(db_recent, "add_capture_indexes", newer_migration)
        preflight.setattr(db_recent, "add_fork_indexes", newer_migration)
        attest(legacy, read)
    read.close()

    # The standalone entry point must honor the same selected schema-32 profile.
    import contextlib
    import io
    import json
    import sys

    from chess_coach import cli
    from chess_coach.db_versioning import CURRENT_VERSION

    def cli_run(target, *arguments, override=None):
        with monkeypatch.context() as patch, contextlib.redirect_stdout(io.StringIO()) as out:
            patch.setattr(sys, "argv", ["chess-coach", "--db", str(target), *arguments])
            if override is None:
                cli.main()
            else:
                cli.main(compatibility=override)
        return json.loads(out.getvalue())

    def legacy_state(path):
        connection = sqlite3.connect(path)
        try:
            return (
                connection.execute("PRAGMA user_version").fetchone()[0],
                connection.execute("PRAGMA schema_version").fetchone()[0],
                connection.execute(
                    "SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name"
                ).fetchall(),
                connection.execute(
                    "SELECT id,typeof(pgn),pgn,typeof(source_id),source_id FROM games ORDER BY id"
                ).fetchall(),
                connection.execute(
                    "SELECT id,typeof(config_json),config_json,typeof(nnue),nnue,typeof(compatibility_json),compatibility_json FROM analysis_runs ORDER BY id"
                ).fetchall(),
                connection.execute(
                    "SELECT id,typeof(input_json),input_json,typeof(input_hash),input_hash FROM detector_runs ORDER BY id"
                ).fetchall(),
                connection.execute(
                    "SELECT id,typeof(input_json),input_json,typeof(output_hash),output_hash FROM mapping_runs ORDER BY id"
                ).fetchall(),
            )
        finally:
            connection.close()

    baseline = legacy_state(legacy)
    assert baseline[0] == 32
    report = cli_run(
        legacy,
        "style-choices",
        "--learner",
        "learner",
        "--protection-evidence",
        "1",
        "--response",
        "c1c4",
    )
    assert report["status"] == "unknown"
    assert legacy_state(legacy) == baseline
    cli_run(legacy, "evidence-report", override=True)
    assert legacy_state(legacy) == baseline

    # A stale release attestation or malformed profile fails before initialization.
    with monkeypatch.context() as patch:
        patch.setattr(
            schema_compat_identity,
            "release_info",
            lambda: {
                "commit": "b" * 40,
                "module_path": str(root / ".runtime" / "releases" / ("b" * 40) / "module.py"),
            },
        )
        with pytest.raises(ValueError, match="attestation"):
            cli_run(legacy, "evidence-report")
    with monkeypatch.context() as patch:
        patch.setenv("CHESS_SCHEMA_COMPAT", "invalid")
        with pytest.raises(ValueError, match="unsupported"):
            cli_run(legacy, "evidence-report")
        missing = root / "unrelated.sqlite"
        cli_run(missing, "capabilities")
        cli_run(missing, "competencies")
        assert cli_run(missing, "acquisition-status", "--project-root", str(root)) == []
        destination = root / "check-only-backup.sqlite"
        assert isinstance(
            cli_run(
                missing,
                "backup-db",
                str(legacy),
                str(destination),
                "--project-root",
                str(root),
                "--check-only",
            ),
            dict,
        )
        assert not missing.exists() and not destination.exists()
    assert legacy_state(legacy) == baseline

    # A selected profile for one file cannot silently migrate a different file.
    wrong = data / "other.sqlite"
    source = sqlite3.connect(legacy)
    destination = sqlite3.connect(wrong)
    source.backup(destination)
    source.close()
    destination.close()
    wrong_before = legacy_state(wrong)
    with pytest.raises(ValueError, match="differs"):
        cli_run(wrong, "evidence-report")
    assert legacy_state(wrong) == wrong_before
    cli_run(wrong, "evidence-report", override=False)
    assert legacy_state(wrong)[0] == CURRENT_VERSION

    # With no profile, ordinary CLI startup still initializes a native database.
    native = data / "native.sqlite"
    with monkeypatch.context() as patch:
        patch.delenv("CHESS_SCHEMA_COMPAT")
        cli_run(native, "evidence-report")
    assert legacy_state(native)[0] == CURRENT_VERSION
    cli_run(legacy, "seed-competencies")
    assert legacy_state(legacy) == baseline

    compat_app = create_app(
        db_path=legacy,
        subject="learner",
        actor="fixture",
        corpus="fixture-v1",
        login=LOGIN,
        origin=ORIGIN,
        compatibility=True,
    )
    capture_page = compat_app.test_client().get(
        "/library?family=capture", base_url=ORIGIN, headers=HEADERS
    )
    assert capture_page.status_code == 200
    page = compat_app.test_client().get(
        f"/evidence/{evidence_id}", base_url=ORIGIN, headers=HEADERS
    )
    assert page.status_code == 200 and b"Chess position" in page.data
    compat_db = Database(legacy, compatibility=True)
    before = compat_db.connection.execute("PRAGMA schema_version").fetchone()[0]
    plan = compat_db.connection.execute(
        "EXPLAIN QUERY PLAN SELECT input_json FROM detector_runs_read "
        "WHERE producer=? AND position_id=? AND status='active'",
        ("mate-in-one", 1),
    ).fetchall()
    assert any("idx_detector_run_active" in row[3] for row in plan)
    compat_db.initialize()
    assert (
        compat_db.connection.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE name IN "
            "('idx_curriculum_fork_due', 'idx_curriculum_fork_scheduled')"
        ).fetchone()[0]
        == 0
    )
    from chess_coach.opening_profile_cli_db import open_database

    read_only, selected_database = open_database(root)
    assert selected_database == legacy
    assert read_only.execute("PRAGMA query_only").fetchone()[0] == 1
    assert read_only.execute("PRAGMA user_version").fetchone()[0] == 32
    with pytest.raises(sqlite3.OperationalError):
        read_only.execute("CREATE TABLE forbidden_write(id INTEGER)")
    read_only.close()
    from chess_coach.course_pgn import chapter as make_chapter

    snapshot = {"prompt_fen": chess.STARTING_FEN, "learner_color": "white", "lines": ["e2e4"]}
    worked = make_chapter("Synthetic", "Worked example", snapshot, {})
    offered = {"hash": "a" * 64, "prepared_at": "2026-01-01T00:00:00+00:00"}
    course = {
        "chapters": [worked],
        "patterns": [],
        "selection": {"coverage": [], "unavailable": []},
    }
    with monkeypatch.context() as patch:
        patch.setattr("chess_coach.web_tactical_course.offered", lambda *_: (offered, course))
        patch.setattr("chess_coach.web_tactical_course.status", lambda *_: {"configured": False})
        patch.setattr("chess_coach.web_tactical_course.preparation", lambda *_: None)
        patch.setattr("chess_coach.web_tactical_course.preparation_details", lambda *_: None)
        patch.setattr(
            "chess_coach.web_tactical_exposure.record_exposure",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(
                AssertionError("compat must not write")
            ),
        )
        compat_client = compat_app.test_client()
        worked_page = compat_client.get(
            "/coaching/tactical-course", base_url=ORIGIN, headers=HEADERS
        )
        assert (
            worked_page.status_code == 200
            and b"Delivery tracking is unavailable" in worked_page.data
        )
        worked_pgn = compat_client.get(
            "/coaching/tactical-course?download=1&version=" + offered["hash"],
            base_url=ORIGIN,
            headers=HEADERS,
        )
        assert worked_pgn.status_code == 200 and worked_pgn.mimetype == "application/x-chess-pgn"
        lesson = {
            **worked,
            "fen": chess.STARTING_FEN,
            "color": "white",
            "name": "Synthetic",
            "eco": "A00",
            "reason": "Example",
            "instruction": "Choose a move",
            "san": ["e4", "e5"],
            "revisit": "Revisit",
            "scope": "Fixture",
            "geometry": "Fixture",
            "source_url": "https://example.invalid",
            "license_url": "https://example.invalid/license",
            "license": "Fixture",
            "source": {
                "record": "fixture",
                "archive_sha256": "fixture",
                "catalog_source": "https://example.invalid",
            },
        }
        opening = {"version": "b" * 64, "chapters": [lesson], "selection": None}
        patch.setattr("chess_coach.web_unfamiliar_course._load", lambda *_: opening)
        opening_page = compat_client.get(
            "/repertoire/unfamiliar/course", base_url=ORIGIN, headers=HEADERS
        )
        assert (
            opening_page.status_code == 200
            and b"Delivery tracking is unavailable" in opening_page.data
        )
        opening_pgn = compat_client.get(
            "/repertoire/unfamiliar/course?download=1&version=" + opening["version"],
            base_url=ORIGIN,
            headers=HEADERS,
        )
        assert opening_pgn.status_code == 200 and opening_pgn.mimetype == "application/x-chess-pgn"
    from chess_coach.curriculum import daily_plan
    from chess_coach.unified_sessions import start as start_unified

    daily_plan(compat_db, subject="learner", corpus_version="fixture-v1")
    with pytest.raises(ValueError, match="qualified mate training is unavailable"):
        start_unified(
            compat_db,
            attempt_id="compat-learning",
            subject="learner",
            source_type="corpus",
            version="compat-mate",
            key="mate",
            goal="mate_in_one",
            training=True,
        )
    assert (
        compat_db.connection.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE name='unified_training_completions'"
        ).fetchone()[0]
        == 0
    )
    for name in ("analysis_runs", "detector_runs", "mapping_runs"):
        assert [
            tuple(row) for row in compat_db.connection.execute(f"SELECT * FROM {name} ORDER BY id")
        ] == [
            tuple(row)
            for row in compat_db.connection.execute(f"SELECT * FROM {name}_read ORDER BY id")
        ]
    args: dict[str, Any] = dict(
        position_id=1, producer="compat", detector_version="v1", input_data={"test": True}, facts=[]
    )
    from chess_coach import detector_input_schema

    with monkeypatch.context() as verified:
        verified.setattr(detector_input_schema, "legacy", newer_migration)
        result = record_fact_run(compat_db, **args)
        assert record_fact_run(compat_db, **args) == {**result, "replayed": True}
    assert compat_db.connection.execute("PRAGMA user_version").fetchone()[0] == 32
    assert compat_db.connection.execute("PRAGMA schema_version").fetchone()[0] == before
    assert not any(
        row[1] == "idx_engine_outputs_position_id"
        for row in compat_db.connection.execute("PRAGMA index_list(engine_outputs)")
    )
    compat_db.close()
    raw = sqlite3.connect(legacy.as_uri() + "?mode=ro", uri=True)
    from chess_coach.schema_compat import readonly

    readonly(raw, legacy)
    raw.execute("PRAGMA query_only=ON")
    assert raw.execute("SELECT count(*) FROM detector_runs_read").fetchone()[0] > 0
    with pytest.raises(sqlite3.OperationalError):
        raw.execute("DELETE FROM detector_runs")
    raw.close()

    # Both scheduled entry points receive the same verified connection mode.

    from chess_coach import ops_retry, ops_worker, tactical_study_current

    calls = []

    def worker_action(db, _args):
        calls.append(("worker", db.compat32))
        db.close()

    monkeypatch.setitem(cli.COMMANDS, "process-pipeline", worker_action)
    monkeypatch.setattr(ops_worker, "database_path", lambda: legacy)
    monkeypatch.setattr(sys, "argv", [])
    ops_worker.main()
    monkeypatch.setenv("LICHESS_USERNAME", "learner")
    monkeypatch.setattr(ops_retry, "database_path", lambda: legacy)
    monkeypatch.setattr(ops_retry, "sync_result", lambda db, *_args, **_kw: None)
    monkeypatch.setattr(
        ops_retry, "process_objectives", lambda db, _learner: calls.append(("retry", db.compat32))
    )
    ops_retry.main()
    assert calls == [("worker", True), ("retry", True)]

    envelope = {"preview": "fixture"}
    monkeypatch.setenv("CHESS_CORPUS", "fixture-v1")
    monkeypatch.setattr(
        tactical_study_current, "preview", lambda *_args: {"kind": "local-tactical-course-v1"}
    )

    def study_build(db, *_args):
        assert db.connection.execute("PRAGMA query_only").fetchone()[0] == 1
        assert db.connection.execute("SELECT count(*) FROM detector_runs_read").fetchone()[0] > 0
        return envelope

    monkeypatch.setattr(tactical_study_current, "build", study_build)
    with tactical_study_current.revalidate(legacy, envelope, "selected") as check:
        check()

    # An attestation cannot be reused for a different release or malformed rows.
    release = schema_compat_identity.release_info
    monkeypatch.setattr(
        schema_compat_identity,
        "release_info",
        lambda: {
            "commit": "b" * 40,
            "module_path": str(root / ".runtime" / "releases" / ("b" * 40) / "module.py"),
        },
    )
    with pytest.raises(ValueError, match="attestation"):
        Database(legacy, compatibility=True)
    monkeypatch.setattr(schema_compat_identity, "release_info", release)
    changed = sqlite3.connect(legacy)
    original_hash = changed.execute("SELECT input_hash FROM detector_runs WHERE id=1").fetchone()[0]
    changed.execute("UPDATE detector_runs SET input_hash=? WHERE id=1", (b"invalid",))
    changed.commit()
    changed.close()
    invalid = sqlite3.connect(legacy.as_uri() + "?mode=ro", uri=True)
    invalid.execute("PRAGMA query_only=ON")
    with pytest.raises(ValueError, match="representation"):
        attest(legacy, invalid)
    invalid.close()
    invalid = Database(legacy, compatibility=True)
    with pytest.raises(sqlite3.OperationalError):
        invalid.connection.execute(
            "SELECT input_json FROM detector_runs_read WHERE id=1"
        ).fetchone()
    invalid.close()
    from chess_coach.schema_compat import configured

    assert not configured(path)
    changed = sqlite3.connect(legacy)
    changed.execute("UPDATE detector_runs SET input_hash=? WHERE id=1", (original_hash,))
    mapping_id, mapping_hash = changed.execute(
        "SELECT id,output_hash FROM mapping_runs ORDER BY id LIMIT 1"
    ).fetchone()
    changed.execute("UPDATE mapping_runs SET output_hash=? WHERE id=?", (b"invalid", mapping_id))
    changed.commit()
    invalid = Database(legacy, compatibility=True)
    with pytest.raises(sqlite3.OperationalError):
        invalid.connection.execute(
            "SELECT input_json FROM mapping_runs_read WHERE id=?", (mapping_id,)
        ).fetchone()
    invalid.close()
    changed.execute("UPDATE mapping_runs SET output_hash=? WHERE id=?", (mapping_hash, mapping_id))
    changed.execute(
        "UPDATE analysis_runs SET config_json='',nnue='',compatibility_json='' WHERE id=1"
    )
    changed.commit()
    invalid = Database(legacy, compatibility=True)
    with pytest.raises(sqlite3.OperationalError):
        invalid.connection.execute("SELECT id FROM analysis_runs_read WHERE id=1").fetchone()
    invalid.close()
    changed.execute("UPDATE analysis_runs SET config_json='{}',compatibility_json='{}' WHERE id=1")
    original_index = changed.execute(
        "SELECT sql FROM sqlite_master WHERE name='idx_detector_run_active'"
    ).fetchone()[0]
    changed.execute("DROP INDEX idx_detector_run_active")
    changed.execute(
        "CREATE INDEX idx_detector_run_active ON detector_runs(producer,position_id) "
        "WHERE status='active'"
    )
    changed.commit()
    invalid = sqlite3.connect(legacy.as_uri() + "?mode=ro", uri=True)
    with pytest.raises(ValueError, match="constraints differ"):
        attest(legacy, invalid)
    invalid.close()
    changed.execute("DROP INDEX idx_detector_run_active")
    changed.execute(original_index)
    changed.execute("CREATE TABLE analysis_provenance(id INTEGER)")
    changed.commit()
    changed.close()
    with pytest.raises(ValueError, match="attestation"):
        Database(legacy, compatibility=True)
    invalid = sqlite3.connect(legacy.as_uri() + "?mode=ro", uri=True)
    with pytest.raises(ValueError, match="newer schema objects"):
        attest(legacy, invalid)
    invalid.close()


def test_review_practice_completion_and_followup_plan(setup):
    path, app, evidence_id = setup
    client = app.test_client()
    detail = client.get(f"/evidence/{evidence_id}", base_url=ORIGIN, headers=HEADERS)
    assert b"Source game: 1; ply: 1" in detail.data
    assert b"Chess position" in detail.data and b"mate_in_one" in detail.data
    csrf = token(detail)
    assert (
        post(client, f"/evidence/{evidence_id}/review", csrf, decision="accept").status_code == 303
    )
    page = client.get("/plan", base_url=ORIGIN, headers=HEADERS)
    assert b"Find mate in one." in page.data
    assert (
        post(client, "/practice/start", csrf, version="fixture-v1", puzzle_id="puzzle").status_code
        == 303
    )
    page = client.get("/practice", base_url=ORIGIN, headers=HEADERS)
    assert page.status_code == 200 and b"Find mate in one." in page.data
    assert b"c5f8" not in page.data and b"c5c8" not in page.data
    assert (
        post(
            client,
            "/practice/move",
            csrf,
            attempt=token(page, "attempt"),
            item_id=token(page, "item_id"),
            event=token(page, "event"),
            move="c5c8",
        ).status_code
        == 303
    )
    page = client.get("/practice", base_url=ORIGIN, headers=HEADERS)
    assert (
        b"Solved" in page.data
        and b"Next due:" in page.data
        and b"verified_mate_in_one" in page.data
    )
    next_plan = client.get("/plan", base_url=ORIGIN, headers=HEADERS)
    assert b"No practice items" in next_plan.data
    db = Database(path)
    assert (
        db.connection.execute("SELECT decision FROM evidence_review_events").fetchone()[0]
        == "accept"
    )
    assert db.connection.execute("SELECT COUNT(*) FROM training_completions").fetchone()[0] == 1
    assert (
        db.connection.execute(
            "SELECT COUNT(*) FROM evidence_mappings WHERE human_validated=0"
        ).fetchone()[0]
        == 1
    )
    db.close()


def test_untrusted_review_text_is_escaped(setup):
    path, app, evidence_id = setup
    db = Database(path)
    review_evidence(
        db, evidence_id, decision="accept", actor="fixture", rationale="<script>alert(1)</script>"
    )
    db.close()
    page = app.test_client().get(f"/evidence/{evidence_id}", base_url=ORIGIN, headers=HEADERS)
    assert b"<script>alert(1)</script>" not in page.data
    assert b"&lt;script&gt;alert(1)&lt;/script&gt;" in page.data


def test_real_unix_server_enforces_identity_origin_and_csrf(setup):
    import http.client
    import os
    import shutil
    import socket
    import subprocess
    import sys
    import tempfile
    import time
    from urllib.parse import urlencode

    source_db, _, evidence_id = setup
    with tempfile.TemporaryDirectory(prefix="wh-") as directory:
        root = Path(directory)
        path = root / "web.sock"
        db_path = root / "coach.sqlite"
        shutil.copyfile(source_db, db_path)
        env = os.environ | {
            "CHESS_PROJECT_ROOT": str(root),
            "CHESS_DB": str(db_path),
            "CHESS_WEB_SOCKET": str(path),
            "CHESS_SUBJECT": "learner",
            "CHESS_REVIEW_ACTOR": "fixture-reviewer",
            "CHESS_CORPUS": "fixture-v1",
            "CHESS_TAILSCALE_LOGIN": LOGIN,
            "CHESS_WEB_ORIGIN": ORIGIN,
        }

        class UnixConnection(http.client.HTTPConnection):
            def connect(self):
                self.sock = socket.socket(socket.AF_UNIX)
                self.sock.settimeout(5)
                self.sock.connect(str(path))

        def request(method, route, *, headers=None, data=None):
            client = UnixConnection("localhost", timeout=5)
            body = urlencode(data or {}) if method == "POST" else None
            supplied = {"Host": "localhost", "X-Forwarded-Host": "coach.invalid"}
            supplied.update(headers or {})
            if body is not None:
                supplied["Content-Type"] = "application/x-www-form-urlencoded"
            client.request(method, route, body=body, headers=supplied)
            response = client.getresponse()
            status, response_headers, payload = response.status, response.headers, response.read()
            client.close()
            return status, response_headers, payload

        proc = subprocess.Popen(
            [sys.executable, "-m", "chess_coach.web_server"],
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            deadline = time.monotonic() + 10
            while not path.exists() and proc.poll() is None and time.monotonic() < deadline:
                time.sleep(0.02)
            assert path.is_socket() and proc.poll() is None
            route = f"/evidence/{evidence_id}"
            assert request("GET", route)[0] == 403
            assert request("GET", route, headers={"Tailscale-User-Login": "wrong"})[0] == 403
            assert (
                request(
                    "GET",
                    route,
                    headers={**HEADERS, "Host": "coach.invalid", "X-Forwarded-Host": "localhost"},
                )[0]
                == 403
            )
            status, headers, body = request(
                "GET",
                route,
                headers={
                    **HEADERS,
                    "Origin": "https://evil.invalid",
                    "X-Forwarded-Host": "evil.invalid",
                },
            )
            assert status == 200 and headers.get("Access-Control-Allow-Origin") is None
            assert headers["Referrer-Policy"] == "same-origin"
            cookie = headers["Set-Cookie"]
            assert cookie.startswith("__Host-chess_coach_session=")
            assert (
                "Secure" in cookie
                and "HttpOnly" in cookie
                and "SameSite=Strict" in cookie
                and "Path=/" in cookie
                and "Domain=" not in cookie
            )
            quote = bytes([34])
            marker = b"name=" + quote + b"csrf" + quote + b" value=" + quote
            csrf = body.split(marker, 1)[1].split(quote, 1)[0].decode()
            post_route = route + "/review"
            authenticated = {**HEADERS, "Cookie": cookie.split(";", 1)[0]}
            form = {"csrf": csrf, "decision": "accept"}
            no_identity = {"Cookie": authenticated["Cookie"], "Origin": ORIGIN}
            assert request("POST", post_route, headers=no_identity, data=form)[0] == 403
            assert (
                request(
                    "POST",
                    post_route,
                    headers={**no_identity, "Tailscale-User-Login": "wrong"},
                    data=form,
                )[0]
                == 403
            )
            assert request("POST", post_route, headers=authenticated, data=form)[0] == 403
            assert (
                request("POST", post_route, headers={**authenticated, "Origin": "null"}, data=form)[
                    0
                ]
                == 403
            )
            assert (
                request(
                    "POST",
                    post_route,
                    headers={**authenticated, "Origin": "https://evil.invalid"},
                    data=form,
                )[0]
                == 403
            )
            assert (
                request(
                    "POST",
                    post_route,
                    headers={**authenticated, "Origin": ORIGIN},
                    data={"decision": "accept"},
                )[0]
                == 403
            )
            assert (
                request(
                    "POST",
                    post_route,
                    headers={**authenticated, "Origin": ORIGIN},
                    data={"csrf": "wrong", "decision": "accept"},
                )[0]
                == 403
            )
            check = Database(db_path)
            assert (
                check.connection.execute("SELECT COUNT(*) FROM evidence_review_events").fetchone()[
                    0
                ]
                == 0
            )
            check.close()
            assert (
                request(
                    "POST",
                    post_route,
                    headers={**authenticated, "Origin": ORIGIN, "X-Forwarded-Host": "evil.invalid"},
                    data=form,
                )[0]
                == 303
            )
            check = Database(db_path)
            assert (
                check.connection.execute("SELECT COUNT(*) FROM evidence_review_events").fetchone()[
                    0
                ]
                == 1
            )
            check.close()
        finally:
            proc.kill()
            proc.wait(timeout=5)
