"""Grounded coaching and immutable regeneration on synthetic sources."""

from chess_coach.fork_detector import process_decision
from chess_coach.lesson_mechanisms import describe
from chess_coach.lesson_source import source
from tests.test_fork_pipeline import LEARNER, make_game


def test_fork_lesson_uses_rechecked_fact_and_legal_line(tmp_path, monkeypatch):
    db, _ = make_game(tmp_path / "synthetic.sqlite", monkeypatch)
    result = process_decision(db, 1, LEARNER)
    evidence_id = result["evidence_ids"][0]
    candidate = {"id": evidence_id, "position_id": 1}
    current = source(db, LEARNER, candidate)
    example = describe(current)
    assert example["played"] != "Nc7+"
    assert "Nc7+" in example["facts"][0]
    assert example["evidence_id"] == evidence_id
    assert source(db, "another", candidate) is None
    db.connection.execute(
        "UPDATE detector_runs SET status='superseded' WHERE id=?", (result["detector_run_id"],)
    )
    db.connection.commit()
    assert source(db, LEARNER, candidate) is None


def test_decision_and_saved_history_render_coaching(tmp_path, monkeypatch):
    import chess_coach.web_lessons as web_lessons
    from chess_coach.web import create_app

    path = tmp_path / "synthetic.sqlite"
    db, _ = make_game(path, monkeypatch)
    result = process_decision(db, 1, LEARNER)
    evidence_id = result["evidence_ids"][0]
    from chess_coach.evidence_review import review_evidence

    review_evidence(db, evidence_id, decision="accept", actor="fixture")
    db.close()
    group = {
        "skill": "fork",
        "operation": "execute",
        "family": "fork-opportunity-mapper",
        "version": "1.0.1",
        "lesson_examples": [
            {
                "id": evidence_id,
                "position_id": 1,
                "context": {
                    "side": "white",
                    "phase": "low material",
                    "clock": "unknown",
                    "time control": "unknown",
                },
            }
        ],
    }
    report_data = {
        "current": [group],
        "previous": [],
        "start": "s",
        "end": "e",
        "compare_start": "p",
        "skill": None,
        "operation": None,
    }
    monkeypatch.setattr(web_lessons, "report", lambda *args, **kwargs: report_data)
    app = create_app(
        db_path=path,
        subject=LEARNER,
        actor="fixture",
        corpus="test",
        login="login",
        origin="https://coach.invalid",
    )
    client = app.test_client()
    headers = {"Tailscale-User-Login": "login"}
    report_page = client.get("/recurrence", base_url="https://coach.invalid", headers=headers)
    assert b"not repeated mistakes" in report_page.data
    view = client.get("/decisions/1", base_url="https://coach.invalid", headers=headers)
    assert view.status_code == 200
    assert b"Diagnostic question" in view.data and b"Nc7+" in view.data
    with client.session_transaction(base_url="https://coach.invalid") as session:
        csrf = session["csrf"]
    form = {
        "csrf": csrf,
        "start": "s",
        "end": "e",
        "compare_start": "p",
        "period": "current",
        **{key: group[key] for key in ("skill", "operation", "family", "version")},
    }
    headers["Origin"] = "https://coach.invalid"
    first = client.post(
        "/lessons/regenerate", data=form, base_url="https://coach.invalid", headers=headers
    )
    second = client.post(
        "/lessons/regenerate", data=form, base_url="https://coach.invalid", headers=headers
    )
    assert first.status_code == second.status_code == 303
    assert first.location != second.location
    page = client.get(first.location, base_url="https://coach.invalid", headers=headers)
    assert b"historical snapshot" in page.data and b"Nc7+" in page.data
    history = client.get("/lessons", base_url="https://coach.invalid", headers=headers)
    assert history.status_code == 200 and history.data.count(b"fork / execute") == 2
    from chess_coach.db import Database

    check = Database(path)
    assert (
        check.connection.execute("SELECT COUNT(*) FROM evidence_review_events").fetchone()[0] == 1
    )
    check.close()


def test_material_and_mate_sources_generate_specific_legal_explanations(tmp_path, monkeypatch):
    from chess_coach.mate_auto import process_decision as mate_decision
    from chess_coach.material_detector import process_decision as material_decision
    from tests.test_mate_proof import owned_game
    from tests.test_material_pipeline import LEARNER as MATERIAL_LEARNER
    from tests.test_material_pipeline import make_game as material_game

    db = material_game(tmp_path / "material.sqlite", monkeypatch)
    material = material_decision(db, 1, MATERIAL_LEARNER)
    evidence_id = material["evidence_ids"][0]
    example = describe(source(db, MATERIAL_LEARNER, {"id": evidence_id, "position_id": 1}))
    assert example["facts"] and example["lines"]
    assert all(line["moves"] for line in example["lines"])
    db.close()
    db = owned_game(tmp_path / "mate.sqlite", monkeypatch)
    mate_decision(db, 1, "fixture_a")
    row = db.connection.execute(
        "SELECT id FROM evidence_mappings WHERE mapping_run_id IS NOT NULL"
    ).fetchone()
    example = describe(source(db, "fixture_a", {"id": row["id"], "position_id": 1}))
    assert "forced mating" in example["facts"][0]
    assert example["lines"]


