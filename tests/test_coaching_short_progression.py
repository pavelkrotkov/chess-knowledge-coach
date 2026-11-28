"""A completed prepared short-mate rehearsal rotates to a different board."""

import json
import sys

import chess
import chess.engine
import chess.pgn
import pytest

from chess_coach.coaching_practice import choices
from chess_coach.db import Database
from chess_coach.evidence_review import review_evidence
from chess_coach.ingest import ingest_pgn
from chess_coach.lesson_mechanisms import describe
from chess_coach.lesson_source import source
from chess_coach.mate_auto import process_decision
from chess_coach.pipeline_config import PipelineConfig
from chess_coach.pipeline_inputs import engine_identity, game_input
from chess_coach.pipeline_work import run_analysis
from chess_coach.web import create_app
from tests.test_mate_proof import Engine
from tests.test_unified_sessions import token

SUBJECT = "fixture_a"


@pytest.mark.parametrize("form", ["prepared", "async_final"])
def test_private_card_rotates_only_after_complete_unassisted_rehearsal(tmp_path, monkeypatch, form):
    import chess_coach.web_coaching as web_coaching
    from tests.capture_certificate_fixture import project as course_project

    project, path = course_project(tmp_path, "short-project")
    db = Database(path)
    db.initialize()
    monkeypatch.setattr(chess.engine.SimpleEngine, "popen_uci", lambda _: Engine())
    monkeypatch.setattr("chess_coach.mate_auto.short_candidate", lambda *_: True)
    config = PipelineConfig(learner=SUBJECT, engine_path=sys.executable, nodes=100)
    examples = []
    for day in (1, 2, 3):
        board = chess.Board(
            "6k1/5ppp/8/7Q/8/5R2/7r/K4R2 w - - 0 1"
            if day < 3
            else "6k1/5ppp/8/1p5Q/8/5R2/7r/K4R2 w - - 0 1"
        )
        game = chess.pgn.Game()
        game.setup(board)
        game.headers.update(
            {
                "White": SUBJECT,
                "Black": "fixture_b",
                "Result": "*",
                "UTCDate": f"2026.01.0{day}",
                "UTCTime": "12:00:00",
            }
        )
        game.add_variation(board.parse_uci("a1b1"))
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
        process_decision(db, position, SUBJECT)
        evidence = db.connection.execute(
            "SELECT id FROM evidence_mappings WHERE position_id=? AND skill='calculation'",
            (position,),
        ).fetchone()[0]
        inspected = source(db, SUBJECT, {"id": evidence, "position_id": position})
        examples.append(describe(inspected))
        detector_version = inspected["evidence"]["facts"][0]["detector_version"]

    if form == "prepared":
        from chess_coach.tactical_course import build

        with monkeypatch.context() as patch:
            patch.setattr("chess_coach.tactical_course_selection.PER_PAIR", 2)
            patch.setattr("chess_coach.tactical_course.PER_PAIR", 2)
            tactical = build(db, SUBJECT, "test")
        assert [item["kind"] for item in tactical["preview"]["patterns"]] == ["short_mate"]
        assert all(item["mode"] == "conceal" for item in tactical["preview"]["chapters"])
        assert [item["role"] for item in tactical["preview"]["chapters"]] == [
            "explanation",
            "worked",
        ]
        assert "forced mate within two of your moves" in tactical["preview"]["chapters"][0]["pgn"]
        assert "Worked example, ungraded" in tactical["preview"]["chapters"][1]["pgn"]
        assert (
            tactical["preview"]["selection"]["unavailable"][0]["reason"]
            == "related corpus or compatible unfamiliar example unavailable"
        )
        calculation = next(
            item
            for item in tactical["preview"]["selection"]["coverage"]
            if item["skill"] == "calculation"
        )
        assert calculation["examined"] == 2 and calculation["limited"]
        assert tactical["preview"]["selection"]["per_pair_limit"] == 2

        # Reuse the real related-short-mate corpus example with this owned proof.
        from chess_coach.related_mate_source import source_for_evidence
        from chess_coach.tactical_course_budget import Budget, PreviewUnavailable
        from chess_coach.tactical_course_choice import SLICE_SECONDS as SELECTED_SECONDS
        from chess_coach.tactical_export import build as export_course
        from chess_coach.tactical_study_current import revalidate
        from chess_coach.tactical_study_preview import preview as study_preview

        source_mate = source_for_evidence(db, SUBJECT, examples[0]["evidence_id"])
        initial = chess.Board("6k1/1p3ppp/8/7Q/8/5R2/7r/K4R2 b - - 0 1")
        db.connection.execute(
            "INSERT INTO puzzle_corpora(version,source,checksum,state) VALUES(?,?,?,?)",
            ("test", "fixture", "checksum", "staging"),
        )
        corpus = db.connection.execute(
            "SELECT id FROM puzzle_corpora WHERE version=?", ("test",)
        ).fetchone()[0]
        db.connection.execute(
            "INSERT INTO puzzles(puzzle_id,corpus_id,fen,source,solution,rating,rating_deviation,themes_json,objective) "
            "VALUES(?,?,?,?,?,?,?,?,?)",
            (
                "short",
                corpus,
                initial.fen(),
                "https://example.invalid",
                "b7b6 " + source_mate["lines"][0],
                1200,
                80,
                json.dumps(["mateIn2"]),
                "unknown",
            ),
        )
        db.connection.execute(
            "INSERT INTO puzzle_themes VALUES(?,?,?,?)", (corpus, "short", "mateIn2", 1200)
        )
        db.connection.execute("UPDATE puzzle_corpora SET state=? WHERE id=?", ("ready", corpus))
        db.connection.commit()
        default_course = build(db, SUBJECT, "test")
        assert default_course["kind"] == "local-tactical-course-v17"
        assert [item["role"] for item in default_course["preview"]["chapters"]] == [
            "explanation",
            "worked",
            "practice",
        ], default_course["preview"]["selection"]["unavailable"]
        selected_course = build(db, SUBJECT, "test", selected=["calculation:execute"])
        assert selected_course["kind"] == "local-tactical-course-v18"
        assert [item["role"] for item in selected_course["preview"]["chapters"]] == [
            "explanation",
            "worked",
            "practice",
        ]
        practice = selected_course["preview"]["chapters"][2]
        assert practice["source"]["type"] == "corpus" and practice["mode"] == "conceal"
        assert "not a proof against every defense" in practice["pgn"]
        candidate = export_course(
            db, SUBJECT, "test", selected_course, Budget(db, slice_seconds=SELECTED_SECONDS)
        )
        assert study_preview(candidate, candidate["export_sha256"]) == selected_course
        with revalidate(
            path,
            candidate,
            candidate["export_sha256"],
            project_root=project,
            subject=SUBJECT,
            corpus="test",
        ) as check:
            check()

        evidence_id = selected_course["preview"]["patterns"][0]["supporting_sources"][0][
            "evidence_id"
        ]
        review_budget = Budget(db, slice_seconds=SELECTED_SECONDS)
        db.connection.execute("SAVEPOINT mate_course_review")
        try:
            review_evidence(db, evidence_id, decision="reject", actor="fixture")
            with pytest.raises((ValueError, PreviewUnavailable)):
                export_course(db, SUBJECT, "test", selected_course, review_budget)
        finally:
            db.connection.execute("ROLLBACK TO SAVEPOINT mate_course_review")
            db.connection.execute("RELEASE SAVEPOINT mate_course_review")

        from chess_coach.tactical_course_offer import offer
        from chess_coach.tactical_course_publish import publish

        output = project / ".runtime" / "planning" / "mate-course.json"
        publish(output, candidate, Budget(db, slice_seconds=SELECTED_SECONDS), readonly=True)
        offer(
            project,
            path,
            SUBJECT,
            output,
            candidate,
            Budget(db, slice_seconds=SELECTED_SECONDS),
            enabled=True,
        )
        course_app = create_app(
            db_path=path,
            subject=SUBJECT,
            actor="fixture",
            corpus="test",
            login="login",
            origin="https://coach.invalid",
            project_root=project,
        )
        candidate_hash = candidate["export_sha256"]
        page = course_app.test_client().get(
            f"/coaching/tactical-course?version={candidate_hash}&chapter=2",
            base_url="https://coach.invalid",
            headers={"Tailscale-User-Login": "login"},
        )
        evidence = practice["source"]["binding"]["evidence_id"]
        assert page.status_code == 200
        assert f"/evidence/{evidence}/related-mates".encode() in page.data

        # Compare the complete bounded pair with and without history reuse.
        import chess_coach.learner_context as learner_context
        import chess_coach.preview_history as history_module
        import chess_coach.tactical_course_selection as course_selection
        from chess_coach.tactical_course_deadline import PreviewDeadline

        original_boards = learner_context.decision_context_boards

        def measured_pair(reuse):
            starts = {"recurrence": 0, "preview": 0}

            def counted(kind):
                def run(*args, **kwargs):
                    starts[kind] += 1
                    return original_boards(*args, **kwargs)

                return run

            with monkeypatch.context() as patch:
                patch.setattr(learner_context, "decision_context_boards", counted("recurrence"))
                patch.setattr(history_module, "decision_context_boards", counted("preview"))
                if not reuse:
                    patch.setattr(history_module.PreviewHistory, "can_share", lambda *_: False)
                result = course_selection._pair(db, SUBJECT, "calculation", "execute", Budget(db))
            return result, starts

        from chess_coach.tactical_course_budget import Budget

        baseline, before = measured_pair(False)
        optimized, after = measured_pair(True)
        assert baseline == optimized
        assert before["recurrence"] > 0
        assert after["recurrence"] == 0
        assert before["preview"] == after["preview"]
        print("synthetic_course_traversals", {"before": before, "after": after})

        original_evidence = course_selection.evidence

        def deferred_capture(db, subject, skill, operation, *args, **kwargs):
            if (skill, operation) == ("hanging_piece", "execute"):
                raise PreviewDeadline()
            return original_evidence(db, subject, skill, operation, *args, **kwargs)

        with monkeypatch.context() as patch:
            patch.setattr(course_selection, "evidence", deferred_capture)
            partial = build(db, SUBJECT, "test")
        coverage = partial["preview"]["selection"]["coverage"]
        assert coverage[0]["status"] == "deferred: time budget"
        assert coverage[0]["examined"] is None
        assert all(item["status"] == "complete" for item in coverage[1:])
        assert [item["kind"] for item in partial["preview"]["patterns"]] == ["short_mate"]
        assert "Only completed supported pairs" in partial["preview"]["selection"]["scope"]
        assert not db.connection.in_transaction

        original_collect = course_selection.collect_page
        calls = 0

        def interrupted_collect(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise PreviewDeadline()
            return original_collect(*args, **kwargs)

        with monkeypatch.context() as patch:
            patch.setattr(course_selection, "collect_page", interrupted_collect)
            groups, coverage = course_selection.candidates(db, SUBJECT, Budget(db))
        assert calls == 2
        assert not groups
        assert next(row for row in coverage if row["skill"] == "calculation")["status"] == (
            "deferred: time budget"
        )
        assert not db.connection.in_transaction

    lesson = {
        "skill": "calculation",
        "operation": "execute",
        "family": "bounded-mate-observation-mapper",
        "source_version": detector_version,
        "examples": examples,
        "qualification": "Fixture",
        "possible": "Fixture",
        "habit": "Fixture",
        "question": "Fixture",
        "practice": "Fixture",
    }
    preview = {
        "groups": [
            {
                "lesson": lesson,
                "misses": 3,
                "miss_games": 3,
                "from_date": "2026-01-01",
                "to_date": "2026-01-03",
            }
        ],
        "failure_limits": [],
        "excluded": {},
        "coverage": {
            "database_games": 3,
            "database_analysis": {},
            "examined_games": 3,
            "analysis_stages": {},
            "game_limit_reached": False,
            "scan_limit_reached": False,
        },
    }
    monkeypatch.setattr(web_coaching, "report", lambda *_: preview)
    app = create_app(
        db_path=path,
        subject=SUBJECT,
        actor="fixture",
        corpus="test",
        login="fixture",
        origin="https://coach.invalid",
    )
    client = app.test_client()
    headers = {"Tailscale-User-Login": "fixture"}
    origin = headers | {"Origin": "https://coach.invalid"}
    base = "https://coach.invalid"
    page = client.get("/coaching?full=1", base_url=base, headers=headers)
    first_key = token(page, "key")
    assert first_key == str(examples[0]["evidence_id"])
    assert choices(db, SUBJECT, preview)[0]["key"] == first_key
    csrf = token(page, "csrf")

    def begin():
        started = client.post(
            "/unified/start",
            data={
                "csrf": csrf,
                "source_type": "own-game",
                "version": "mate-two-own-v1",
                "key": first_key,
            },
            base_url=base,
            headers=origin,
        )
        assert started.status_code == 303
        return client.get(started.location, base_url=base, headers=headers)

    def move(page, text):
        result = client.post(
            "/unified/move",
            data={
                "csrf": csrf,
                "attempt": token(page, "attempt"),
                "event": token(page, "event"),
                "move": text,
            },
            base_url=base,
            headers=origin,
        )
        assert result.status_code == 303
        return client.get(result.location, base_url=base, headers=headers)

    def root_and_mate(page):
        attempt = token(page, "attempt")
        row = db.connection.execute(
            "SELECT lines_json FROM unified_sessions WHERE attempt_id=?", (attempt,)
        ).fetchone()
        lines = json.loads(row[0])
        root = lines[0][0]
        page = move(page, root)
        event = db.connection.execute(
            "SELECT response_json FROM unified_session_events WHERE attempt_id=? ORDER BY rowid DESC LIMIT 1",
            (attempt,),
        ).fetchone()
        reply = json.loads(event[0])["opponent_move"]
        mate = next(line[2] for line in lines if line[:2] == [root, reply])
        return page, mate

    page, mate = root_and_mate(begin())
    assert token(client.get("/coaching?full=1", base_url=base, headers=headers), "key") == first_key
    hinted = client.post(
        "/unified/hint",
        data={"csrf": csrf, "attempt": token(page, "attempt"), "event": token(page, "event")},
        base_url=base,
        headers=origin,
    )
    page = client.get(hinted.location, base_url=base, headers=headers)
    move(page, mate)
    assert token(client.get("/coaching?full=1", base_url=base, headers=headers), "key") == first_key

    page, mate = root_and_mate(begin())
    assert token(client.get("/coaching?full=1", base_url=base, headers=headers), "key") == first_key
    attempt = token(page, "attempt")
    if form == "async_final":
        board = chess.Board(
            db.connection.execute(
                "SELECT current_fen FROM unified_sessions WHERE attempt_id=?", (attempt,)
            ).fetchone()[0]
        )
        mate = next(
            candidate.uci()
            for candidate in board.legal_moves
            if candidate.uci() != mate and _is_mate(board, candidate)
        )
    completed = move(page, mate)
    if form == "async_final":
        from chess_coach.objective_worker import process

        assert (
            token(client.get("/coaching?full=1", base_url=base, headers=headers), "key")
            == first_key
        )
        assert process(db, SUBJECT)["outcomes"] == {"correct": 1}
        completed = client.get("/unified/" + attempt, base_url=base, headers=headers)
    assert b"checkmate objective was verified" in completed.data
    page = client.get("/coaching?full=1", base_url=base, headers=headers)
    assert token(page, "key") == str(examples[2]["evidence_id"])
    assert b"Try a different position or explore related unfamiliar practice" in page.data
    assert b"Find related short-mate practice for this source" in page.data
    assert choices(db, SUBJECT, preview)[0]["key"] == first_key
    lesson["examples"] = examples[1:]
    page = client.get("/coaching?full=1", base_url=base, headers=headers)
    assert token(page, "key") == str(examples[2]["evidence_id"])
    assert b"Try a different position or explore related unfamiliar practice" in page.data
    assert choices(db, SUBJECT, preview)[0]["key"] == str(examples[1]["evidence_id"])
    assert db.connection.execute("SELECT COUNT(*) FROM training_attempts").fetchone()[0] == 0
    assert db.connection.execute("SELECT COUNT(*) FROM mastery_events").fetchone()[0] == 0

    review_evidence(db, int(first_key), decision="reject", actor="fixture")
    page = client.get("/coaching?full=1", base_url=base, headers=headers)
    assert b"You completed a recent short-mate example" not in page.data
    db.close()


def _is_mate(board, move):
    board.push(move)
    result = board.is_checkmate()
    board.pop()
    return result
