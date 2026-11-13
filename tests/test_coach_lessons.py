"""Grounded coaching and immutable regeneration on synthetic sources."""

from chess_coach.fork_detector import process_decision
from chess_coach.lesson_mechanisms import describe
from chess_coach.lesson_source import source
from tests.test_fork_pipeline import LEARNER, make_game


def _reject_between_course_slices(db, path, subject, group, monkeypatch):
    import sqlite3
    from contextlib import contextmanager

    import pytest

    from chess_coach import tactical_course_resolve
    from chess_coach.tactical_course_budget import Budget, PreviewUnavailable

    budget = Budget(db)
    original_scope = budget.scope
    slices = []

    @contextmanager
    def changed_scope(*, snapshot):
        with original_scope(snapshot=snapshot):
            yield
        slices.append(1)
        if len(slices) == 1:
            with sqlite3.connect(path) as writer:
                writer.execute("UPDATE games SET event=event WHERE id=1")
            from chess_coach.tactical_course_deadline import PreviewDeadline

            raise PreviewDeadline()

    with monkeypatch.context() as patch:
        patch.setattr(budget, "scope", changed_scope)
        with pytest.raises(PreviewUnavailable):
            tactical_course_resolve.own(db, subject, group, budget)
    assert len(slices) == 1


def test_fork_lesson_uses_rechecked_fact_and_legal_line(tmp_path, monkeypatch):
    path = tmp_path / "synthetic.sqlite"
    db, config = make_game(path, monkeypatch)
    result = process_decision(db, 1, LEARNER)
    evidence_id = result["evidence_ids"][0]
    candidate = {"id": evidence_id, "position_id": 1}
    current = source(db, LEARNER, candidate)
    example = describe(current)
    assert example["played"] != "Nc7+"
    assert "Nc7+" in example["facts"][0]
    assert example["evidence_id"] == evidence_id
    assert source(db, "another", candidate) is None

    # A recurring fork lesson admits the next usable shown source without
    # searching the corpus until the learner opens the unfamiliar finder.
    from chess_coach.coaching_practice_source import resolve_example
    from chess_coach.coaching_report import report as coaching_report
    from chess_coach.evidence_review import review_evidence
    from chess_coach.ingest import ingest_pgn
    from chess_coach.objective_fork_contract import VERSION as FORK_VERSION
    from chess_coach.pipeline_inputs import engine_identity, game_input
    from chess_coach.pipeline_work import run_analysis
    from chess_coach.web import create_app

    review_evidence(db, evidence_id, decision="accept", actor="fixture")
    original_pgn = db.connection.execute("SELECT pgn FROM games WHERE id=1").fetchone()[0]
    ingest_pgn(db, original_pgn.replace("2026.01.01", "2026.01.02"))
    second_position = db.connection.execute(
        "SELECT id FROM positions WHERE game_id=2 AND ply=1"
    ).fetchone()[0]
    assert (
        run_analysis(db, 2, game_input(db, 2), config, engine_identity(config.engine_path))[
            "status"
        ]
        == "complete"
    )
    second = process_decision(db, second_position, LEARNER)
    second_id = second["evidence_ids"][0]
    group = next(
        item
        for item in coaching_report(db, LEARNER)["groups"]
        if item["lesson"]["skill"] == "fork" and item["lesson"]["operation"] == "execute"
    )
    lesson = group["lesson"]
    assert group["miss_games"] == 2 and len(lesson["examples"]) == 2
    assert all(resolve_example(db, LEARNER, lesson, item) for item in lesson["examples"])
    assert resolve_example(db, "another", lesson, lesson["examples"][0]) is None

    app = create_app(
        db_path=path,
        subject=LEARNER,
        actor="fixture",
        corpus="test",
        login="fixture-login",
        origin="https://coach.invalid",
    )
    client = app.test_client()
    headers = {"Tailscale-User-Login": "fixture-login"}
    base = "https://coach.invalid"
    assert client.get("/coaching?pattern=fork.execute", base_url=base).status_code == 403
    import pytest

    import chess_coach.coaching_practice_source as practice_source
    import chess_coach.related_fork_assessment_finder as finder

    original_resolve = practice_source.resolve_source

    def skip_second(db, kind, version, key, *, subject=None):
        if kind == "own-game" and version == FORK_VERSION and key == str(second_id):
            raise ValueError("synthetic unsupported source")
        return original_resolve(db, kind, version, key, subject=subject)

    before = db.connection.execute("PRAGMA data_version").fetchone()[0]
    counts = {
        table: db.connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        for table in ("unified_sessions", "evidence_mappings", "mastery_states", "training_items")
    }
    with monkeypatch.context() as patch:
        patch.setattr(practice_source, "resolve_source", skip_second)
        patch.setattr(
            finder,
            "selection",
            lambda *_args: (_ for _ in ()).throw(
                AssertionError("coaching GET searched the fork corpus")
            ),
        )
        page = client.get("/coaching?pattern=fork.execute", base_url=base, headers=headers)
        full = client.get("/coaching?full=1", base_url=base, headers=headers)
    assert page.status_code == full.status_code == 200
    assert b"<h3>Finding forks</h3>" in page.data and b"2 independent games" in page.data
    assert b"Practice this source position" in page.data and b"practice is cued" in page.data
    assert b"Rehearse this fork" in page.data
    assert f'name="version" value="{FORK_VERSION}"'.encode() in page.data
    assert f'name="key" value="{evidence_id}"'.encode() in page.data
    assessment = f"/evidence/{evidence_id}/related-forks/find-verified"
    assert assessment.encode() in page.data and b"bounded search may find no match" in page.data
    assert b"<h3>Finding forks</h3>" in full.data and assessment.encode() in full.data
    with monkeypatch.context() as patch:
        patch.setattr(practice_source, "resolve_source", skip_second)
        patch.setattr("chess_coach.web_protection_plan.admissible", lambda *_args: None)
        patch.setattr("chess_coach.web_protection_plan.report", lambda *_args: None)
        patch.setattr(finder, "selection", lambda *_args: pytest.fail("unexpected corpus search"))
        focus = client.get("/plan/next-focus", base_url=base, headers=headers)
    assert focus.data.count(b"Next focus: finding forks") == 1
    assert b"<title>Next practice focus \xe2\x80\x94 Chess coach</title>" in focus.data
    assert b"2 independent games" in focus.data and b"Rehearse this fork" in focus.data
    assert assessment.encode() in focus.data
    assert db.connection.execute("PRAGMA data_version").fetchone()[0] == before
    assert {
        table: db.connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        for table in counts
    } == counts

    # Reproduce the measured overrun without waiting: each stage fits its
    # three-second slice, but together they exceed the old shared deadline.
    import sqlite3
    import time
    from types import SimpleNamespace

    from chess_coach import coaching_quick, coaching_quick_run

    clock = [time.monotonic()]
    real_build, real_choose = coaching_quick_run.build, coaching_quick_run.choose

    def measured_build(db, learner, pair, check):
        result = real_build(db, learner, pair, check)
        if pair == ("fork", "execute"):
            clock[0] += 2.0
        return result

    def measured_choose(db, learner, group, check):
        result = real_choose(db, learner, group, check)
        clock[0] += 1.25
        check()
        return result

    with monkeypatch.context() as patch:
        patch.setattr(coaching_quick_run, "time", SimpleNamespace(monotonic=lambda: clock[0]))
        patch.setattr(coaching_quick_run, "build", measured_build)
        patch.setattr(coaching_quick_run, "choose", measured_choose)
        start = clock[0]
        focused = client.get("/coaching?pattern=fork.execute", base_url=base, headers=headers)
        assert clock[0] - start > coaching_quick_run.PAIR_SECONDS
        assert b"Rehearse this fork" in focused.data
        assert b"Find an unfamiliar fork assessment for this source" in focused.data
        assert b"Some practice links could not be checked" not in focused.data
        clock[0] = time.monotonic()
        patch.setattr("chess_coach.web_protection_plan.admissible", lambda *_args: None)
        patch.setattr("chess_coach.web_protection_plan.report", lambda *_args: None)
        focus = client.get("/plan/next-focus", base_url=base, headers=headers)
        assert b"Next focus: finding forks" in focus.data
        assert b"Find an unfamiliar fork assessment for this source" in focus.data
        clock[0] = time.monotonic()
        patch.setattr(coaching_quick, "TOTAL_SECONDS", 2.5)
        limited, actions = coaching_quick.report(db, LEARNER, (("fork", "execute"),))
        assert limited["quick"]["practice_limited"] and actions[0] is None
        patch.setattr(coaching_quick, "TOTAL_SECONDS", 12.0)
        clock[0] = time.monotonic()
        multi, actions = coaching_quick.report(
            db, LEARNER, (("fork", "execute"), ("mate_in_one", "execute"))
        )
        assert multi["quick"]["practice_limited"] and actions[0] is None

    def changed_choose(*args):
        result = real_choose(*args)
        with sqlite3.connect(path) as writer:
            writer.execute("UPDATE games SET event=event WHERE id=1")
        return result

    with monkeypatch.context() as patch:
        patch.setattr(coaching_quick_run, "choose", changed_choose)
        changed = client.get("/coaching?pattern=fork.execute", base_url=base, headers=headers)
    assert b"The source changed or the quick checks were unavailable" in changed.data
    assert b"Rehearse this fork" not in changed.data

    # Unsupported sources remain visible without practice or finder actions.
    with monkeypatch.context() as patch:
        patch.setattr(
            practice_source,
            "resolve_source",
            lambda *_a, **_k: (_ for _ in ()).throw(ValueError("synthetic unavailable")),
        )
        unavailable = client.get("/coaching?pattern=fork.execute", base_url=base, headers=headers)
    assert b"Finding forks" in unavailable.data and b"Practice is unavailable" in unavailable.data
    assert b"Find an unfamiliar fork assessment for this source" not in unavailable.data

    with client.session_transaction(base_url=base) as browser:
        csrf = browser["csrf"]
    started = client.post(
        "/unified/start",
        base_url=base,
        headers=headers | {"Origin": base},
        data={
            "csrf": csrf,
            "source_type": "own-game",
            "version": FORK_VERSION,
            "key": str(evidence_id),
        },
    )
    assert started.status_code == 303
    practice = client.get(started.location, base_url=base, headers=headers)
    assert b"Execute the named fork" in practice.data
    empty = client.get(assessment, base_url=base, headers=headers)
    assert empty.status_code == 200 and b"No certified unfamiliar fork" in empty.data

    # The same source can form a private worked course and a source-bound
    # unfamiliar chapter, without creating any training or Study records.
    import json
    from copy import deepcopy

    from chess_coach.tactical_course import build as tactical_preview
    from chess_coach.tactical_course_budget import Budget
    from chess_coach.tactical_export import build as tactical_export
    from chess_coach.tactical_study_current import revalidate
    from chess_coach.tactical_study_preview import preview as study_preview

    missing_corpus = tactical_preview(db, LEARNER, "not-configured")
    assert missing_corpus["preview"]["selection"]["unavailable"][0]["reason"] == (
        "fork corpus unavailable"
    )
    missing_export = tactical_export(db, LEARNER, "not-configured", missing_corpus, Budget(db))
    assert study_preview(missing_export, missing_export["export_sha256"]) == missing_corpus

    db.connection.execute(
        "INSERT INTO puzzle_corpora(version,source,checksum,state) VALUES(?,?,?,?)",
        ("test", "https://database.lichess.org/", "fixture-checksum", "staging"),
    )
    corpus_id = db.connection.execute(
        "SELECT id FROM puzzle_corpora WHERE version='test'"
    ).fetchone()[0]
    solution = "h7h6 b5c7 e8f8 c7a8"
    db.connection.execute(
        """INSERT INTO puzzles(puzzle_id,corpus_id,fen,source,solution,rating,rating_deviation,
        themes_json,objective) VALUES(?,?,?,?,?,?,?,?,'unknown')""",
        (
            "fixture-fork",
            corpus_id,
            "r3k3/7p/8/1N6/8/8/6P1/7K b - - 0 1",
            "https://example.invalid",
            solution,
            1200,
            80,
            '["fork"]',
        ),
    )
    db.connection.execute(
        "INSERT INTO puzzle_themes VALUES(?,?,'fork',1200)", (corpus_id, "fixture-fork")
    )
    db.connection.execute("UPDATE puzzle_corpora SET state='ready' WHERE id=?", (corpus_id,))
    db.connection.commit()
    before_course = db.connection.total_changes
    course = tactical_preview(db, LEARNER, "test")
    assert course["kind"] == "local-tactical-course-v4"
    pattern = course["preview"]["patterns"][0]
    assert pattern["kind"] == "fork" and pattern["independent_games"] == 2
    assert pattern["local_challenge"].endswith("/related-forks/find-verified")
    own, related = course["preview"]["chapters"]
    assert missing_corpus["preview"]["chapters"][0] == own
    assert own["source"]["evidence_id"] in {evidence_id, second_id}
    assert own["mode"] == related["mode"] == "conceal"
    assert own["orientation"] == "white" and "attacks two valuable targets" in own["pgn"]
    assert "Worked example, ungraded" in related["pgn"] and "CC0" in related["pgn"]
    exported = tactical_export(db, LEARNER, "test", course, Budget(db))
    assert exported["kind"] == "local-tactical-course-export-v4"
    assert study_preview(exported, exported["export_sha256"]) == course
    monkeypatch.setenv("CHESS_SUBJECT", LEARNER)
    monkeypatch.setenv("CHESS_CORPUS", "test")
    with revalidate(path, exported, exported["export_sha256"]) as check:
        check()

    # A commit between the source and chapter slices invalidates the preview.
    from chess_coach import tactical_course_resolve
    from chess_coach.tactical_course_budget import PreviewUnavailable

    _reject_between_course_slices(db, path, LEARNER, group, monkeypatch)
    before_course = db.connection.total_changes
    with monkeypatch.context() as patch:
        patch.setattr("chess_coach.tactical_course_related.fork_selection", lambda *_a, **_k: None)
        without_related = tactical_preview(db, LEARNER, "test")
    assert len(without_related["preview"]["chapters"]) == 1
    assert without_related["preview"]["selection"]["unavailable"][0]["reason"] == (
        "fork corpus unavailable"
    )
    assert without_related["preview"]["chapters"][0] == own
    # A rehashed chapter with altered source binding is still rejected.
    from chess_coach.course_preview import preview_hash

    altered = deepcopy(course)
    altered["preview"]["chapters"][1]["source"]["binding"]["rank_version"] = "changed"
    altered["preview_sha256"] = preview_hash(altered["preview"])
    with pytest.raises(ValueError):
        tactical_export(db, LEARNER, "test", altered, Budget(db))
    omitted_export = tactical_export(db, LEARNER, "test", without_related, Budget(db))
    assert study_preview(omitted_export, omitted_export["export_sha256"]) == without_related

    from chess_coach import tactical_course_familiar_games
    from chess_coach.tactical_course_familiar_games import FamiliarityLimit

    assert issubclass(FamiliarityLimit, ValueError)
    with monkeypatch.context() as patch:
        patch.setattr(tactical_course_familiar_games, "LIMIT", 1)
        capped_games = tactical_preview(db, LEARNER, "test")
    assert capped_games["preview"]["chapters"] == [own]
    assert capped_games["preview"]["selection"]["unavailable"][0]["reason"] == (
        "familiarity history exceeds the bounded scan"
    )
    capped_export = tactical_export(db, LEARNER, "test", capped_games, Budget(db))
    assert study_preview(capped_export, capped_export["export_sha256"]) == capped_games
    with monkeypatch.context() as patch:
        patch.setattr(tactical_course_familiar_games, "LIMIT", 1)
        with pytest.raises(FamiliarityLimit):
            tactical_export(db, LEARNER, "test", course, Budget(db))

    from chess_coach.tactical_course_deadline import PreviewDeadline

    with monkeypatch.context() as patch:
        patch.setattr(
            "chess_coach.tactical_course_related.fork_selection",
            lambda *_a, **_k: (_ for _ in ()).throw(PreviewDeadline()),
        )
        timed = tactical_preview(db, LEARNER, "test")
    assert timed["preview"]["chapters"] == [own]
    assert timed["preview"]["selection"]["unavailable"][0]["reason"] == (
        "related matching deferred: time budget"
    )
    timed_export = tactical_export(db, LEARNER, "test", timed, Budget(db))
    assert study_preview(timed_export, timed_export["export_sha256"]) == timed

    # Unexpected source failures still fail closed for every matcher.
    with monkeypatch.context() as patch:
        patch.setattr(
            tactical_course_resolve,
            "familiarity",
            lambda *_a: (_ for _ in ()).throw(ValueError("source changed")),
        )
        with pytest.raises(PreviewUnavailable):
            tactical_course_resolve.related(db, LEARNER, "test", {"kind": "fork"}, Budget(db))
    assert db.connection.total_changes == before_course

    # An already encountered prompt is no longer an unfamiliar course source.
    db.connection.execute(
        """INSERT INTO puzzle_sessions(attempt_id,corpus_version,corpus_checksum,puzzle_id,
        initial_fen,solution,current_fen,next_index,status,hints_used,started_at)
        VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
        (
            "familiar-fork",
            "test",
            "fixture-checksum",
            "fixture-fork",
            "r3k3/7p/8/1N6/8/8/6P1/7K b - - 0 1",
            solution,
            "r3k3/7p/8/1N6/8/8/6P1/7K b - - 0 1",
            0,
            "active",
            0,
            "2026-01-01",
        ),
    )
    db.connection.commit()
    familiar_course = tactical_preview(db, LEARNER, "test")
    assert familiar_course["preview"]["chapters"] == [own]
    assert familiar_course["preview"]["selection"]["unavailable"][0]["reason"] == (
        "no compatible unfamiliar fork in the bounded scan"
    )
    familiar_export = tactical_export(db, LEARNER, "test", familiar_course, Budget(db))
    assert study_preview(familiar_export, familiar_export["export_sha256"]) == familiar_course
    from chess_coach import tactical_course_familiar

    with monkeypatch.context() as patch:
        patch.setattr(tactical_course_familiar, "LIMIT", 0)
        capped_legacy = tactical_preview(db, LEARNER, "test")
    assert capped_legacy["preview"]["chapters"] == [own]
    assert capped_legacy["preview"]["selection"]["unavailable"][0]["reason"] == (
        "familiarity history exceeds the bounded scan"
    )
    with pytest.raises(ValueError):
        tactical_export(db, LEARNER, "test", course, Budget(db))
    db.connection.execute("DELETE FROM puzzle_sessions WHERE attempt_id='familiar-fork'")
    db.connection.commit()

    # Both rank orders retain real owned fork and capture chapters when the
    # shared familiarity history reaches its limit.
    import chess
    import chess.engine
    import chess.pgn

    from chess_coach import tactical_course, tactical_course_familiar
    from chess_coach.material_detector import process_decision as material_decision
    from chess_coach.tactical_course_selection import candidates
    from tests.test_material_pipeline import Engine as MaterialEngine

    with monkeypatch.context() as patch:
        patch.setattr(chess.engine.SimpleEngine, "popen_uci", lambda *_: MaterialEngine())
        for day in (3, 4):
            board = chess.Board("4k3/8/8/8/3q4/8/8/3RK3 w - - 0 1")
            game = chess.pgn.Game()
            game.setup(board)
            game.headers.update(
                {
                    "White": LEARNER,
                    "Black": "fixture_opponent",
                    "Result": "*",
                    "UTCDate": f"2026.01.0{day}",
                    "UTCTime": "12:00:00",
                }
            )
            node = game.add_variation(board.parse_uci("e1f1"))
            node.add_variation(chess.Move.from_uci("e8f8"))
            ingest_pgn(db, str(game))
            game_id = db.connection.execute("SELECT MAX(id) FROM games").fetchone()[0]
            position_id = db.connection.execute(
                "SELECT id FROM positions WHERE game_id=? AND ply=1", (game_id,)
            ).fetchone()[0]
            assert (
                run_analysis(
                    db,
                    game_id,
                    game_input(db, game_id),
                    config,
                    engine_identity(config.engine_path),
                )["status"]
                == "complete"
            )
            material_decision(db, position_id, LEARNER)
    groups, coverage = candidates(db, LEARNER, Budget(db))
    capture_group = next(g for g in groups if g["lesson"]["skill"] == "hanging_piece")
    fork_group = next(g for g in groups if g["lesson"]["skill"] == "fork")

    # The selected snapshot is reused only inside its original read transaction.
    from chess_coach import coaching_practice_source, tactical_course_chapters

    resolve_source = coaching_practice_source.resolve_source
    resolutions = []

    def counted_resolution(*args, **kwargs):
        assert args[0].connection.in_transaction
        resolutions.append(1)
        return resolve_source(*args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(coaching_practice_source, "resolve_source", counted_resolution)
        patch.setattr(
            tactical_course_chapters,
            "resolve_source",
            lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("duplicate source resolution")),
        )
        assert tactical_course_chapters.owned(db, LEARNER, capture_group)
        assert len(resolutions) == 1
    with monkeypatch.context() as patch:
        patch.setattr(
            tactical_course, "candidates", lambda *_a: ([fork_group, capture_group], coverage)
        )
        original_owned = tactical_course_resolve.owned

        def deferred_one(db, subject, group, **kwargs):
            if group["lesson"]["skill"] == "fork":
                raise PreviewDeadline()
            return original_owned(db, subject, group, **kwargs)

        patch.setattr(tactical_course_resolve, "owned", deferred_one)
        deferred = tactical_preview(db, LEARNER, "test")
        assert [p["kind"] for p in deferred["preview"]["patterns"]] == ["capture"]
        assert any(
            item["reason"] == "owned source deferred: time budget"
            for item in deferred["preview"]["selection"]["unavailable"]
        )
        deferred_export = tactical_export(db, LEARNER, "test", deferred, Budget(db))
        assert study_preview(deferred_export, deferred_export["export_sha256"]) == deferred
        previous_deferred = deepcopy(deferred)
        previous_deferred["kind"] = previous_deferred["preview"]["kind"] = (
            "local-tactical-course-v3"
        )
        previous_deferred["preview"]["policy"] = "provisional-recurring-tactics-v3"
        previous_deferred["preview_sha256"] = preview_hash(previous_deferred["preview"])
        with pytest.raises(ValueError):
            tactical_export(db, LEARNER, "test", previous_deferred, Budget(db))

        from chess_coach import ops_tactical_course

        patch.setattr(ops_tactical_course, "paths", lambda _root, output: (path, output))
        patch.setenv("CHESS_SUBJECT", LEARNER)
        patch.setenv("CHESS_CORPUS", "test")
        output = tmp_path / "deferred-course.json"
        ops_tactical_course.prepare(tmp_path, output)
        assert json.loads(output.read_text()) == deferred
        patch.setattr(
            tactical_course_resolve,
            "owned",
            lambda *_a, **_k: (_ for _ in ()).throw(PreviewDeadline()),
        )
        with pytest.raises(PreviewUnavailable):
            tactical_preview(db, LEARNER, "test")
    original_games = tactical_course_familiar._games
    scans = []

    def counted_games(*args):
        scans.append(1)
        return original_games(*args)

    with monkeypatch.context() as patch:
        patch.setattr(tactical_course_familiar_games, "LIMIT", 1)
        patch.setattr(tactical_course_familiar, "_games", counted_games)
        for index, order in enumerate(((capture_group, fork_group), (fork_group, capture_group))):
            patch.setattr(tactical_course, "candidates", lambda *_a, order=order: (order, coverage))
            mixed = tactical_preview(db, LEARNER, "test")
            assert [p["kind"] for p in mixed["preview"]["patterns"]] == (
                ["capture", "fork"] if index == 0 else ["fork", "capture"]
            )
            assert len(mixed["preview"]["chapters"]) == 2
            assert all(c["source"]["type"] == "own-game" for c in mixed["preview"]["chapters"])
            assert [u["reason"] for u in mixed["preview"]["selection"]["unavailable"]] == [
                "familiarity history exceeds the bounded scan"
            ] * 2
            assert len(scans) == index + 1
            mixed_export = tactical_export(db, LEARNER, "test", mixed, Budget(db))
            assert study_preview(mixed_export, mixed_export["export_sha256"]) == mixed
        wrong = deepcopy(mixed)
        wrong["preview"]["selection"]["unavailable"].append(
            {
                "skill": "hanging_piece",
                "operation": "prevent",
                "reason": "familiarity history exceeds the bounded scan",
            }
        )
        wrong["preview_sha256"] = preview_hash(wrong["preview"])
        with pytest.raises(ValueError):
            tactical_export(db, LEARNER, "test", wrong, Budget(db))
        limited_budget = Budget(db)
        with pytest.raises(FamiliarityLimit):
            tactical_course_familiar.familiarity(db, LEARNER, limited_budget)
        with pytest.raises(ValueError, match="subject changed"):
            tactical_course_familiar.familiarity(db, "another", limited_budget)

    second_example = next(item for item in lesson["examples"] if item["evidence_id"] == second_id)
    review_evidence(db, second_id, decision="reject", actor="fixture")
    assert resolve_example(db, LEARNER, lesson, second_example) is None
    with pytest.raises(ValueError):
        tactical_export(db, LEARNER, "test", course, Budget(db))

    db.connection.execute(
        "UPDATE detector_runs SET status='superseded' WHERE id=?", (result["detector_run_id"],)
    )
    db.connection.commit()
    assert source(db, LEARNER, candidate) is None
    first_example = next(item for item in lesson["examples"] if item["evidence_id"] == evidence_id)
    assert resolve_example(db, LEARNER, lesson, first_example) is None
    with monkeypatch.context() as patch:
        patch.setattr("chess_coach.web_protection_plan.admissible", lambda *_args: None)
        patch.setattr("chess_coach.web_protection_plan.report", lambda *_args: None)
        stale_focus = client.get("/plan/next-focus", base_url=base, headers=headers)
    assert b"Optional practice: finding forks" not in stale_focus.data
    db.close()
    _fork_prevention_coaching(tmp_path, monkeypatch)


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


def _fork_prevention_coaching(tmp_path, monkeypatch):
    import chess
    import chess.engine
    import chess.pgn

    from chess_coach.coaching_fork_defense import actions
    from chess_coach.coaching_practice import choices
    from chess_coach.coaching_report import report
    from chess_coach.evidence_review import review_evidence
    from chess_coach.fork_defense_detector import process_decision as defense_decision
    from chess_coach.ingest import ingest_pgn
    from chess_coach.objective_fork_avoidance_contract import VERSION as AVOIDANCE
    from chess_coach.objective_fork_defense_contract import VERSION as DEFENSE
    from chess_coach.pipeline_inputs import engine_identity, game_input
    from chess_coach.pipeline_work import run_analysis
    from chess_coach.web import create_app
    from tests.test_fork_defense_pipeline import LEARNER, Engine, make_game

    path = tmp_path / "coaching-fork-defense.sqlite"
    db, config = make_game(path, monkeypatch, failure=True)
    anchored = defense_decision(db, 1, LEARNER)["evidence_ids"][0]
    board = chess.Board("7k/6p1/8/8/1n6/8/7P/1R2K3 w - - 0 1")
    game = chess.pgn.Game.from_board(board)
    game.headers.update(
        {
            "White": LEARNER,
            "Black": "fixture_opponent",
            "Result": "*",
            "UTCDate": "2026.01.02",
            "UTCTime": "12:00:00",
        }
    )
    node = game.add_variation(board.parse_uci("b1a1"))
    board.push_uci("b1a1")
    node.add_variation(board.parse_uci("b4c2"))
    monkeypatch.setattr(
        chess.engine.SimpleEngine,
        "popen_uci",
        lambda _: Engine(["b1b3", "h8g8", "e1f1", "g7g6"], ["b1a1", "b4c2", "e1f1", "c2a1"]),
    )
    ingest_pgn(db, str(game))
    assert (
        run_analysis(db, 2, game_input(db, 2), config, engine_identity(config.engine_path))[
            "status"
        ]
        == "complete"
    )
    position = db.connection.execute(
        "SELECT id FROM positions WHERE game_id=2 AND ply=1"
    ).fetchone()[0]
    avoidance = defense_decision(db, position, LEARNER)["evidence_ids"][0]

    preview = report(db, LEARNER)
    group = next(
        group for group in preview["groups"] if group["lesson"]["family"] == "fork-defense-mapper"
    )
    assert group["miss_games"] == 2 and len(group["lesson"]["examples"]) == 2
    assert choices(db, LEARNER, {"groups": [group]}) == [None]
    admitted = actions(db, LEARNER, {"groups": [group]})[0]
    assert {item["kind"] for item in admitted.values()} == {"fork_defense", "fork_avoidance"}
    assert anchored in admitted
    assert admitted[avoidance]["kind"] == "fork_avoidance"

    app = create_app(
        db_path=path,
        subject=LEARNER,
        actor="fixture",
        corpus="missing",
        login="fixture-login",
        origin="https://coach.invalid",
    )
    client = app.test_client()
    base, headers = "https://coach.invalid", {"Tailscale-User-Login": "fixture-login"}
    assert client.get("/coaching?pattern=fork.prevent", base_url=base).status_code == 403
    import chess_coach.web_related_fork_avoidance as avoidance_view
    import chess_coach.web_related_fork_prevention as prevention_view

    before = db.connection.execute("PRAGMA data_version").fetchone()[0]
    with monkeypatch.context() as patch:

        def no_search(*_args, **_kwargs):
            raise AssertionError("coaching GET searched the corpus")

        patch.setattr(avoidance_view, "preview", no_search)
        patch.setattr(prevention_view, "preview", no_search)
        quick = client.get("/coaching?pattern=fork.prevent", base_url=base, headers=headers)
        full = client.get("/coaching?full=1", base_url=base, headers=headers)
    assert quick.status_code == full.status_code == 200
    for page in (quick, full):
        assert b"Defending against forks" in page.data and b"2 independent games" in page.data
        assert b"Rehearse defending an existing threat" in page.data
        assert b"Rehearse avoiding a created threat" in page.data
        assert b"exercise is cued" in page.data
        assert f'name="version" value="{DEFENSE}"'.encode() in page.data
        assert f'name="version" value="{AVOIDANCE}"'.encode() in page.data
        assert f"/evidence/{anchored}/related-fork-preventions".encode() in page.data
        assert f"/evidence/{avoidance}/related-fork-avoidances".encode() in page.data
    assert db.connection.execute("PRAGMA data_version").fetchone()[0] == before
    # Both existing routes admit their own source and keep an honest empty result.
    with client.session_transaction(base_url=base) as browser:
        csrf = browser["csrf"]
    for eid, version, suffix, phrase in (
        (anchored, DEFENSE, "related-fork-preventions", b"Defend against the anchored knight fork"),
        (avoidance, AVOIDANCE, "related-fork-avoidances", b"Avoid the created knight fork"),
    ):
        empty = client.get(f"/evidence/{eid}/{suffix}", base_url=base, headers=headers)
        assert empty.status_code == 200 and b"corpus unavailable" in empty.data
        response = client.post(
            "/unified/start",
            base_url=base,
            headers=headers | {"Origin": base},
            data={"csrf": csrf, "source_type": "own-game", "version": version, "key": str(eid)},
        )
        assert response.status_code == 303
        assert phrase in client.get(response.location, base_url=base, headers=headers).data

    # A rejected source and a superseded source fail closed.
    review_evidence(db, avoidance, decision="reject", actor="fixture")
    assert set(actions(db, LEARNER, {"groups": [group]})[0]) == {anchored}
    run = db.connection.execute(
        "SELECT run_id FROM detector_facts WHERE id=(SELECT fact_id FROM evidence_fact_links WHERE evidence_id=? LIMIT 1)",
        (anchored,),
    ).fetchone()[0]
    db.connection.execute("UPDATE detector_runs SET status='superseded' WHERE id=?", (run,))
    db.connection.commit()
    assert actions(db, LEARNER, {"groups": [group]}) == [{}]
    db.close()


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
    assert preview["kind"] == "local-tactical-course-v4"
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
    offer_slot = planning / "tactical-course-offer.json"
    with monkeypatch.context() as patch:
        patch.setattr(
            "chess_coach.ops_tactical_export.build",
            lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("reserved export was built")),
        )
        for reserved in (offer_slot, planning / "tactical-study-request.json"):
            for offered_flag in (False, True):
                with pytest.raises(ValueError):
                    export_candidate(
                        project,
                        first_preview,
                        preview["preview_sha256"],
                        reserved,
                        offer=offered_flag,
                    )
            with pytest.raises(ValueError):
                prepare(project, reserved)
            assert not reserved.exists()
    export_candidate(project, first_preview, preview["preview_sha256"], export_path, offer=True)
    exported_bytes = export_path.read_bytes()
    original_offer = offer_slot.read_bytes()
    for index, existing in enumerate((exported_bytes, b"null")):
        offer_slot.write_bytes(existing)
        refused_output = planning / f"refused-offer-{index}.json"
        with pytest.raises(ValueError):
            export_candidate(
                project, first_preview, preview["preview_sha256"], refused_output, offer=True
            )
        assert offer_slot.read_bytes() == existing and refused_output.exists()
    offer_slot.write_bytes(original_offer)
    exported = json.loads(exported_bytes)
    assert exported["kind"] == "local-tactical-course-export-v4"
    assert exported["export_sha256"] == preview_hash(exported["export"])
    assert exported["export"]["preview_sha256"] == preview["preview_sha256"]
    assert exported["export"]["chapters"] == preview["preview"]["chapters"]
    assert exported["export"]["selection"] == preview["preview"]["selection"]

    course_app = create_app(
        project_root=project,
        db_path=path,
        subject=LEARNER,
        actor="fixture",
        corpus="test",
        login="login",
        origin="https://coach.invalid",
    )
    course_client = course_app.test_client()
    course_headers = {"Tailscale-User-Login": "login"}
    course_url = "/coaching/tactical-course"
    assert course_client.get(course_url, base_url="https://coach.invalid").status_code == 403
    before_course_page = db.connection.total_changes
    with monkeypatch.context() as patch:
        patch.setattr(
            "chess_coach.tactical_export.build",
            lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("rebuilt course on GET")),
        )
        shown = course_client.get(
            course_url, base_url="https://coach.invalid", headers=course_headers
        )
    assert shown.status_code == 200
    assert exported["export_sha256"].encode() in shown.data
    assert b"Prepared tactical course" in shown.data and b"Show the supplied line" in shown.data
    assert b"View the source decision" in shown.data and b"ungraded" in shown.data
    assert b"Recorded omissions" in shown.data and db.connection.total_changes == before_course_page
    assert (
        course_client.get(
            course_url + "?version=" + "0" * 64,
            base_url="https://coach.invalid",
            headers=course_headers,
        ).status_code
        == 409
    )
    course_app.config["SUBJECT"] = "another_learner"
    assert (
        b"No current prepared course"
        in course_client.get(
            course_url, base_url="https://coach.invalid", headers=course_headers
        ).data
    )
    course_app.config["SUBJECT"] = LEARNER
    other_database = path.parent / "other.sqlite"
    other_database.touch()
    course_app.config["DB_PATH"] = str(other_database)
    assert (
        b"No current prepared course"
        in course_client.get(
            course_url, base_url="https://coach.invalid", headers=course_headers
        ).data
    )
    course_app.config["DB_PATH"] = str(path)
    changed_export = json.loads(exported_bytes)
    changed_export["export"]["ranking_qualification"] = "changed"
    export_path.chmod(0o600)
    export_path.write_text(json.dumps(changed_export))
    assert (
        b"No current prepared course"
        in course_client.get(
            course_url, base_url="https://coach.invalid", headers=course_headers
        ).data
    )
    export_path.write_bytes(exported_bytes)
    export_path.chmod(0o400)

    # Request only the exact offered course; an incomplete attempt retries the same file.
    from chess_coach import tactical_study_worker
    from chess_coach.study_remote import StudyError

    with monkeypatch.context() as patch:
        patch.setenv("LICHESS_STUDY_TOKEN", "fixture-token")
        patch.setenv("CHESS_PROJECT_ROOT", str(project))
        with course_client.session_transaction(base_url="https://coach.invalid") as session:
            course_csrf = session["csrf"]
        submit = course_url + "/study"
        post_headers = course_headers | {"Origin": "https://coach.invalid"}
        payload = {"csrf": course_csrf, "version": exported["export_sha256"]}
        assert (
            course_client.post(
                submit,
                data={"version": payload["version"]},
                base_url="https://coach.invalid",
                headers=post_headers,
            ).status_code
            == 403
        )
        assert (
            course_client.post(
                submit,
                data={**payload, "version": "0" * 64},
                base_url="https://coach.invalid",
                headers=post_headers,
            ).status_code
            == 409
        )
        assert (
            course_client.post(
                submit, data=payload, base_url="https://coach.invalid", headers=post_headers
            ).status_code
            == 303
        )
        request_slot = planning / "tactical-study-request.json"
        first_request = request_slot.read_bytes()
        assert (
            course_client.post(
                submit, data=payload, base_url="https://coach.invalid", headers=post_headers
            ).status_code
            == 303
        )
        assert request_slot.read_bytes() == first_request
        calls = []

        def incomplete(_root, saved, version, *, queued):
            calls.append((saved, version, queued))
            raise StudyError("incomplete")

        patch.setattr(tactical_study_worker, "publish_locked", incomplete)
        assert tactical_study_worker.run(db, LEARNER, project)
        assert json.loads(request_slot.read_text())["state"] == "incomplete"
        assert (
            b"Publication is incomplete"
            in course_client.get(
                course_url, base_url="https://coach.invalid", headers=course_headers
            ).data
        )
        assert calls == [(export_path, payload["version"], True)]
        from chess_coach import study_worker

        db.connection.execute(
            "INSERT OR IGNORE INTO pipeline_health(id,status,started_at,sync_status) VALUES(1,?,?,?)",
            ("complete", "2026-01-01", "complete"),
        )
        db.connection.execute(
            "UPDATE pipeline_health SET retry_until = ? WHERE id = 1",
            ("2999-01-01T00:00:00+00:00",),
        )
        db.connection.commit()
        saved_request = request_slot.read_bytes()
        study_worker.dispatch(db, LEARNER, project)
        assert request_slot.read_bytes() == saved_request and len(calls) == 1
        db.connection.execute("UPDATE pipeline_health SET retry_until = NULL WHERE id = 1")
        db.connection.commit()
        offer_slot.write_bytes(b"{}")
        study_worker.dispatch(db, LEARNER, project)
        offer_slot.write_bytes(original_offer)
        assert calls == [(export_path, payload["version"], True)] * 2
        with patch.context() as broken_slot:
            broken_slot.setattr(
                study_worker, "read", lambda _path: (_ for _ in ()).throw(ValueError())
            )
            opening_calls = []
            broken_slot.setattr(
                study_worker, "opening_run", lambda *_args: opening_calls.append(True)
            )
            study_worker.dispatch(db, LEARNER, project)
            assert opening_calls == [True]
        from chess_coach.deep_selection_source import learner_key

        chapters = exported["export"]["chapters"]
        ids = [f"{index:08d}" for index in range(len(chapters))]
        receipt = {
            "learner_key": learner_key(LEARNER),
            "course_sha256": payload["version"],
            "complete": True,
            "privacy_verified": True,
            "anonymous_verified": True,
            "ordered_verified": True,
            "chapter_ids": ids,
            "entry_chapter": ids[0],
            "chapters": ["done"] * len(ids),
            "chapter_modes": [chapter["mode"] for chapter in chapters],
            "study": "Abcd1234",
            "verified_at": "2026-01-01T00:00:00+00:00",
        }
        with patch.context() as receipt_patch:
            receipt_patch.setattr("chess_coach.tactical_study_receipt.read", lambda _path: receipt)
            study_worker.dispatch(db, LEARNER, project)
            assert len(calls) == 2 and json.loads(request_slot.read_text())["state"] == "complete"
            assert (
                b"Open the verified private Study"
                in course_client.get(
                    course_url, base_url="https://coach.invalid", headers=course_headers
                ).data
            )

    # A saved v1 preview retains its exact scope, hash, export and Study reconstruction.
    from chess_coach.tactical_course_budget import Budget
    from chess_coach.tactical_export import build as build_export
    from chess_coach.tactical_study_preview import preview as study_preview

    legacy_body = json.loads(first_content)["preview"]
    legacy_body["kind"] = "local-tactical-course-v1"
    legacy_body["policy"] = "provisional-recurring-tactics-v1"
    legacy_body["selection"]["pairs"] = legacy_body["selection"]["pairs"][:-1]
    legacy_body["selection"]["coverage"] = legacy_body["selection"]["coverage"][:-1]
    legacy = {
        "kind": legacy_body["kind"],
        "preview": legacy_body,
        "preview_sha256": preview_hash(legacy_body),
    }
    legacy_export = build_export(db, LEARNER, "test", legacy, Budget(db))
    previous = json.loads(first_content)["preview"]
    previous["kind"] = "local-tactical-course-v3"
    previous["policy"] = "provisional-recurring-tactics-v3"
    previous_preview = {
        "kind": previous["kind"],
        "preview": previous,
        "preview_sha256": preview_hash(previous),
    }
    previous_export = build_export(db, LEARNER, "test", previous_preview, Budget(db))
    assert study_preview(previous_export, previous_export["export_sha256"]) == previous_preview
    expected = {
        **exported["export"],
        "kind": "local-tactical-course-export-v1",
        "policy": "tactical-export-verification-v1",
        "preview_sha256": legacy["preview_sha256"],
        "selection": legacy_body["selection"],
    }
    assert legacy_export["export"] == expected
    assert legacy_export["export_sha256"] == preview_hash(expected)
    assert study_preview(legacy_export, legacy_export["export_sha256"]) == legacy
    invalid_legacy = json.loads(json.dumps(legacy))
    invalid_legacy["preview"]["selection"]["unavailable"][0]["reason"] = (
        "familiarity history exceeds the bounded scan"
    )
    invalid_legacy["preview_sha256"] = preview_hash(invalid_legacy["preview"])
    with pytest.raises(ValueError):
        build_export(db, LEARNER, "test", invalid_legacy, Budget(db))
    from chess_coach.tactical_study_current import revalidate as study_revalidate

    with study_revalidate(path, legacy_export, legacy_export["export_sha256"]) as check:
        check()
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
        project, related_preview_path, related_preview["preview_sha256"], related_output, offer=True
    )
    related_export = json.loads(related_output.read_bytes())
    assert related_export["export"]["chapters"] == related_preview["preview"]["chapters"]
    new_hash = related_export["export_sha256"]
    assert (
        course_client.get(
            course_url + "?version=" + exported["export_sha256"],
            base_url="https://coach.invalid",
            headers=course_headers,
        ).status_code
        == 409
    )
    second_chapter = course_client.get(
        course_url + "?version=" + new_hash + "&chapter=1",
        base_url="https://coach.invalid",
        headers=course_headers,
    )
    assert (
        second_chapter.status_code == 200 and b"Related unfamiliar example" in second_chapter.data
    )
    assert (
        b"View the source decision" in second_chapter.data
        and b"Show the supplied line" in second_chapter.data
    )
    # Revalidate the explicit export before opening any versioned intent or transport.
    import chess_coach.tactical_study_session as tactical_session

    calls = []

    def synthetic_publish(database, intent_path, course, *, action, check=None):
        calls.append((database, intent_path, course, action, check))
        return "synthetic destination"

    with monkeypatch.context() as patch:
        patch.setattr(tactical_session, "_publish", synthetic_publish)
        selected_hash = related_export["export_sha256"]
        planning.chmod(0o755)
        for action in (tactical_session.prepare_locked, tactical_session.publish_locked):
            with pytest.raises(ValueError, match="planning path unavailable"):
                action(project, related_output, selected_hash)
        assert not calls
        planning.chmod(0o700)
        assert (
            tactical_session.prepare_locked(project, related_output, selected_hash)
            == "synthetic destination"
        )
        assert calls[0][1].name == f"tactical-study-{selected_hash}-intent.json"
        assert calls[0][2]["course_sha256"] == selected_hash
        assert (
            tactical_session.publish_locked(project, related_output, selected_hash)
            == "synthetic destination"
        )
        assert calls[1][1] == calls[0][1] and calls[1][2] == calls[0][2]
        assert calls[1][3].keywords["strict"] is True
        assert calls[1][4] is calls[1][3].keywords["check"]
        with pytest.raises(ValueError):
            tactical_session.prepare_locked(project, related_output, "0" * 64)
        with pytest.raises(ValueError):
            tactical_session.publish_locked(project, related_output, "0" * 64)
        assert len(calls) == 2 and not calls[0][1].exists()
    legacy_path = planning / "legacy-export.json"
    legacy_path.write_text(json.dumps(legacy_export))
    legacy_path.chmod(0o600)
    legacy_calls = []

    def legacy_publish(database, intent_path, course, *, action, check=None):
        legacy_calls.append((intent_path, course, action, check))
        return "legacy destination"

    with monkeypatch.context() as patch:
        patch.setattr(tactical_session, "_publish", legacy_publish)
        assert (
            tactical_session.publish_locked(project, legacy_path, legacy_export["export_sha256"])
            == "legacy destination"
        )
    assert legacy_calls[0][0].name == f"tactical-study-{legacy_export['export_sha256']}-intent.json"
    assert legacy_calls[0][1] == {
        "course": expected,
        "course_sha256": legacy_export["export_sha256"],
    }
    assert legacy_calls[0][2].keywords["strict"] is True
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

    # A source change during inventory must stop the subsequent create.
    from chess_coach.study_remote import Remote
    from tests.test_private_study import Provider

    class ChangingProvider(Provider):
        def request(self, method, url, **kwargs):
            if str(url).endswith("/api/study/by/learner"):
                db.connection.execute("UPDATE games SET event=event WHERE id=1")
                db.connection.commit()
            return super().request(method, url, **kwargs)

    changing_provider = ChangingProvider()

    def changing_publish(_database, intent_path, course, *, action):
        remote = Remote("fixture-token", "learner", changing_provider)
        return action(remote, intent_path, course)

    with monkeypatch.context() as patch:
        patch.setattr(tactical_session, "_publish", changing_publish)
        with pytest.raises(PreviewUnavailable, match="changed"):
            tactical_session.prepare_locked(project, related_output, selected_hash)
    assert changing_provider.created == 0
    assert not json.loads(calls[0][1].read_text())["create_pending"]

    other_id = next(item["evidence_id"] for item in supports if item["evidence_id"] != selected_id)
    review_evidence(db, other_id, decision="accept", actor="fixture")
    with monkeypatch.context() as patch:
        patch.setattr(tactical_session, "_publish", synthetic_publish)
        with pytest.raises(ValueError):
            tactical_session.prepare_locked(project, related_output, selected_hash)
        assert len(calls) == 2 and not json.loads(calls[0][1].read_text())["create_pending"]
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

    from chess_coach.deep_selection_source import learner_key

    private_hash = "a" * 64
    private_receipt = planning / f"tactical-study-{private_hash}-intent.json"
    private_receipt.write_text(
        json.dumps(
            {
                "course_sha256": private_hash,
                "complete": True,
                "privacy_verified": True,
                "anonymous_verified": True,
                "ordered_verified": True,
                "learner_key": learner_key(LEARNER),
                "study": "abcd1234",
                "entry_chapter": "ch000000",
                "chapter_ids": ["ch000000"],
                "chapters": ["done"],
                "chapter_modes": ["conceal"],
                "verified_at": "2026-01-01T00:00:00+00:00",
            }
        )
    )
    private_receipt.chmod(0o600)
    app = create_app(
        project_root=project,
        db_path=path,
        subject=LEARNER,
        actor="fixture",
        corpus="test",
        login="login",
        origin="https://coach.invalid",
    )
    client = app.test_client()
    headers = {"Tailscale-User-Login": "login"}
    assert client.get("/coaching?full=1", base_url="https://coach.invalid").status_code == 403
    import chess_coach.coaching_quick_pair as quick_pair
    import chess_coach.coaching_quick_run as quick_run

    original_evidence = quick_pair.evidence
    calls = []

    def bounded_evidence(*args, **kwargs):
        calls.append(kwargs["limit"])
        return original_evidence(*args, **kwargs)

    read_only = Database(path)
    statements = []
    read_only.connection.set_trace_callback(
        lambda sql: statements.append(sql.split(None, 1)[0].upper())
    )
    with monkeypatch.context() as patch:
        patch.setattr("chess_coach.web_coaching.database", lambda: read_only)
        patch.setattr(quick_pair, "evidence", bounded_evidence)
        patch.setattr(
            "chess_coach.web_coaching.report",
            lambda *_args: (_ for _ in ()).throw(AssertionError("full report on quick GET")),
        )
        quick = client.get("/coaching", base_url="https://coach.invalid", headers=headers)
    read_only.close()
    assert not {"INSERT", "UPDATE", "DELETE", "REPLACE"} & set(statements)
    assert quick.status_code == 200
    assert calls and len(calls) <= 4 and set(calls) == {5}
    assert b"Quick preview:" in quick.data and b"<h3>Finding captures</h3>" in quick.data
    assert b"2 independent games" in quick.data and b"Source position before the move" in quick.data
    assert b"/evidence/" in quick.data and b"/decisions/" in quick.data
    assert b"Save this coaching preview" not in quick.data
    assert b"Open your tactical course" in quick.data and b"Daily plan" in quick.data
    from chess_coach.recurrence_skills import PAIRS

    for skill, operation in PAIRS:
        assert f"pattern={skill}.{operation}".encode() in quick.data
    focused = client.get(
        "/coaching?pattern=hanging_piece.execute", base_url="https://coach.invalid", headers=headers
    )
    assert focused.status_code == 200 and b"<h3>Finding captures</h3>" in focused.data
    assert b"19 other supported patterns" in focused.data
    assert (
        client.get(
            "/coaching?pattern=unsupported.execute",
            base_url="https://coach.invalid",
            headers=headers,
        ).status_code
        == 400
    )
    assert (
        client.get(
            "/coaching?full=1&pattern=hanging_piece.execute",
            base_url="https://coach.invalid",
            headers=headers,
        ).status_code
        == 400
    )

    original_build = quick_run.build

    def deferred(db, learner, pair, check):
        if pair == ("hanging_piece", "prevent"):
            from chess_coach.tactical_course_budget import PreviewUnavailable

            raise PreviewUnavailable("synthetic deadline")
        return original_build(db, learner, pair, check)

    with monkeypatch.context() as patch:
        patch.setattr(quick_run, "build", deferred)
        partial = client.get("/coaching", base_url="https://coach.invalid", headers=headers)
    assert b"<h3>Finding captures</h3>" in partial.data
    assert b"did not complete checking: Protecting pieces" in partial.data
    with monkeypatch.context() as patch:
        patch.setattr(quick_run, "PAIR_SECONDS", 0)
        timed_out = client.get("/coaching", base_url="https://coach.invalid", headers=headers)
    assert timed_out.status_code == 200 and b"did not complete checking" in timed_out.data
    assert b"Complete preview" in timed_out.data and b"Saved lesson history" in timed_out.data

    import chess_coach.coaching_failures_page as failures_page
    from chess_coach.tactical_course_budget import PreviewUnavailable

    def interrupted(*_args, **_kwargs):
        raise PreviewUnavailable("synthetic in-snapshot cutoff")

    reading = Database(path)
    with monkeypatch.context() as patch:
        patch.setattr("chess_coach.web_coaching.database", lambda: reading)
        patch.setattr(failures_page, "source", interrupted)
        interrupted_page = client.get(
            "/coaching?pattern=hanging_piece.execute",
            base_url="https://coach.invalid",
            headers=headers,
        )
    assert b"did not complete checking" in interrupted_page.data
    assert not reading.connection.in_transaction
    assert reading.connection.execute("PRAGMA query_only").fetchone()[0] == 0
    reading.close()

    changed = []

    def changing(db, learner, pair, check):
        result = original_build(db, learner, pair, check)
        if not changed:
            with sqlite3.connect(path) as other:
                other.execute("UPDATE games SET event=event WHERE id=1")
            changed.append(True)
        return result

    with monkeypatch.context() as patch:
        patch.setattr(quick_run, "build", changing)
        stale = client.get("/coaching", base_url="https://coach.invalid", headers=headers)
    assert b"The source changed or the quick checks were unavailable" in stale.data
    assert b"<h3>Finding captures</h3>" not in stale.data
    page = client.get("/coaching?full=1", base_url="https://coach.invalid", headers=headers)
    assert page.status_code == 200
    assert b"Open your tactical course" in page.data
    assert b"/study/abcd1234/ch000000#0" in page.data
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
    page = client.get("/coaching?full=1", base_url="https://coach.invalid", headers=headers)
    assert b"Only 0 of three" in page.data
    assert (
        b"Finding captures"
        in client.get(saved.location, base_url="https://coach.invalid", headers=headers).data
    )
    history = client.get("/lessons", base_url="https://coach.invalid", headers=headers)
    assert b"Coaching preview / recurring patterns" in history.data


def test_protection_lesson_offers_only_a_current_bounded_line_replay(tmp_path, monkeypatch):
    import sys
    from io import StringIO
    from pathlib import Path

    import pytest

    from chess_coach.db import Database
    from chess_coach.evidence_review import review_evidence
    from chess_coach.ingest import ingest_pgn
    from chess_coach.material_detector import process_decision as material_decision
    from chess_coach.pipeline_config import PipelineConfig
    from chess_coach.pipeline_inputs import engine_identity, game_input
    from chess_coach.pipeline_work import run_analysis
    from chess_coach.web import create_app
    from tests.test_material_pipeline import LEARNER, make_protection_game
    from tests.test_unified_sessions import token

    for color in ("white", "black"):
        with monkeypatch.context() as patch:
            patch.setattr("chess_coach.analysis_transaction.TemporaryFile", lambda **_: StringIO())
            created_db = make_protection_game(Path(":memory:"), patch, color=color, created=True)
            created_id = material_decision(created_db, 1, LEARNER)["evidence_ids"][0]
            if color == "white":
                from chess_coach.related_created import preview as created_preview
                from chess_coach.unified_session_events import hint, reveal, show, submit

                fen = "4k3/7p/8/2b5/8/3R4/1P6/7K b - - 0 1"

                def add_sample(db, *, fen=fen):
                    db.connection.execute(
                        "INSERT INTO puzzle_corpora(version,source,checksum,state) VALUES('test','fixture','checksum','staging')"
                    )
                    corpus = db.connection.execute("SELECT id FROM puzzle_corpora").fetchone()[0]
                    db.connection.execute(
                        """INSERT INTO puzzles(puzzle_id,corpus_id,fen,source,solution,rating,
                        rating_deviation,themes_json,objective) VALUES(
                        'sample',?,?,'https://example.invalid','h7h6 d3d5 e8f8 d5d6',
                        1200,80,'[]','unknown')""",
                        (corpus, fen),
                    )
                    db.connection.execute(
                        "INSERT INTO puzzle_themes VALUES(?,'sample','defensiveMove',1200)",
                        (corpus,),
                    )
                    db.connection.execute(
                        "UPDATE puzzle_corpora SET state='ready' WHERE id=?", (corpus,)
                    )
                    db.connection.commit()

                add_sample(created_db)
                # A separate in-memory encounter verifies a non-supplied safe move.
                from chess_coach.objective_created_judge import judge as created_judge
                from chess_coach.objective_worker import process as verify_objectives
                from chess_coach.related_capture_assessment import setup as assessment_setup

                assessed = make_protection_game(Path(":memory:"), patch, created=True)
                assessed_id = material_decision(assessed, 1, LEARNER)["evidence_ids"][0]
                add_sample(assessed)
                import time

                import chess

                assessment_board, _, _ = assessment_setup(assessed, "test", "sample")
                for root, expected in (
                    ("d3d2", "correct"),
                    ("d3d4", "incorrect"),
                    ("d3d8", "unresolved"),
                ):
                    checked = created_judge(
                        assessment_board,
                        assessment_board.parse_uci(root),
                        chess.D3,
                        time.monotonic,
                        time.monotonic(),
                        5,
                        {},
                    )
                    assert checked["status"] == expected
                for mate_fen, answer in (
                    ("4k3/7p/1P6/2b5/b7/3R4/1P3q2/7K b - - 0 1", "d3d5"),
                    ("4k3/7p/8/2b5/P4q2/3R4/rP6/7K b - - 0 1", "b2b3"),
                ):
                    mate_board = chess.Board(mate_fen)
                    mate_board.push_uci("h7h6")
                    mate_result = created_judge(
                        mate_board,
                        mate_board.parse_uci(answer),
                        chess.D3,
                        time.monotonic,
                        time.monotonic(),
                        5,
                        {},
                    )
                    assert (mate_result["status"], mate_result["reason"]) == (
                        "unresolved",
                        "opponent_immediate_mate",
                    )
                checking_board = chess.Board("4k3/8/7p/2b5/8/3R4/1P6/3n3K w - - 0 2")
                move = checking_board.parse_uci("d3d5")
                child = checking_board.copy()
                child.push(move)
                assert any(child.gives_check(reply) for reply in child.legal_moves)
                assert (
                    created_judge(
                        checking_board, move, chess.D3, time.monotonic, time.monotonic(), 5, {}
                    )["status"]
                    == "correct"
                )
                assessment_app = create_app(
                    db_path=":memory:",
                    subject=LEARNER,
                    actor="fixture",
                    corpus="test",
                    login="login",
                    origin="https://coach.invalid",
                )
                with patch.context() as assessment_patch:
                    assessment_patch.setattr(
                        "chess_coach.web_related_created.database", lambda db=assessed: db
                    )
                    assessment_patch.setattr(
                        "chess_coach.web_unified_practice.database", lambda db=assessed: db
                    )
                    assessment_patch.setattr(
                        "chess_coach.web_unified_actions.database", lambda db=assessed: db
                    )
                    assessment_client = assessment_app.test_client()
                    assessment_headers = {"Tailscale-User-Login": "login"}
                    assessment_preview = assessment_client.get(
                        f"/evidence/{assessed_id}/related-created-exposure",
                        base_url="https://coach.invalid",
                        headers=assessment_headers,
                    )
                    assert b"Check my first move" in assessment_preview.data
                    begun = assessment_client.post(
                        f"/evidence/{assessed_id}/related-created-exposure/start",
                        base_url="https://coach.invalid",
                        headers=assessment_headers | {"Origin": "https://coach.invalid"},
                        data={
                            "csrf": token(assessment_preview, "csrf"),
                            "reference": token(assessment_preview, "reference"),
                            "assessment": "1",
                        },
                    )
                    assert begun.status_code == 303
                    assessment_page = assessment_client.get(
                        begun.headers["Location"],
                        base_url="https://coach.invalid",
                        headers=assessment_headers,
                    )
                    assert b"rook on d3" in assessment_page.data
                    assert all(
                        text not in assessment_page.data for text in (b"Rd5", b"Rd4", b"Bxd4")
                    )
                    attempt = begun.headers["Location"].rsplit("/", 1)[-1]
                    answered = assessment_client.post(
                        "/unified/move",
                        base_url="https://coach.invalid",
                        headers=assessment_headers | {"Origin": "https://coach.invalid"},
                        data={
                            "csrf": token(assessment_page, "csrf"),
                            "attempt": attempt,
                            "event": token(assessment_page, "event"),
                            "move": "d3d2",
                        },
                    )
                    assert answered.status_code == 303
                    assert (
                        assessed.connection.execute(
                            "SELECT count(*) FROM objective_requests"
                        ).fetchone()[0]
                        == 1
                    )
                    assert verify_objectives(assessed, LEARNER)["outcomes"] == {"correct": 1}
                    import json

                    stored = assessed.connection.execute(
                        "SELECT result_json FROM objective_results"
                    ).fetchone()[0]
                    assert json.loads(stored)["learning_eligible"] is False
                    result_page = assessment_client.get(
                        answered.headers["Location"],
                        base_url="https://coach.invalid",
                        headers=assessment_headers,
                    )
                    assert b"Verified correct" in result_page.data
                    assert (
                        show(assessed, attempt, LEARNER)["verification"]["assistance"]
                        == "unassisted"
                    )
                assessed.close()

                found = created_preview(created_db, LEARNER, created_id, "test")
                assert len(found["items"]) == 1 and not found["created_scan"]["truncated"]
                assert "created_witness" not in found["items"][0]
                from chess_coach import related_created

                frozen = related_created.selection(created_db, LEARNER, created_id, "test")
                created_db.connection.execute(
                    """INSERT INTO puzzle_sessions(attempt_id,corpus_version,corpus_checksum,
                    puzzle_id,initial_fen,solution,current_fen,next_index,status,started_at)
                    VALUES('later-legacy','test','checksum','sample',?,?,
                    ?,0,'active','2020-01-01T00:00:00+00:00')""",
                    (fen, "h7h6 d3d5 e8f8 d5d6", fen),
                )
                created_db.connection.commit()
                with patch.context() as changed:
                    changed.setattr(
                        related_created, "selection", lambda *_args, frozen=frozen: frozen
                    )
                    with pytest.raises(ValueError):
                        related_created.start_related(
                            created_db,
                            attempt_id="blocked",
                            subject=LEARNER,
                            evidence_id=created_id,
                            corpus_version="test",
                            reference=found["items"][0]["reference"],
                        )
                assert (
                    created_db.connection.execute(
                        "SELECT 1 FROM unified_sessions WHERE attempt_id='blocked'"
                    ).fetchone()
                    is None
                )
                created_db.connection.execute(
                    "DELETE FROM puzzle_sessions WHERE attempt_id='later-legacy'"
                )
                created_db.connection.commit()
                preview_app = create_app(
                    db_path=":memory:",
                    subject=LEARNER,
                    actor="fixture",
                    corpus="test",
                    login="login",
                    origin="https://coach.invalid",
                )
                patch.setattr("chess_coach.web_related_created.database", lambda db=created_db: db)
                patch.setattr("chess_coach.web_unified_practice.database", lambda db=created_db: db)
                patch.setattr("chess_coach.web_unified_actions.database", lambda db=created_db: db)
                browser = preview_app.test_client()
                headers = {"Tailscale-User-Login": "login"}
                preview_page = browser.get(
                    f"/evidence/{created_id}/related-created-exposure",
                    base_url="https://coach.invalid",
                    headers=headers,
                )
                assert preview_page.status_code == 200 and b"You play white" in preview_page.data
                import sqlite3
                from unittest.mock import Mock

                busy = sqlite3.OperationalError("busy")
                busy.sqlite_errorcode = sqlite3.SQLITE_BUSY
                with patch.context() as locked:
                    locked.setattr(
                        "chess_coach.web_related_created.preview", Mock(side_effect=busy)
                    )
                    retry = browser.get(
                        f"/evidence/{created_id}/related-created-exposure",
                        base_url="https://coach.invalid",
                        headers=headers,
                    )
                    assert retry.status_code == 503 and b"try again" in retry.data
                assert all(text not in preview_page.data for text in (b"Rd5", b"Rd4", b"Bxd4"))
                started = browser.post(
                    f"/evidence/{created_id}/related-created-exposure/start",
                    base_url="https://coach.invalid",
                    headers=headers | {"Origin": "https://coach.invalid"},
                    data={
                        "csrf": token(preview_page, "csrf"),
                        "reference": token(preview_page, "reference"),
                    },
                )
                assert started.status_code == 303
                attempt = started.headers["Location"].rsplit("/", 1)[-1]
                practice_page = browser.get(
                    started.headers["Location"], base_url="https://coach.invalid", headers=headers
                )
                assert practice_page.status_code == 200
                assert all(
                    text not in practice_page.data
                    for text in (b"Rd5", b"Rd4", b"Bxd4", b"Reveal a line")
                )
                state = show(created_db, attempt, LEARNER)
                assert state["created_waiting"] and "created_contrast" not in state
                for action in (hint, reveal):
                    with pytest.raises(ValueError, match="answer before"):
                        action(created_db, attempt, LEARNER, event_id=action.__name__)
                illegal = submit(created_db, attempt, LEARNER, event_id="illegal", move="a1a1")
                assert illegal["feedback"] == "illegal" and "created_contrast" not in illegal
                answered = browser.post(
                    "/unified/move",
                    base_url="https://coach.invalid",
                    headers=headers | {"Origin": "https://coach.invalid"},
                    data={
                        "csrf": token(practice_page, "csrf"),
                        "attempt": attempt,
                        "event": token(practice_page, "event"),
                        "move": "d3d4",
                    },
                )
                assert answered.status_code == 303
                result = browser.get(
                    answered.headers["Location"], base_url="https://coach.invalid", headers=headers
                )
                assert result.status_code == 200 and b"ungraded" in result.data
                assert all(text in result.data for text in (b"Rd5", b"Rd4", b"Bxd4"))
                assert show(created_db, attempt, LEARNER)["created_contrast"] == {
                    "good": "Rd5",
                    "bad": "Rd4",
                    "capture": "Bxd4",
                }
            app = create_app(
                db_path=":memory:",
                subject=LEARNER,
                actor="fixture",
                corpus="test",
                login="login",
                origin="https://coach.invalid",
            )
            patch.setattr("chess_coach.web_views.database", lambda db=created_db: db)
            client = app.test_client()
            before = created_db.connection.total_changes
            page = client.get(
                f"/evidence/{created_id}",
                base_url="https://coach.invalid",
                headers={"Tailscale-User-Login": "login"},
            )
            assert page.status_code == 200 and created_db.connection.total_changes == before
            assert b"Exposure created by the played move" in page.data
            assert b"checked continuation" in page.data and b"checked alternative" in page.data
            with patch.context() as unknown:
                unknown.setattr(
                    "chess_coach.material_created_exposure_proof.history_known", lambda _: False
                )
                unavailable = client.get(
                    f"/evidence/{created_id}",
                    base_url="https://coach.invalid",
                    headers={"Tailscale-User-Login": "login"},
                )
                assert b"Exposure created by the played move" not in unavailable.data
            created_db.connection.execute(
                "UPDATE decision_analysis_lines SET score_value=score_value+1 WHERE position_id=1"
            )
            created_db.connection.commit()
            stale = client.get(
                f"/evidence/{created_id}",
                base_url="https://coach.invalid",
                headers={"Tailscale-User-Login": "login"},
            )
            assert b"Exposure created by the played move" not in stale.data
            created_db.connection.execute(
                "UPDATE decision_analysis_lines SET score_value=score_value-1 WHERE position_id=1"
            )
            created_db.connection.commit()
            review_evidence(created_db, created_id, decision="reject", actor="fixture")
            rejected = client.get(
                f"/evidence/{created_id}",
                base_url="https://coach.invalid",
                headers={"Tailscale-User-Login": "login"},
            )
            assert b"Exposure created by the played move" not in rejected.data
            created_db.close()

    path = tmp_path / "protection-coaching.sqlite"
    db = make_protection_game(path, monkeypatch)
    original_id = material_decision(db, 1, LEARNER)["evidence_ids"][0]
    from chess_coach.evidence_review import inspect_evidence
    from chess_coach.material_created_exposure import explain as created_exposure
    from chess_coach.protection_plan import report as protection_report

    assert created_exposure(db, inspect_evidence(db, original_id), LEARNER) is None

    single = protection_report(db, LEARNER)
    assert single["groups"] == 0 and single["source"] is None and single["checked"] == 0
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

    # Protection uses the same two bounded source slices, with the same chapter.
    import time

    import chess.engine

    from chess_coach import tactical_course_budget, tactical_course_resolve
    from chess_coach.coaching_report import report as coaching_report
    from chess_coach.tactical_course import build as tactical_preview
    from chess_coach.tactical_course_budget import Budget as CourseBudget
    from chess_coach.tactical_course_chapters import owned
    from chess_coach.tactical_export import build as tactical_export

    group = next(
        item
        for item in coaching_report(db, LEARNER)["groups"]
        if (item["lesson"]["skill"], item["lesson"]["operation"]) == ("hanging_piece", "prevent")
    )
    expected = owned(db, LEARNER, group)
    original_independent, original_owned = (
        tactical_course_resolve.independent,
        tactical_course_resolve.owned,
    )

    def delayed_independent(*args):
        time.sleep(0.6)
        return original_independent(*args)

    def delayed_owned(*args, **kwargs):
        time.sleep(0.6)
        return original_owned(*args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(tactical_course_budget, "SLICE_SECONDS", 1.0)
        patch.setattr(tactical_course_resolve, "independent", delayed_independent)
        patch.setattr(tactical_course_resolve, "owned", delayed_owned)
        assert tactical_course_resolve.own(db, LEARNER, group, CourseBudget(db)) == expected
    _reject_between_course_slices(db, path, LEARNER, group, monkeypatch)
    db.connection.execute(
        "INSERT INTO puzzle_corpora(version,source,checksum,state) VALUES('test','https://database.lichess.org/','fixture','staging')"
    )
    corpus_id = db.connection.execute(
        "SELECT id FROM puzzle_corpora WHERE version='test'"
    ).fetchone()[0]
    db.connection.execute(
        """INSERT INTO puzzles(puzzle_id,corpus_id,fen,source,solution,rating,rating_deviation,themes_json,objective)
        VALUES('protection-course-fixture',?,?,'https://example.invalid','h7h6 d4d5',1200,80,'[]','unknown')""",
        (corpus_id, "4k3/7p/8/2b5/3R4/8/1P6/7K b - - 0 1"),
    )
    db.connection.execute(
        "INSERT INTO puzzle_themes VALUES(?,'protection-course-fixture','defensiveMove',1200)",
        (corpus_id,),
    )
    db.connection.execute("UPDATE puzzle_corpora SET state='ready' WHERE id=?", (corpus_id,))
    db.connection.commit()
    before_course = db.connection.total_changes
    with monkeypatch.context() as patch:
        patch.setattr(
            chess.engine.SimpleEngine,
            "popen_uci",
            lambda *_: (_ for _ in ()).throw(AssertionError("engine")),
        )
        course = tactical_preview(db, LEARNER, "test")
        exported = tactical_export(db, LEARNER, "test", course, CourseBudget(db))
    assert next(p for p in course["preview"]["patterns"] if p["kind"] == "protection")
    assert expected[1] in course["preview"]["chapters"]
    assert exported["export"]["chapters"] == course["preview"]["chapters"]
    pattern = next(p for p in course["preview"]["patterns"] if p["kind"] == "protection")
    assert pattern["local_challenge"] == "/plan/protection/finder"
    related = next(ch for ch in course["preview"]["chapters"] if ch["source"]["type"] == "corpus")
    assert related["mode"] == "conceal" and "Worked example, ungraded" in related["pgn"]
    assert "profitable immediate capture" in related["pgn"] and "CC0" in related["pgn"]

    from copy import deepcopy

    from chess_coach.course_preview import preview_hash
    from chess_coach.tactical_study_preview import preview as study_preview

    legacy = deepcopy(course)
    legacy["kind"] = legacy["preview"]["kind"] = "local-tactical-course-v2"
    legacy["preview"]["policy"] = "provisional-recurring-tactics-v2"
    legacy["preview"]["selection"].pop("protection_per_band")
    legacy["preview"]["patterns"][0]["local_challenge"] = None
    legacy["preview"]["chapters"].remove(related)
    legacy["preview"]["selection"]["unavailable"].append(
        {"skill": "hanging_piece", "operation": "prevent", "reason": "related matching unsupported"}
    )
    legacy["preview_sha256"] = preview_hash(legacy["preview"])
    legacy_export = tactical_export(db, LEARNER, "test", legacy, CourseBudget(db))
    assert study_preview(legacy_export, legacy_export["export_sha256"]) == legacy

    with monkeypatch.context() as patch:
        from chess_coach import tactical_course_related

        original_selection = tactical_course_related.protection_selection

        def no_match(*args, **kwargs):
            selection = original_selection(*args, **kwargs)
            return (*selection[:3], [], *selection[4:])

        patch.setattr(tactical_course_related, "protection_selection", no_match)
        missing = tactical_preview(db, LEARNER, "test")
        assert missing["preview"]["selection"]["unavailable"][0]["reason"] == (
            "no compatible unfamiliar protection in the bounded scan"
        )
        assert tactical_export(db, LEARNER, "test", missing, CourseBudget(db))
    with monkeypatch.context() as patch:
        patch.setattr(
            "chess_coach.tactical_course_protection.current",
            lambda *_a, **_k: (_ for _ in ()).throw(ValueError("source changed")),
        )
        with pytest.raises(ValueError):
            tactical_export(db, LEARNER, "test", course, CourseBudget(db))
    assert db.connection.total_changes == before_course
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
    import chess_coach.protection_plan_select as protection_select
    import chess_coach.protection_plan_source as protection_source

    current_protection = protection_source.current
    checked = []

    def first_ineligible(db, evidence_id, subject, **kwargs):
        checked.append(evidence_id)
        if len(checked) == 1:
            raise ValueError("synthetic source is not replayable")
        return current_protection(db, evidence_id, subject, **kwargs)

    def forbidden(*_args, **_kwargs):
        raise AssertionError("unexpected source scan or engine work")

    with monkeypatch.context() as patch:
        patch.setattr("chess_coach.related_capture_familiar.familiarity", forbidden)
        patch.setattr("chess_coach.deep_execution_engine.start_engine", forbidden)
        daily = client.get("/plan", base_url="https://coach.invalid", headers=headers)
    assert b"Practice protecting a piece" in daily.data
    assert client.get("/plan/protection", base_url="https://coach.invalid").status_code == 403
    reading = Database(path)
    statements = []
    reading.connection.set_trace_callback(
        lambda sql: statements.append(sql.split(None, 1)[0].upper())
    )
    with monkeypatch.context() as patch:
        patch.setattr("chess_coach.web_protection_plan.database", lambda: reading)
        patch.setattr(protection_source, "current", first_ineligible)
        patch.setattr("chess_coach.related_capture_familiar.familiarity", forbidden)
        patch.setattr("chess_coach.deep_execution_engine.start_engine", forbidden)
        protection_page = client.get(
            "/plan/protection", base_url="https://coach.invalid", headers=headers
        )
    reading.close()
    assert not {"INSERT", "UPDATE", "DELETE", "REPLACE"} & set(statements)
    assert protection_page.status_code == 200 and len(checked) == 2
    assert b"2 independent candidate games" in protection_page.data
    assert b"1 checked source was unavailable or ineligible" in protection_page.data
    assert b"provisional candidate games" in protection_page.data
    assert b"The selected replay is checked separately" in protection_page.data
    assert b"identify the piece under threat" in protection_page.data
    assert b"You play white" in protection_page.data and b"d4d5" not in protection_page.data
    protection_key = token(protection_page, "key")
    assert int(protection_key.split(":")[-1]) == checked[1]
    assert f"/evidence/{checked[1]}".encode() in protection_page.data
    assert b"This replay keeps your schedule and mastery record separate" in protection_page.data
    with monkeypatch.context() as patch:
        patch.setattr("chess_coach.plan_capture_action.recommendation", lambda *_args: None)
        focus = client.get("/plan/next-focus", base_url="https://coach.invalid", headers=headers)
    assert focus.status_code == 200
    assert b"Next focus: protect a piece" in focus.data
    assert b"2 independent candidate games" in focus.data
    assert b"Replay the prepared defensive line" in focus.data

    class Budget:
        def check(self):
            pass

    with monkeypatch.context() as patch:
        patch.setattr(
            protection_select,
            "resolve",
            lambda *_args: (_ for _ in ()).throw(ValueError("unavailable")),
        )
        missing, count = protection_select.select(None, LEARNER, [[{} for _ in range(6)]], Budget())
    assert missing is None and count == 5
    replay = client.post(
        "/unified/start",
        data={
            "csrf": token(protection_page, "csrf"),
            "source_type": "own-game",
            "version": token(protection_page, "version"),
            "key": protection_key,
        },
        base_url="https://coach.invalid",
        headers=origin,
    )
    assert replay.status_code == 303
    replay_page = client.get(replay.location, base_url="https://coach.invalid", headers=headers)
    assert b"does not prove every defense" in replay_page.data

    page = client.get("/coaching?full=1", base_url="https://coach.invalid", headers=headers)
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
    page = client.get("/coaching?full=1", base_url="https://coach.invalid", headers=headers)
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
    page = client.get("/coaching?full=1", base_url="https://coach.invalid", headers=headers)
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
    page = client.get("/coaching?full=1", base_url="https://coach.invalid", headers=headers)
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
    page = client.get("/coaching?full=1", base_url="https://coach.invalid", headers=headers)
    assert token(page, "key") == key
    db = Database(path)
    review_evidence(db, int(key), decision="reject", actor="fixture")
    db.close()
    assert (
        client.get(started.location, base_url="https://coach.invalid", headers=headers).status_code
        == 410
    )