def test_repeated_failure_coaching_preview_is_private_and_historical(tmp_path, monkeypatch):
    import json
    import sys

    import pytest

    from chess_coach.course_evidence import revalidate_group
    from chess_coach.db import Database
    from chess_coach.decision_inspection import inspect_decision
    from chess_coach.evidence_review import review_evidence
    from chess_coach.ingest import ingest_pgn
    from chess_coach.material_detector import process_decision as material_decision
    from chess_coach.pipeline_config import PipelineConfig
    from chess_coach.pipeline_inputs import engine_identity, game_input
    from chess_coach.pipeline_work import run_analysis
    from chess_coach.web import create_app
    from tests.test_material_pipeline import LEARNER, make_game
    from tests.test_unified_sessions import token

    project = tmp_path / "project"
    path = project / ".runtime" / "data" / "coaching.sqlite"
    path.parent.mkdir(parents=True)
    (project / ".runtime").chmod(0o700)
    planning = project / ".runtime" / "planning"
    planning.mkdir(mode=0o700)
    (project / ".runtime" / "entry").mkdir(mode=0o700)
    monkeypatch.setenv("CHESS_DB", str(path))
    monkeypatch.setenv("CHESS_SUBJECT", LEARNER)
    monkeypatch.setenv("CHESS_CORPUS", "test")
    db = make_game(path, monkeypatch)
    material_decision(db, 1, LEARNER)
    pgn = db.connection.execute("SELECT pgn FROM games WHERE id=1").fetchone()[0]
    assert "2026.01.01" in pgn
    ingest_pgn(db, pgn.replace("2026.01.01", "2026.01.02"))
    position = db.connection.execute(
        "SELECT id FROM positions WHERE game_id=2 AND ply=1"
    ).fetchone()[0]
    config = PipelineConfig(learner=LEARNER, engine_path=sys.executable, nodes=100)
    assert (
        run_analysis(db, 2, game_input(db, 2), config, engine_identity(sys.executable))["status"]
        == "complete"
    )
    material_decision(db, position, LEARNER)

    # Compare the paged scan with the established complete scan.
    import sqlite3

    import chess

    import chess_coach.tactical_course_familiar_games as familiarity_games
    from chess_coach.related_capture_familiar import familiarity as original_familiarity
    from chess_coach.tactical_course_budget import Budget, PreviewUnavailable
    from chess_coach.tactical_course_deadline import PreviewDeadline
    from chess_coach.tactical_course_familiar import familiarity as paged_familiarity

    db.connection.execute(
        "INSERT INTO puzzle_sessions(attempt_id,corpus_version,corpus_checksum,puzzle_id,"
        "initial_fen,solution,current_fen,next_index,status,hints_used,started_at) "
        "VALUES(?,?,?,?,?,?,?,?,?,?,?)",
        (
            "familiar-fixture",
            "test",
            "checksum",
            "puzzle",
            chess.STARTING_FEN,
            "e2e4 e7e5",
            chess.STARTING_FEN,
            0,
            "active",
            0,
            "2026-01-01",
        ),
    )
    db.connection.execute(
        "INSERT INTO games(pgn,white,black,result) VALUES(?,?,?,?)",
        ("unrelated", "other", "other", "*"),
    )
    db.connection.commit()
    with monkeypatch.context() as patch:
        patch.setattr(familiarity_games, "PAGE", 1)
        original = original_familiarity(db, LEARNER)
        budget = Budget(db)
        paged = paged_familiarity(db, LEARNER, budget)
        assert paged[:2] == original[:2]
        assert paged_familiarity(db, LEARNER, budget) is paged
        for key in paged[0]:
            assert paged[2](key) == original[2](key)

    original_pages = familiarity_games._pages

    def changed_pages(*args, **kwargs):
        for rows in original_pages(*args, **kwargs):
            yield rows
            with sqlite3.connect(path) as writer:
                writer.execute("UPDATE games SET event=event WHERE id=1")

    with monkeypatch.context() as patch:
        patch.setattr(familiarity_games, "PAGE", 1)
        patch.setattr(familiarity_games, "_pages", changed_pages)
        with pytest.raises(PreviewUnavailable, match="changed"):
            paged_familiarity(db, LEARNER, Budget(db))
    with monkeypatch.context() as patch:

        def interrupted(*_args):
            raise PreviewDeadline()

        patch.setattr(familiarity_games, "_initial_prompt", interrupted)
        budget = Budget(db)
        with pytest.raises(PreviewDeadline):
            paged_familiarity(db, LEARNER, budget)
        with pytest.raises(PreviewDeadline):
            paged_familiarity(db, LEARNER, budget)

    from chess_coach.course_preview import preview_hash
    from chess_coach.ops_tactical_course import prepare
    from chess_coach.ops_tactical_export import prepare as export_candidate
    from chess_coach.study_publisher import publish

    first_preview = planning / "tactical-first.json"
    second_preview = planning / "tactical-second.json"
    prepare(project, first_preview)
    first_content = first_preview.read_bytes()
    preview = json.loads(first_content)
    assert preview["kind"] == "local-tactical-course-v1"
    assert preview["preview_sha256"] == preview_hash(preview["preview"])
    assert [item["kind"] for item in preview["preview"]["patterns"]] == ["capture"]
    assert preview["preview"]["patterns"][0]["independent_games"] == 2
    supports = preview["preview"]["patterns"][0]["supporting_sources"]
    assert len(supports) == 2 and len({item["game_key"] for item in supports}) == 2
    assert all(item["lineage_sha256"] and item["fact_ids"] for item in supports)
    assert preview["preview"]["chapters"][0]["mode"] == "conceal"
    chapter = preview["preview"]["chapters"][0]
    assert "Worked example, ungraded" in chapter["pgn"]
    assert "Source review: unreviewed." in chapter["pgn"]
    assert "Played " in chapter["pgn"] and "Goal:" in chapter["pgn"]
    import io

    import chess.pgn

    from chess_coach.coaching_report import report as coaching_report

    saved_group = coaching_report(db, LEARNER)["groups"][0]
    selected_id = chapter["source"]["evidence_id"]
    example = next(
        item for item in saved_group["lesson"]["examples"] if item["evidence_id"] == selected_id
    )
    parsed = chess.pgn.read_game(io.StringIO(chapter["pgn"]))
    assert parsed is not None
    note = " ".join(parsed.comment.split())
    assert example["played"] in note and example["facts"][0] in note
    assert saved_group["lesson"]["question"] in note and saved_group["lesson"]["habit"] in note
    assert (
        preview["preview"]["selection"]["unavailable"][0]["reason"]
        == "related corpus or compatible unfamiliar example unavailable"
    )
    prepare(project, second_preview)
    assert first_preview.read_bytes() == first_content
    second = json.loads(second_preview.read_bytes())
    assert second["preview_sha256"] == preview["preview_sha256"]
    assert preview["preview"]["selection"]["corpus_version"] == "test"

    export_path = planning / "tactical-export.json"
    export_candidate(project, first_preview, preview["preview_sha256"], export_path)
    exported_bytes = export_path.read_bytes()
    exported = json.loads(exported_bytes)
    assert exported["kind"] == "local-tactical-course-export-v1"
    assert exported["export_sha256"] == preview_hash(exported["export"])
    assert exported["export"]["preview_sha256"] == preview["preview_sha256"]
    assert exported["export"]["chapters"] == preview["preview"]["chapters"]
    assert exported["export"]["selection"] == preview["preview"]["selection"]
    assert export_path.stat().st_mode & 0o777 == 0o400
    with pytest.raises(ValueError):
        export_candidate(project, first_preview, preview["preview_sha256"], export_path)
    assert (
        export_path.read_bytes() == exported_bytes and first_preview.read_bytes() == first_content
    )
    invalid_preview = planning / "invalid-chapter.json"
    invalid = json.loads(first_content)
    invalid["preview"]["chapters"][0]["pgn"] += "\n{ changed }\n"
    invalid["preview_sha256"] = preview_hash(invalid["preview"])
    invalid_preview.write_text(json.dumps(invalid))
    invalid_preview.chmod(0o600)
    invalid_output = planning / "invalid-export.json"
    with pytest.raises(ValueError):
        export_candidate(project, invalid_preview, invalid["preview_sha256"], invalid_output)
    assert not invalid_output.exists() and export_path.read_bytes() == exported_bytes
    # Even a rehashed envelope cannot claim incomplete coverage or contradictory gaps.
    broken = []
    deferred = json.loads(first_content)
    pattern = deferred["preview"]["patterns"][0]
    row = next(
        item
        for item in deferred["preview"]["selection"]["coverage"]
        if (item["skill"], item["operation"]) == (pattern["skill"], pattern["operation"])
    )
    row.update(status="deferred: time budget", examined=None, limited=True, excluded={})
    broken.append(deferred)
    too_few = json.loads(first_content)
    pattern = too_few["preview"]["patterns"][0]
    row = next(
        item
        for item in too_few["preview"]["selection"]["coverage"]
        if (item["skill"], item["operation"]) == (pattern["skill"], pattern["operation"])
    )
    row["examined"] = 1
    broken.append(too_few)
    duplicated = json.loads(first_content)
    duplicated["preview"]["selection"]["unavailable"].append(
        duplicated["preview"]["selection"]["unavailable"][0]
    )
    broken.append(duplicated)
    missing = json.loads(first_content)
    missing["preview"]["selection"]["unavailable"] = []
    broken.append(missing)
    for case in broken:
        case["preview_sha256"] = preview_hash(case["preview"])
        invalid_preview.write_text(json.dumps(case))
        with pytest.raises(ValueError):
            export_candidate(project, invalid_preview, case["preview_sha256"], invalid_output)
        assert not invalid_output.exists()
    with pytest.raises(ValueError):
        export_candidate(project, first_preview, "0" * 64, invalid_output)
    assert not invalid_output.exists()
    with pytest.raises(ValueError):
        prepare(project, first_preview)

    # A real synthetic unfamiliar source is reconstructed and bound as well.
    import chess

    db.connection.execute(
        "INSERT INTO puzzle_corpora(version,source,checksum,state) VALUES('test','fixture','checksum','staging')"
    )
    corpus_id = db.connection.execute(
        "SELECT id FROM puzzle_corpora WHERE version='test'"
    ).fetchone()[0]
    board = chess.Board("4k3/8/8/8/3q4/8/8/3RK3 b - - 0 1")
    board.set_piece_at(chess.A7, chess.Piece(chess.PAWN, chess.BLACK))
    db.connection.execute(
        """INSERT INTO puzzles(puzzle_id,corpus_id,fen,source,solution,rating,rating_deviation,themes_json,objective)
        VALUES('fixture-related',?,?,'https://example.invalid','a7a6 d1d4',1200,80,'["hangingPiece"]','unknown')""",
        (corpus_id, board.fen()),
    )
    db.connection.execute(
        "INSERT INTO puzzle_themes VALUES(?,?,'hangingPiece',1200)", (corpus_id, "fixture-related")
    )
    db.connection.execute("UPDATE puzzle_corpora SET state='ready' WHERE id=?", (corpus_id,))
    db.connection.commit()
    related_preview_path = planning / "related-preview.json"
    related_output = planning / "related-export.json"
    prepare(project, related_preview_path)
    related_preview = json.loads(related_preview_path.read_bytes())
    from chess_coach.related_capture import _selection as capture_selection

    position_id = json.loads(first_content)["preview"]["chapters"][0]["source"]["position_id"]
    old_selection = capture_selection(db, LEARNER, position_id, "test")
    new_selection = capture_selection(
        db, LEARNER, position_id, "test", familiar_data=paged_familiarity(db, LEARNER, Budget(db))
    )
    assert new_selection == old_selection
    assert len(related_preview["preview"]["chapters"]) == 2
    export_candidate(
        project, related_preview_path, related_preview["preview_sha256"], related_output
    )
    related_export = json.loads(related_output.read_bytes())
    assert related_export["export"]["chapters"] == related_preview["preview"]["chapters"]
    conflicting = json.loads(related_preview_path.read_bytes())
    pattern = conflicting["preview"]["patterns"][0]
    conflicting["preview"]["selection"]["unavailable"].append(
        {
            "skill": pattern["skill"],
            "operation": pattern["operation"],
            "reason": "related corpus or compatible unfamiliar example unavailable",
        }
    )
    conflicting["preview_sha256"] = preview_hash(conflicting["preview"])
    invalid_preview.write_text(json.dumps(conflicting))
    with pytest.raises(ValueError):
        export_candidate(project, invalid_preview, conflicting["preview_sha256"], invalid_output)
    assert not invalid_output.exists()
    altered = json.loads(related_preview_path.read_bytes())
    altered["preview"]["chapters"][1]["source"]["binding"]["rank_version"] = "changed"
    altered["preview_sha256"] = preview_hash(altered["preview"])
    altered_path = planning / "altered-related.json"
    altered_path.write_text(json.dumps(altered))
    altered_path.chmod(0o600)
    rejected = planning / "altered-related-export.json"
    with pytest.raises(ValueError):
        export_candidate(project, altered_path, altered["preview_sha256"], rejected)
    assert not rejected.exists() and related_output.is_file()

    other_id = next(item["evidence_id"] for item in supports if item["evidence_id"] != selected_id)
    review_evidence(db, other_id, decision="accept", actor="fixture")
    stale_output = planning / "stale-export.json"
    with pytest.raises(ValueError):
        export_candidate(project, first_preview, preview["preview_sha256"], stale_output)
    assert not stale_output.exists() and export_path.read_bytes() == exported_bytes
    reviewed_first = planning / "reviewed-first.json"
    prepare(project, reviewed_first)
    review_evidence(db, other_id, decision="accept", actor="fixture")
    reviewed_second = planning / "reviewed-second.json"
    prepare(project, reviewed_second)
    first_reviewed = json.loads(reviewed_first.read_bytes())
    second_reviewed = json.loads(reviewed_second.read_bytes())
    assert (
        first_reviewed["preview"]["patterns"][0]["review_states"]
        == second_reviewed["preview"]["patterns"][0]["review_states"]
    )
    assert first_reviewed["preview_sha256"] != second_reviewed["preview_sha256"]
    assert first_reviewed["preview"]["chapters"][0] == second_reviewed["preview"]["chapters"][0]
    assert first_preview.read_bytes() == first_content

    import time

    import chess_coach.tactical_course_publish as tactical_publish
    from chess_coach.tactical_course_budget import Budget, PreviewUnavailable
    from chess_coach.tactical_course_deadline import PreviewDeadline

    with monkeypatch.context() as patch:
        patch.setattr("chess_coach.tactical_course_budget.SLICE_SECONDS", 0.01)
        with pytest.raises(PreviewDeadline), Budget(db).scope(snapshot=True):
            time.sleep(0.05)
    assert not db.connection.in_transaction

    original_stage = tactical_publish.stage

    def concurrent_stage(output, value):
        temporary = original_stage(output, value)
        assert not output.exists() and json.loads(temporary.read_bytes())["kind"] == preview["kind"]
        db.connection.execute("UPDATE games SET event=event WHERE id=1")
        db.connection.commit()
        return temporary

    changed = planning / "concurrent.json"
    with monkeypatch.context() as patch:
        patch.setattr(tactical_publish, "stage", concurrent_stage)
        with pytest.raises(PreviewUnavailable, match="changed"):
            prepare(project, changed)
    assert not changed.exists()
    assert not list(planning.glob(".tactical-preview-*"))
    assert first_preview.read_bytes() == first_content

    def fail_link(temporary, output, **_kwargs):
        assert not output.exists()
        assert json.loads(temporary.read_bytes())["kind"] == preview["kind"]
        raise OSError("synthetic publication failure")

    failed = planning / "failed-publication.json"
    with monkeypatch.context() as patch:
        patch.setattr(tactical_publish.os, "link", fail_link)
        with pytest.raises(OSError, match="synthetic"):
            prepare(project, failed)
    assert not failed.exists() and not list(planning.glob(".tactical-preview-*"))
    assert first_preview.read_bytes() == first_content
    with pytest.raises(KeyError):
        publish(object(), planning / "publisher-intent.json", preview)
    with pytest.raises(KeyError):
        publish(object(), planning / "publisher-intent.json", exported)
    assert not (planning / "publisher-intent.json").exists()
    db.close()

    app = create_app(
        db_path=path,
        subject=LEARNER,
        actor="fixture",
        corpus="test",
        login="login",
        origin="https://coach.invalid",
    )
    client = app.test_client()
    headers = {"Tailscale-User-Login": "login"}
    assert client.get("/coaching", base_url="https://coach.invalid").status_code == 403
    page = client.get("/coaching", base_url="https://coach.invalid", headers=headers)
    assert page.status_code == 200
    assert b"Finding captures" in page.data and b"2 independent games" in page.data
    assert b"Source position before the move" in page.data and b'class="board"' in page.data
    assert b"Only 1 of three" in page.data and b"Recorded best-search continuation" in page.data
    check = Database(path)
    assert check.connection.execute("SELECT COUNT(*) FROM lesson_versions").fetchone()[0] == 0
    check.close()
    with client.session_transaction(base_url="https://coach.invalid") as session:
        csrf = session["csrf"]
    assert (
        client.post(
            "/coaching/save", data={"csrf": csrf}, base_url="https://coach.invalid", headers=headers
        ).status_code
        == 403
    )
    saved = client.post(
        "/coaching/save",
        data={"csrf": csrf},
        base_url="https://coach.invalid",
        headers=headers | {"Origin": "https://coach.invalid"},
    )
    assert saved.status_code == 303
    snapshot = client.get(saved.location, base_url="https://coach.invalid", headers=headers)
    assert b"historical snapshot" in snapshot.data and b"Finding captures" in snapshot.data
    assert b"Find related capture practice" in snapshot.data
    version, key = token(snapshot, "version"), token(snapshot, "key")
    origin = headers | {"Origin": "https://coach.invalid"}
    started = client.post(
        "/unified/start",
        data={"csrf": csrf, "source_type": "own-game", "version": version, "key": key},
        base_url="https://coach.invalid",
        headers=origin,
    )
    assert started.status_code == 303
    practice = client.get(started.location, base_url="https://coach.invalid", headers=headers)
    attempt = token(practice, "attempt")
    hinted = client.post(
        "/unified/hint",
        data={"csrf": csrf, "attempt": attempt, "event": token(practice, "event")},
        base_url="https://coach.invalid",
        headers=origin,
    )
    practice = client.get(hinted.location, base_url="https://coach.invalid", headers=headers)
    assert b"Hint: consider a piece" in practice.data
    moved = client.post(
        "/unified/move",
        data={"csrf": csrf, "attempt": attempt, "event": token(practice, "event"), "move": "d1d4"},
        base_url="https://coach.invalid",
        headers=origin,
    )
    completed = client.get(moved.location, base_url="https://coach.invalid", headers=headers)
    assert b"bounded capture objective was verified" in completed.data
    assert b"checkmate objective was verified" not in completed.data
    db = Database(path)
    assert (
        db.connection.execute(
            "SELECT COUNT(*) FROM unified_session_events WHERE attempt_id=?", (attempt,)
        ).fetchone()[0]
        == 2
    )
    assert db.connection.execute("SELECT COUNT(*) FROM mastery_events").fetchone()[0] == 0

    saved_lesson = json.loads(
        db.connection.execute("SELECT lesson_json FROM lesson_versions").fetchone()[0]
    )
    example = saved_lesson["groups"][0]["lesson"]["examples"][0]
    decision = inspect_decision(db, example["position_id"], learner=LEARNER)
    assert example["fen"] == decision["decision_fen"]
    assert (
        example["fen"]
        != db.connection.execute(
            "SELECT fen FROM positions WHERE id=?", (example["position_id"],)
        ).fetchone()[0]
    )
    assert revalidate_group(db, LEARNER, saved_lesson["groups"][0]) == 2
    import chess_coach.tactical_course_chapters as course_chapters
    import chess_coach.tactical_course_evidence as course_evidence

    original = course_evidence.decisions_for_game

    def duplicate_identity(*args, **kwargs):
        decisions = original(*args, **kwargs)
        assert decisions is not None
        for item in decisions.values():
            item["game_key"] = "same synthetic game"
        return decisions

    with monkeypatch.context() as patch:
        patch.setattr(course_evidence, "decisions_for_game", duplicate_identity)
        with pytest.raises(ValueError, match="independent"):
            course_chapters.owned(db, LEARNER, saved_lesson["groups"][0])
    review_evidence(db, int(key), decision="reject", actor="fixture")
    with pytest.raises(ValueError, match="evidence changed"):
        revalidate_group(db, LEARNER, saved_lesson["groups"][0])
    from chess_coach.tactical_course_budget import PreviewUnavailable

    with pytest.raises(PreviewUnavailable):
        prepare(project, planning / "after-rejection.json")
    assert not (planning / "after-rejection.json").exists()
    db.close()
    stale = client.post(
        "/unified/start",
        data={"csrf": csrf, "source_type": "own-game", "version": version, "key": key},
        base_url="https://coach.invalid",
        headers=origin,
    )
    assert stale.status_code == 400
    page = client.get("/coaching", base_url="https://coach.invalid", headers=headers)
    assert b"Only 0 of three" in page.data
    assert (
        b"Finding captures"
        in client.get(saved.location, base_url="https://coach.invalid", headers=headers).data
    )
    history = client.get("/lessons", base_url="https://coach.invalid", headers=headers)
    assert b"Coaching preview / recurring patterns" in history.data


def test_protection_lesson_offers_only_a_current_bounded_line_replay(tmp_path, monkeypatch):
    import sys

    from chess_coach.db import Database
    from chess_coach.ingest import ingest_pgn
    from chess_coach.material_detector import process_decision as material_decision
    from chess_coach.pipeline_config import PipelineConfig
    from chess_coach.pipeline_inputs import engine_identity, game_input
    from chess_coach.pipeline_work import run_analysis
    from chess_coach.web import create_app
    from tests.test_material_pipeline import LEARNER, make_protection_game
    from tests.test_unified_sessions import token

    path = tmp_path / "protection-coaching.sqlite"
    db = make_protection_game(path, monkeypatch)
    material_decision(db, 1, LEARNER)
    pgn = db.connection.execute("SELECT pgn FROM games WHERE id=1").fetchone()[0]
    ingest_pgn(db, pgn.replace("2026.01.01", "2026.01.02"))
    position = db.connection.execute(
        "SELECT id FROM positions WHERE game_id=2 AND ply=1"
    ).fetchone()[0]
    config = PipelineConfig(learner=LEARNER, engine_path=sys.executable, nodes=100)
    assert (
        run_analysis(db, 2, game_input(db, 2), config, engine_identity(sys.executable))["status"]
        == "complete"
    )
    material_decision(db, position, LEARNER)
    db.close()
    app = create_app(
        db_path=path,
        subject=LEARNER,
        actor="fixture",
        corpus="test",
        login="login",
        origin="https://coach.invalid",
    )
    from chess_coach import coaching_practice

    original = coaching_practice.resolve_example
    unavailable = []

    def skip_first(db, subject, lesson, example):
        if not unavailable:
            unavailable.append(example["evidence_id"])
        if example["evidence_id"] == unavailable[0]:
            return None
        return original(db, subject, lesson, example)

    monkeypatch.setattr(coaching_practice, "resolve_example", skip_first)
    client = app.test_client()
    headers = {"Tailscale-User-Login": "login"}
    origin = headers | {"Origin": "https://coach.invalid"}
    page = client.get("/coaching", base_url="https://coach.invalid", headers=headers)
    assert b"Protecting pieces" in page.data and b"Replay a defensive line" in page.data
    csrf, version, key = token(page, "csrf"), token(page, "version"), token(page, "key")
    selected = int(key.split(":")[-1])
    assert selected != unavailable[0]
    source_section = (
        page.get_data(as_text=True)
        .split(f'/evidence/{selected}">Source decision</a>', 1)[1]
        .split("</section>", 1)[0]
    )
    assert f'name="key" value="{key}"' in source_section
    data = {"csrf": csrf, "source_type": "own-game", "version": version, "key": key}
    first = client.post(
        "/unified/start", data=data, base_url="https://coach.invalid", headers=origin
    )
    practice = client.get(first.location, base_url="https://coach.invalid", headers=headers)
    assert b"does not prove every defense" in practice.data
    assert b"Back to coaching" in practice.data
    alternate = client.post(
        "/unified/move",
        data={
            "csrf": csrf,
            "attempt": token(practice, "attempt"),
            "event": token(practice, "event"),
            "move": "a2a3",
        },
        base_url="https://coach.invalid",
        headers=origin,
    )
    feedback = client.get(alternate.location, base_url="https://coach.invalid", headers=headers)
    assert b"needs verification" in feedback.data and b"not been marked incorrect" in feedback.data
    second = client.post(
        "/unified/start", data=data, base_url="https://coach.invalid", headers=origin
    )
    practice = client.get(second.location, base_url="https://coach.invalid", headers=headers)
    attempt = token(practice, "attempt")
    hinted = client.post(
        "/unified/hint",
        data={"csrf": csrf, "attempt": attempt, "event": token(practice, "event")},
        base_url="https://coach.invalid",
        headers=origin,
    )
    practice = client.get(hinted.location, base_url="https://coach.invalid", headers=headers)
    moved = client.post(
        "/unified/move",
        data={"csrf": csrf, "attempt": attempt, "event": token(practice, "event"), "move": "d4d5"},
        base_url="https://coach.invalid",
        headers=origin,
    )
    completed = client.get(moved.location, base_url="https://coach.invalid", headers=headers)
    assert (
        b"completed the recorded defensive line" in completed.data
        and b"Other defenses remain ungraded" in completed.data
    )
    assert b"Piece defense verified" not in completed.data
    db = Database(path)
    assert (
        db.connection.execute(
            "SELECT COUNT(*) FROM unified_session_events WHERE attempt_id=?", (attempt,)
        ).fetchone()[0]
        == 2
    )
    assert db.connection.execute("SELECT COUNT(*) FROM mastery_events").fetchone()[0] == 0
    evidence = int(key.split(":")[-1])
    db.connection.execute(
        "UPDATE mapping_runs SET mapper_version=? WHERE id=(SELECT mapping_run_id FROM evidence_mappings WHERE id=?)",
        ("old-fixture", evidence),
    )
    db.connection.commit()
    db.close()
    assert (
        client.post(
            "/unified/start", data=data, base_url="https://coach.invalid", headers=origin
        ).status_code
        == 400
    )


def test_mate_lesson_starts_owned_practice_and_rechecks_review(tmp_path, monkeypatch):
    import sys

    import chess
    import chess.engine
    import chess.pgn

    from chess_coach.db import Database
    from chess_coach.evidence_review import review_evidence
    from chess_coach.ingest import ingest_pgn
    from chess_coach.mate_auto import process_decision as mate_decision
    from chess_coach.pipeline_config import PipelineConfig
    from chess_coach.pipeline_inputs import engine_identity, game_input
    from chess_coach.pipeline_work import run_analysis
    from chess_coach.web import create_app
    from tests.test_mate_proof import FEN, Engine
    from tests.test_unified_sessions import token

    path = tmp_path / "mate-coaching.sqlite"
    db = Database(path)
    db.initialize()
    monkeypatch.setattr(chess.engine.SimpleEngine, "popen_uci", lambda _: Engine())
    config = PipelineConfig(learner="fixture_a", engine_path=sys.executable, nodes=100)
    for day in (1, 2):
        board = chess.Board(FEN if day == 1 else FEN.replace("8/8 w", "P7/8 w"))
        game = chess.pgn.Game()
        game.setup(board)
        game.headers.update(
            {
                "White": "fixture_a",
                "Black": "fixture_b",
                "Result": "*",
                "UTCDate": f"2026.01.{day:02}",
                "UTCTime": "12:00:00",
            }
        )
        game.add_variation(board.parse_uci("f6e5"))
        ingest_pgn(db, str(game))
        position = db.connection.execute(
            "SELECT id FROM positions WHERE game_id=? AND ply=1", (day,)
        ).fetchone()[0]
        assert (
            run_analysis(db, day, game_input(db, day), config, engine_identity(sys.executable))[
                "status"
            ]
            == "complete"
        )
        mate_decision(db, position, "fixture_a")
    db.close()
    app = create_app(
        db_path=path,
        subject="fixture_a",
        actor="fixture",
        corpus="test",
        login="login",
        origin="https://coach.invalid",
    )
    client = app.test_client()
    headers = {"Tailscale-User-Login": "login"}
    origin = headers | {"Origin": "https://coach.invalid"}
    plan = client.get("/plan", base_url="https://coach.invalid", headers=headers)
    assert b"Practice your recurring patterns" in plan.data
    page = client.get("/coaching", base_url="https://coach.invalid", headers=headers)
    assert b"Finding mate in one" in page.data and b"Find related mate practice" in page.data
    csrf, version, key = token(page, "csrf"), token(page, "version"), token(page, "key")
    assert (
        b"Try this example next. No unassisted first-move checkmate was found for it in recent practice"
        in page.data
    )
    data = {"csrf": csrf, "source_type": "own-game", "version": version, "key": key}
    assisted = client.post(
        "/unified/start", data=data, base_url="https://coach.invalid", headers=origin
    )
    practice = client.get(assisted.location, base_url="https://coach.invalid", headers=headers)
    hinted = client.post(
        "/unified/hint",
        data={
            "csrf": csrf,
            "attempt": token(practice, "attempt"),
            "event": token(practice, "event"),
        },
        base_url="https://coach.invalid",
        headers=origin,
    )
    practice = client.get(hinted.location, base_url="https://coach.invalid", headers=headers)
    assisted_move = client.post(
        "/unified/move",
        data={
            "csrf": csrf,
            "attempt": token(practice, "attempt"),
            "event": token(practice, "event"),
            "move": "g6g7",
        },
        base_url="https://coach.invalid",
        headers=origin,
    )
    assisted_result = client.get(
        assisted_move.location, base_url="https://coach.invalid", headers=headers
    )
    assert b"checkmate objective was verified" in assisted_result.data
    page = client.get("/coaching", base_url="https://coach.invalid", headers=headers)
    assert token(page, "key") == key
    started = client.post(
        "/unified/start",
        data={"csrf": csrf, "source_type": "own-game", "version": version, "key": key},
        base_url="https://coach.invalid",
        headers=origin,
    )
    practice = client.get(started.location, base_url="https://coach.invalid", headers=headers)
    moved = client.post(
        "/unified/move",
        data={
            "csrf": csrf,
            "attempt": token(practice, "attempt"),
            "event": token(practice, "event"),
            "move": "g6g7",
        },
        base_url="https://coach.invalid",
        headers=origin,
    )
    completed = client.get(moved.location, base_url="https://coach.invalid", headers=headers)
    assert b"checkmate objective was verified" in completed.data
    page = client.get("/coaching", base_url="https://coach.invalid", headers=headers)
    assert token(page, "key") != key
    assert (
        b"Try this example next. No unassisted first-move checkmate was found for it in recent practice"
        in page.data
    )
    db = Database(path)
    from chess_coach.coaching_practice import choices
    from chess_coach.coaching_report import report

    assert choices(db, "fixture_a", report(db, "fixture_a"))[0]["key"] == key
    assert db.connection.execute("SELECT COUNT(*) FROM mastery_events").fetchone()[0] == 0
    assert db.connection.execute("SELECT COUNT(*) FROM training_items").fetchone()[0] == 0
    review_evidence(db, int(key), decision="accept", actor="fixture")
    db.close()
    page = client.get("/coaching", base_url="https://coach.invalid", headers=headers)
    assert token(page, "key") == key
    db = Database(path)
    review_evidence(db, int(key), decision="reject", actor="fixture")
    db.close()
    assert (
        client.get(started.location, base_url="https://coach.invalid", headers=headers).status_code
        == 410
    )
