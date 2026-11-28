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
    from tests.capture_certificate_fixture import certify
    from tests.capture_certificate_fixture import project as capture_project

    project, path = capture_project(tmp_path, "fork-coaching-project")
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
    from chess_coach.objective_fork_contract import MISS_VERSION as FORK_VERSION
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
        project_root=project,
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

    # Construct the released default through its real historical policy route.
    from chess_coach import tactical_course
    from chess_coach.tactical_course import build as tactical_preview
    from chess_coach.tactical_course_budget import Budget, PreviewUnavailable
    from chess_coach.tactical_export import build as tactical_export
    from chess_coach.tactical_study_current import revalidate
    from chess_coach.tactical_study_preview import preview as study_preview

    current_fork_course_policy = tactical_course._policy

    def released_default(selected):
        if selected is None:
            return (
                tactical_course.DEFAULT_ROLES_VERSION,
                tactical_course.DEFAULT_ROLES_POLICY,
                tactical_course.CURRENT_PAIRS,
                None,
            )
        return current_fork_course_policy(selected)

    monkeypatch.setattr(tactical_course, "_policy", released_default)
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
    # Distinct zeroing setups allow separate real deliveries without reusing a taught prompt.
    for key, fen, line, theme in (
        ("fixture-fork-h5", "r3k3/8/7p/1N6/8/8/6P1/7K b - - 0 1", "h6h5 b5c7 e8f8 c7a8", "fork"),
        ("fixture-fork-f6", "r3k3/5p2/8/1N6/8/8/6P1/7K b - - 0 1", "f7f6 b5c7 e8f8 c7a8", "fork"),
        ("fixture-capture", "4k3/p7/8/8/3q4/8/8/3RK3 b - - 0 1", "a7a6 d1d4", "hangingPiece"),
        ("fixture-protection", "4k3/7p/8/2b5/3R4/8/1P6/7K b - - 0 1", "h7h6 d4d5", "defensiveMove"),
    ):
        db.connection.execute(
            """INSERT INTO puzzles(puzzle_id,corpus_id,fen,source,solution,rating,rating_deviation,
            themes_json,objective) VALUES(?,?,?,?,?,?,?,?,'unknown')""",
            (key, corpus_id, fen, "https://example.invalid", line, 1200, 80, json.dumps([theme])),
        )
        db.connection.execute(
            "INSERT INTO puzzle_themes VALUES(?,?,?,1200)", (corpus_id, key, theme)
        )
    db.connection.execute("UPDATE puzzle_corpora SET state='ready' WHERE id=?", (corpus_id,))
    db.connection.commit()
    before_course = db.connection.total_changes
    course = tactical_preview(db, LEARNER, "test")
    assert course["kind"] == "local-tactical-course-v9"
    pattern = course["preview"]["patterns"][0]
    assert pattern["kind"] == "fork" and pattern["independent_games"] == 2
    assert pattern["local_challenge"].endswith("/related-forks/find-verified")
    own, related = course["preview"]["chapters"]
    assert missing_corpus["preview"]["chapters"][0] == own
    assert own["source"]["evidence_id"] in {evidence_id, second_id}
    assert own["mode"] == related["mode"] == "conceal"
    assert own["orientation"] == "white" and "attacks two valuable targets" in own["pgn"]
    # The owned chapter replays one actual certificate branch, not a new proof.
    import io

    import chess.pgn

    from chess_coach.tactical_course_display import chapter as display_chapter
    from chess_coach.tactical_course_presentation import VERSION as PRESENTATION_VERSION
    from chess_coach.tactical_exposure_positions import line_positions

    snapshot = own["source_snapshot"]
    proof = snapshot["provenance"]["fork_certificate"]
    line = own["presentation"]["lines"][0].split()
    assert own["presentation"]["version"] == PRESENTATION_VERSION
    assert len(snapshot["lines"]) == 1 and snapshot["lines"][0] == proof["move"]
    assert len(line) == 3 and line[0] == proof["move"]
    assert any(
        (branch["reply"], branch["capture"]) == tuple(line[1:]) for branch in proof["branches"]
    )
    played = chess.pgn.read_game(io.StringIO(own["pgn"]))
    assert played is not None and not played.errors
    assert [move.uci() for move in played.mainline_moves()] == line
    assert "White to move" in own["pgn"] and "Worked example, ungraded" in own["pgn"]
    assert "king on" in own["pgn"] and "rook on" in own["pgn"]
    assert "illustrative reply" in own["pgn"] and "not necessarily best or forced" in own["pgn"]
    assert "at least three material units" in own["pgn"]
    shown = display_chapter(own, 0, 0)
    assert len(shown["moves"]) == 3 and all(item["color"] == "white" for item in shown["moves"])
    assert len(line_positions(own, 0)) == 4
    import chess_coach.web_tactical_course as course_page

    with monkeypatch.context() as browser_view:
        offer = {"hash": course["preview_sha256"], "prepared_at": "fixture"}
        browser_view.setattr(course_page, "offered", lambda *_args: (offer, course["preview"]))
        browser_view.setattr(
            course_page,
            "status",
            lambda *_args: {"configured": False, "state": "none", "receipt": None},
        )
        browser_view.setattr(course_page, "preparation", lambda *_args: None)
        browser_view.setattr(course_page, "preparation_details", lambda: None)
        browser_view.setattr(course_page, "_record", lambda *_args, **_kwargs: None)
        shown_page = client.get("/coaching/tactical-course", base_url=base, headers=headers)
        assert shown_page.status_code == 200
        assert b"White to move" in shown_page.data and b"illustrative reply" in shown_page.data
        assert all(item["san"].encode() in shown_page.data for item in shown["moves"])
        download = client.get(
            "/coaching/tactical-course?download=1&version=" + offer["hash"],
            base_url=base,
            headers=headers,
        )
        assert download.status_code == 200 and own["pgn"].encode() in download.data
    assert db.connection.total_changes == before_course
    assert "Worked example, ungraded" in related["pgn"] and "CC0" in related["pgn"]
    exported = tactical_export(db, LEARNER, "test", course, Budget(db))
    assert exported["kind"] == "local-tactical-course-export-v9"
    assert study_preview(exported, exported["export_sha256"]) == course

    # Saved pre-illustration chapters still rebuild byte-for-byte.
    from chess_coach.course_preview import preview_hash
    from chess_coach.tactical_course_chapters import owned_chapter

    old = deepcopy(course)
    old_own = owned_chapter(db, LEARNER, group, own["source"], pattern["supporting_sources"])
    assert "presentation" not in old_own and old_own["source_snapshot"] == snapshot
    old["preview"]["chapters"][0] = old_own
    old["preview_sha256"] = preview_hash(old["preview"])
    old_export = tactical_export(db, LEARNER, "test", old, Budget(db))
    assert old_export["export"]["chapters"][0]["pgn"] == old_own["pgn"]
    assert study_preview(old_export, old_export["export_sha256"]) == old

    # Previously saved v1 worked chapters still rebuild exactly after v2 becomes the default.
    from chess_coach.objective_fork_contract import VERSION as LEGACY_FORK_VERSION

    with monkeypatch.context() as patch:
        patch.setattr("chess_coach.coaching_practice_identity.FORK_VERSION", LEGACY_FORK_VERSION)
        legacy_course = tactical_preview(db, LEARNER, "test")
    assert legacy_course["preview"]["chapters"][0]["source"]["version"] == LEGACY_FORK_VERSION
    legacy_export = tactical_export(db, LEARNER, "test", legacy_course, Budget(db))
    assert study_preview(legacy_export, legacy_export["export_sha256"]) == legacy_course

    # The selected fork exercise is certified by the real worker; later reads
    # must rebind its separately retained proof without running the solver.
    from chess_coach.opening_queue_location import scope
    from chess_coach.ops_tactical_export import prepare as export_candidate
    from chess_coach.tactical_course_choice import SLICE_SECONDS as SELECTED_SECONDS
    from chess_coach.tactical_course_offer_read import offered
    from chess_coach.tactical_course_request import enqueue
    from chess_coach.tactical_course_worker import run as prepare_course

    db.capture_root = scope(db, project, db.capture_root)
    monkeypatch.setenv("CHESS_DB", str(path))
    monkeypatch.setenv("CHESS_SUBJECT", LEARNER)
    monkeypatch.setenv("CHESS_CORPUS", "test")

    def learning_rows():
        tables = (
            "unified_sessions",
            "unified_session_events",
            "objective_requests",
            "objective_results",
            "unified_training_enrollments",
            "unified_training_completions",
            "training_items",
            "training_attempts",
            "mastery_states",
            "mastery_events",
            "evidence_mappings",
            "evidence_review_events",
        )
        with sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True) as reader:
            reader.execute("PRAGMA query_only=ON")
            return tuple(
                (table, reader.execute(f"SELECT * FROM {table} ORDER BY rowid").fetchall())
                for table in tables
            )

    import httpx

    import chess_coach.tactical_study_session as tactical_session
    from chess_coach.study_pgn_verify import matches
    from chess_coach.study_remote import Remote
    from tests.test_private_study import Provider

    class ForkProvider(Provider):
        def request(self, method, url, **kwargs):
            if httpx.URL(url).path == "/api/account":
                request = httpx.Request(method, url)
                return httpx.Response(
                    200, json={"id": LEARNER, "username": LEARNER}, request=request
                )
            url = str(url).replace(f"/api/study/by/{LEARNER}", "/api/study/by/learner")
            return super().request(method, url, **kwargs)

    def local_provider(_database, intent, course, *, action, check=None):
        return action(remote, intent, course)

    # The real default worker and CLI use their existing two-second slices.
    from chess_coach.ops_tactical_course import prepare as prepare_default_cli

    with monkeypatch.context() as default_policy:
        default_policy.setattr(tactical_course, "_policy", current_fork_course_policy)
        enqueue(db, project, LEARNER, "test")
        prepare_course(db, LEARNER, project)
        default_offer, default_body = offered(project, path, LEARNER, "test")
        assert default_body["kind"] == "local-tactical-course-export-v15"
        assert [part["role"] for part in default_body["chapters"]] == [
            "explanation",
            "worked",
            "practice",
        ]
        assert default_body["selection"]["related_match_seconds"] == 2.0
        assert "work_policy" not in default_body["selection"]
        default_explanation = default_body["chapters"][0]
        default_review = default_explanation["source_snapshot"]["provenance"]["review_status"]
        assert f"This source review is {default_review}" in default_explanation["pgn"]
        assert "king on" in default_explanation["pgn"] and "rook on" in default_explanation["pgn"]
        default_practice = default_body["chapters"][2]
        assert default_practice["source"]["binding"]["assessment"]["proof"]["minimum_gain"] == 3
        default_export = json.loads(
            (project / ".runtime" / "planning" / default_offer["file"]).read_text()
        )
        default_preview_path = project / ".runtime" / "planning" / "default-fork-preview.json"
        prepare_default_cli(project, default_preview_path)
        default_preview = json.loads(default_preview_path.read_text())
        assert default_preview["kind"] == "local-tactical-course-v15"
        default_cli = project / ".runtime" / "planning" / "default-fork-cli.json"
        before_default_reads = learning_rows()
        with monkeypatch.context() as guarded_default:

            def forbidden_default(*_args, **_kwargs):
                pytest.fail("fork proof ran during a prepared default-course read")

            guarded_default.setattr(
                "chess_coach.related_fork_assessment.fork_proof", forbidden_default
            )
            guarded_default.setattr("chess_coach.fork_observation.fork_proof", forbidden_default)
            guarded_default.setattr(
                "chess_coach.objective_fork_judge.fork_proof", forbidden_default
            )
            export_candidate(
                project, default_preview_path, default_preview["preview_sha256"], default_cli
            )
            assert json.loads(default_cli.read_text()) == default_export
            with revalidate(
                path, default_export, default_offer["hash"], project_root=project
            ) as check:
                check()
            page = client.get("/coaching/tactical-course?chapter=2", base_url=base, headers=headers)
            assert page.status_code == 200 and b"Practice a related knight fork" in page.data
            download = client.get(
                "/coaching/tactical-course?download=1&version=" + default_offer["hash"],
                base_url=base,
                headers=headers,
            )
            assert download.status_code == 200 and default_practice["pgn"].encode() in download.data
            default_provider = ForkProvider()
            default_provider.owner = LEARNER
            default_provider.timeout_create = default_provider.timeout_upload = False
            remote = Remote("fixture-token", LEARNER, default_provider)
            guarded_default.setattr(
                "chess_coach.study_anonymous.request", default_provider.anonymous
            )
            guarded_default.setattr(tactical_session, "_publish", local_provider)
            tactical_session.prepare_locked(project, default_cli, default_offer["hash"])
            tactical_session.publish_locked(project, default_cli, default_offer["hash"])
            assert [part["mode"] for part in default_provider.uploaded] == ["conceal"] * 3
            assert matches(
                {**default_practice, "name": default_provider.uploaded[2]["name"]},
                default_provider.export(),
            )
        assert learning_rows() == before_default_reads

    enqueue(db, project, LEARNER, "test", selected=["fork:execute"])
    prepare_course(db, LEARNER, project)
    fork_offer, fork_body = offered(project, path, LEARNER, "test")
    assert fork_body["kind"] == "local-tactical-course-export-v12"
    fork_chapters = fork_body["chapters"]
    assert [item["role"] for item in fork_chapters] == ["explanation", "worked", "practice"]
    explain, worked, exercise = fork_chapters
    assert explain["source"] == worked["source"]
    assert explain["source"]["type"] == "own-game" and exercise["source"]["type"] == "corpus"
    assert exercise["source"]["key"] != default_practice["source"]["key"]
    review = explain["source_snapshot"]["provenance"]["review_status"]
    assert f"This source review is {review}" in explain["pgn"]
    assert "Provisional recurring observation" in explain["pgn"]
    assert "independently reviewed" not in explain["pgn"]
    assert (
        "knight on" in explain["pgn"]
        and "king on" in explain["pgn"]
        and "rook on" in explain["pgn"]
    )
    assert "at least three material units" in explain["pgn"]
    assert exercise["mode"] == "conceal" and "ungraded" in exercise["pgn"]
    assert "may choose a different exercise" in exercise["pgn"]
    assert exercise["source"]["binding"]["assessment"]["proof"]["minimum_gain"] == 3
    assert exercise["source"]["binding"]["assessment"]["context"]["rating_band"] == 6
    fork_export = json.loads((project / ".runtime" / "planning" / fork_offer["file"]).read_text())
    fork_preview = study_preview(fork_export, fork_offer["hash"])
    # Build the released v11 layout through its actual historical policy route.
    from chess_coach import tactical_course

    with monkeypatch.context() as old_policy:
        old_policy.setattr(
            tactical_course,
            "_policy",
            lambda _selected: (
                tactical_course.SELECTED_FORK_VERSION,
                tactical_course.SELECTED_FORK_POLICY,
                [("fork", "execute")],
                SELECTED_SECONDS,
            ),
        )
        old_fork = tactical_preview(
            db,
            LEARNER,
            "test",
            selected=["fork:execute"],
            budget=Budget(db, slice_seconds=SELECTED_SECONDS),
        )
    assert old_fork["kind"] == "local-tactical-course-v11"
    assert len(old_fork["preview"]["chapters"]) == 2
    preview_path = project / ".runtime" / "planning" / "selected-fork-preview.json"
    preview_path.write_text(json.dumps(fork_preview))
    preview_path.chmod(0o600)
    cli_path = project / ".runtime" / "planning" / "selected-fork-cli.json"

    learning_before = learning_rows()
    with monkeypatch.context() as no_proof:

        def forbidden(*_args, **_kwargs):
            pytest.fail("fork proof ran during a prepared course read")

        no_proof.setattr("chess_coach.related_fork_assessment.fork_proof", forbidden)
        no_proof.setattr("chess_coach.fork_observation.fork_proof", forbidden)
        no_proof.setattr("chess_coach.objective_fork_judge.fork_proof", forbidden)
        export_candidate(project, preview_path, fork_preview["preview_sha256"], cli_path)
        assert json.loads(cli_path.read_text()) == fork_export
        with revalidate(path, fork_export, fork_offer["hash"], project_root=project) as check:
            check()
        # Rebuild the actual released v11 layout without repeating its proof.
        old_fork_export = tactical_export(
            db, LEARNER, "test", old_fork, Budget(db, slice_seconds=SELECTED_SECONDS)
        )
        assert study_preview(old_fork_export, old_fork_export["export_sha256"]) == old_fork
        missing_fork = tactical_preview(
            db,
            LEARNER,
            "not-configured",
            selected=["fork:execute"],
            budget=Budget(db, slice_seconds=SELECTED_SECONDS),
        )
        assert [part["role"] for part in missing_fork["preview"]["chapters"]] == [
            "explanation",
            "worked",
        ]
        assert (
            missing_fork["preview"]["selection"]["unavailable"][0]["reason"]
            == "fork corpus unavailable"
        )
        from chess_coach.tactical_course_fork_provenance import retain as retain_fork_proof

        planning = project / ".runtime" / "planning"
        before_records = set(planning.glob("tactical-fork-proof-*.json"))
        retain_fork_proof(
            db, project, LEARNER, missing_fork, Budget(db, slice_seconds=SELECTED_SECONDS)
        )
        assert set(planning.glob("tactical-fork-proof-*.json")) == before_records
        missing_fork_export = tactical_export(
            db, LEARNER, "not-configured", missing_fork, Budget(db, slice_seconds=SELECTED_SECONDS)
        )
        assert (
            study_preview(missing_fork_export, missing_fork_export["export_sha256"]) == missing_fork
        )
        changed_proof = deepcopy(fork_preview)
        changed_chapter = changed_proof["preview"]["chapters"][2]
        changed_chapter["source"]["binding"]["assessment"]["proof"]["branches"][0]["reply"] = "a1a1"
        changed_proof["preview_sha256"] = preview_hash(changed_proof["preview"])
        from chess_coach.tactical_course_fork_provenance import require as require_fork_proof

        with pytest.raises(ValueError, match="fork assessment preparation"):
            require_fork_proof(db, LEARNER, changed_chapter)
        with pytest.raises((ValueError, PreviewUnavailable)):
            tactical_export(
                db, LEARNER, "test", changed_proof, Budget(db, slice_seconds=SELECTED_SECONDS)
            )
        page = client.get("/coaching/tactical-course?chapter=2", base_url=base, headers=headers)
        assert page.status_code == 200 and b"Practice a related knight fork" in page.data
        download = client.get(
            "/coaching/tactical-course?download=1&version=" + fork_offer["hash"],
            base_url=base,
            headers=headers,
        )
        assert download.status_code == 200 and exercise["pgn"].encode() in download.data

        provider = ForkProvider()
        no_proof.setattr("chess_coach.study_anonymous.request", provider.anonymous)
        provider.owner = LEARNER
        provider.timeout_create = provider.timeout_upload = False
        remote = Remote("fixture-token", LEARNER, provider)

        no_proof.setattr(tactical_session, "_publish", local_provider)
        tactical_session.prepare_locked(project, cli_path, fork_offer["hash"])
        tactical_session.publish_locked(project, cli_path, fork_offer["hash"])
        assert [item["mode"] for item in provider.uploaded] == ["conceal", "conceal", "conceal"]
        assert matches({**exercise, "name": provider.uploaded[2]["name"]}, provider.export())
    assert learning_rows() == learning_before

    with revalidate(path, exported, exported["export_sha256"]) as check:
        check()
    with revalidate(path, legacy_export, legacy_export["export_sha256"]) as check:
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
    for suffix, fen, line in (
        ("h5", "r3k3/8/7p/1N6/8/8/6P1/7K b - - 0 1", "h6h5 b5c7 e8f8 c7a8"),
        ("f6", "r3k3/5p2/8/1N6/8/8/6P1/7K b - - 0 1", "f7f6 b5c7 e8f8 c7a8"),
    ):
        db.connection.execute(
            """INSERT INTO puzzle_sessions(attempt_id,corpus_version,corpus_checksum,puzzle_id,
            initial_fen,solution,current_fen,next_index,status,hints_used,started_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
            (
                f"familiar-fork-{suffix}",
                "test",
                "fixture-checksum",
                f"fixture-fork-{suffix}",
                fen,
                line,
                fen,
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
    with pytest.raises((ValueError, PreviewUnavailable)):
        tactical_export(
            db,
            LEARNER,
            "test",
            fork_preview,
            Budget(db, slice_seconds=SELECTED_SECONDS),
            artifact=fork_offer["hash"],
        )
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
    db.connection.execute(
        "DELETE FROM puzzle_sessions WHERE attempt_id IN ('familiar-fork','familiar-fork-h5','familiar-fork-f6')"
    )
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

    def add_capture_source(day):
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
        with monkeypatch.context() as engine:
            engine.setattr(chess.engine.SimpleEngine, "popen_uci", lambda *_: MaterialEngine())
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

    for day in (3, 4):
        add_capture_source(day)
    certify(db, LEARNER, project)
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
            tactical_course, "candidates", lambda *_a, **_k: ([fork_group, capture_group], coverage)
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
        ops_tactical_course.prepare(project, output)
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
            patch.setattr(
                tactical_course, "candidates", lambda *_a, order=order, **_k: (order, coverage)
            )
            mixed = tactical_preview(db, LEARNER, "test")
            assert [p["kind"] for p in mixed["preview"]["patterns"]] == (
                ["capture", "fork"] if index == 0 else ["fork", "capture"]
            )
            chapters = mixed["preview"]["chapters"]
            assert len(chapters) == 3
            if index == 0:
                explanation, worked, fork = chapters
            else:
                fork, explanation, worked = chapters
            assert [explanation["role"], worked["role"]] == ["explanation", "worked"]
            assert explanation["source"] == worked["source"]
            assert explanation["source_snapshot"] == worked["source_snapshot"]
            assert explanation["source"]["kind"] == "capture" and fork["source"]["kind"] == "fork"
            assert explanation["source"]["evidence_id"] in {
                item["evidence_id"] for item in capture_group["lesson"]["examples"]
            }
            assert fork["source"]["evidence_id"] in {
                item["evidence_id"] for item in fork_group["lesson"]["examples"]
            }
            assert all(c["source"]["type"] == "own-game" for c in chapters)
            assert all(c["orientation"] == "white" and c["mode"] == "conceal" for c in chapters)
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

    # Real source counts, rather than a substituted ranking, exercise both mixed orders.
    from tests.capture_certificate_fixture import prepare_corpus

    capture_position = capture_group["lesson"]["examples"][0]["position_id"]
    prepare_corpus(db, LEARNER, project, "test", capture_position)

    def mixed_offer():
        with monkeypatch.context() as guard:
            guard.setattr("chess_coach.related_fork_assessment.fork_proof", forbidden_default)
            guard.setattr("chess_coach.fork_observation.fork_proof", forbidden_default)
            guard.setattr("chess_coach.objective_fork_judge.fork_proof", forbidden_default)
            return offered(project, path, LEARNER, "test")

    with monkeypatch.context() as actual_default:
        actual_default.setattr(tactical_course, "_policy", current_fork_course_policy)
        enqueue(db, project, LEARNER, "test")
        prepare_course(db, LEARNER, project)
        first_offer, first_mixed = mixed_offer()
        first_skills = [part["skill"] for part in first_mixed["patterns"]]
        assert first_skills.index("fork") < first_skills.index("hanging_piece")
        first_practice = next(
            part
            for part in first_mixed["chapters"]
            if part["source"].get("binding", {}).get("motif") == "fork"
        )
        assert first_practice["source"]["binding"]["assessment"]["proof"]["minimum_gain"] == 3
        assert first_mixed["chapters"][-1]["source"]["binding"]["motif"] == "material_capture"
        require_fork_proof(db, LEARNER, first_practice)
        add_capture_source(5)
        certify(db, LEARNER, project)
        prepare_corpus(db, LEARNER, project, "test", capture_position)
        enqueue(db, project, LEARNER, "test")
        prepare_course(db, LEARNER, project)
        second_offer, second_mixed = mixed_offer()
        second_skills = [part["skill"] for part in second_mixed["patterns"]]
        assert second_skills.index("hanging_piece") < second_skills.index("fork")
        second_practice = next(
            part
            for part in second_mixed["chapters"]
            if part["source"].get("binding", {}).get("motif") == "fork"
        )
        require_fork_proof(db, LEARNER, second_practice)
        assert first_offer["hash"] != second_offer["hash"]

        class ProtectionEngine(MaterialEngine):
            def __init__(self):
                super().__init__(best="d4d5", reply="e8f8")

            def analyse(self, board, limit, multipv, root_moves=None):
                lines = super().analyse(board, limit, multipv, root_moves=root_moves)
                if not board.move_stack and root_moves and root_moves[0].uci() == "a2a3":
                    lines[0]["pv"][1] = chess.Move.from_uci("c5d4")
                return lines

        for day in (6, 7):
            board = chess.Board("4k3/8/8/2b5/3R4/8/P7/7K w - - 0 1")
            game = chess.pgn.Game()
            game.setup(board)
            game.headers.update(
                White=LEARNER,
                Black="fixture_opponent",
                Result="*",
                UTCDate=f"2026.01.0{day}",
                UTCTime="12:00:00",
            )
            node = game.add_variation(board.parse_uci("a2a3"))
            node.add_variation(chess.Move.from_uci("c5d4"))
            ingest_pgn(db, str(game))
            game_id = db.connection.execute("SELECT MAX(id) FROM games").fetchone()[0]
            position_id = db.connection.execute(
                "SELECT id FROM positions WHERE game_id=? AND ply=1", (game_id,)
            ).fetchone()[0]
            with monkeypatch.context() as engine:
                engine.setattr(
                    chess.engine.SimpleEngine, "popen_uci", lambda *_: ProtectionEngine()
                )
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

        enqueue(db, project, LEARNER, "test")
        prepare_course(db, LEARNER, project)
        before_mixed_reads = learning_rows()
        with monkeypatch.context() as guarded:
            guarded.setattr("chess_coach.related_fork_assessment.fork_proof", forbidden_default)
            guarded.setattr("chess_coach.fork_observation.fork_proof", forbidden_default)
            guarded.setattr("chess_coach.objective_fork_judge.fork_proof", forbidden_default)
            guarded.setattr("chess_coach.tactical_course_protection.probe", forbidden_default)
            guarded.setattr("chess_coach.objective_protection_snapshot.probe", forbidden_default)
            guarded.setattr("chess_coach.objective_protection_snapshot.judge", forbidden_default)
            guarded.setattr("chess_coach.related_protection_features.probe", forbidden_default)
            guarded.setattr("chess_coach.related_protection_features.judge", forbidden_default)
            mixed_identity, mixed = mixed_offer()
            protection_index = next(
                i
                for i, item in enumerate(mixed["chapters"])
                if item.get("role") == "explanation" and item["source"]["kind"] == "protection"
            )
            page = client.get(
                f"/coaching/tactical-course?version={mixed_identity['hash']}&chapter={protection_index}",
                base_url=base,
                headers=headers,
            )
            assert page.status_code == 200 and b"Understand the threatened piece" in page.data
            download = client.get(
                f"/coaching/tactical-course?version={mixed_identity['hash']}&download=1",
                base_url=base,
                headers=headers,
            )
            assert download.status_code == 200 and b"Practice a defense" in download.data
        assert learning_rows() == before_mixed_reads
        assert mixed["kind"] == "local-tactical-course-export-v15"
        assert {part["kind"] for part in mixed["patterns"]} >= {"capture", "fork", "protection"}
        assert [
            item["role"] for item in mixed["chapters"][protection_index : protection_index + 3]
        ] == ["explanation", "worked", "practice"]
        protection = mixed["chapters"][protection_index : protection_index + 3]
        assert protection[1]["source"]["version"] == "protect-threatened-piece-own-v1"
        assert "Ungraded rehearsal" in protection[2]["pgn"]
        mixed_fork = next(
            item
            for item in mixed["chapters"]
            if item["source"].get("binding", {}).get("motif") == "fork"
        )
        require_fork_proof(db, LEARNER, mixed_fork)
        mixed_envelope = json.loads((planning / mixed_identity["file"]).read_text())
        mixed_preview = study_preview(mixed_envelope, mixed_identity["hash"])
        protection_pattern = next(
            item for item in mixed["patterns"] if item["kind"] == "protection"
        )
        protection_evidence = protection_pattern["supporting_sources"][0]["evidence_id"]
        changed_budget = Budget(db)
        db.connection.execute("SAVEPOINT mixed_protection_review")
        try:
            review_evidence(db, protection_evidence, decision="reject", actor="fixture")
            with pytest.raises((ValueError, PreviewUnavailable)):
                tactical_export(
                    db,
                    LEARNER,
                    "test",
                    mixed_preview,
                    changed_budget,
                    artifact=mixed_identity["hash"],
                )
        finally:
            db.connection.execute("ROLLBACK TO SAVEPOINT mixed_protection_review")
            db.connection.execute("RELEASE SAVEPOINT mixed_protection_review")

    second_example = next(item for item in lesson["examples"] if item["evidence_id"] == second_id)
    review_evidence(db, second_id, decision="reject", actor="fixture")
    with pytest.raises(ValueError):
        offered(project, path, LEARNER, "test")
    assert resolve_example(db, LEARNER, lesson, second_example) is None
    with pytest.raises(ValueError):
        tactical_export(db, LEARNER, "test", course, Budget(db))
    with (
        pytest.raises(ValueError),
        revalidate(path, fork_export, fork_offer["hash"], project_root=project),
    ):
        pass
    with (
        pytest.raises(ValueError),
        revalidate(path, default_export, default_offer["hash"], project_root=project),
    ):
        pass

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
    from chess_coach.db import Database
    from chess_coach.evidence_review import review_evidence
    from chess_coach.ingest import ingest_pgn
    from chess_coach.lesson_history import get
    from chess_coach.lesson_narrative import build
    from chess_coach.pipeline_inputs import engine_identity, game_input
    from chess_coach.pipeline_work import run_analysis
    from chess_coach.recurrence_report import report
    from chess_coach.web import create_app
    from chess_coach.web_db import database

    path = tmp_path / "synthetic.sqlite"
    db, config = make_game(path, monkeypatch)
    first_id = process_decision(db, 1, LEARNER)["evidence_ids"][0]
    review_evidence(db, first_id, decision="accept", actor="fixture")
    pgn = db.connection.execute("SELECT pgn FROM games WHERE id=1").fetchone()[0]
    ingest_pgn(db, pgn.replace("2026.01.01", "2026.01.02"))
    second_position = db.connection.execute(
        "SELECT id FROM positions WHERE game_id=2 AND ply=1"
    ).fetchone()[0]
    assert (
        run_analysis(db, 2, game_input(db, 2), config, engine_identity(config.engine_path))[
            "status"
        ]
        == "complete"
    )
    second_id = process_decision(db, second_position, LEARNER)["evidence_ids"][0]
    review_evidence(db, second_id, decision="accept", actor="fixture")
    dates = {
        "start": "2026-01-01T00:00:00+00:00",
        "end": "2026-01-03T00:00:00+00:00",
        "compare_start": "2025-12-01T00:00:00+00:00",
    }
    data = report(db, LEARNER, **dates, skill="fork", operation="execute")
    group = next(item for item in data["current"] if item["family"] == "fork-opportunity-mapper")
    canonical = build(db, LEARNER, group)
    assert len(canonical["examples"]) == 2
    assert {item["evidence_id"] for item in canonical["examples"]} == {first_id, second_id}
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
    report_page = client.get(
        "/recurrence", query_string=dates, base_url="https://coach.invalid", headers=headers
    )
    assert b"not repeated mistakes" in report_page.data
    view = client.get("/decisions/1", base_url="https://coach.invalid", headers=headers)
    assert view.status_code == 200
    assert b"Diagnostic question" in view.data and b"Nc7+" in view.data
    with client.session_transaction(base_url="https://coach.invalid") as session:
        csrf = session["csrf"]
    form = {
        "csrf": csrf,
        **dates,
        "filter_skill": "fork",
        "filter_operation": "execute",
        "period": "current",
        **{key: group[key] for key in ("skill", "operation", "family", "version")},
    }
    headers["Origin"] = "https://coach.invalid"
    first = client.post(
        "/lessons/regenerate", data=form, base_url="https://coach.invalid", headers=headers
    )

    def reorder(payload):
        assert not database().connection.in_transaction
        payload["facts"]["lesson"]["examples"][0]["facts"].append("unsupported invented claim")
        return '{"order":[1,0]}'

    app.extensions["lesson_generator"] = (reorder, "fixture-model")
    second = client.post(
        "/lessons/regenerate", data=form, base_url="https://coach.invalid", headers=headers
    )
    assert first.status_code == second.status_code == 303
    assert first.location != second.location
    page = client.get(first.location, base_url="https://coach.invalid", headers=headers)
    assert b"historical snapshot" in page.data and b"Nc7+" in page.data
    app.extensions["lesson_generator"] = (
        lambda _facts: '{"order":[1,0],"claim":"unsupported"}',
        "fixture-model",
    )
    malformed = client.post(
        "/lessons/regenerate", data=form, base_url="https://coach.invalid", headers=headers
    )

    def unavailable(_facts):
        raise RuntimeError("private generator error")

    app.extensions["lesson_generator"] = (unavailable, "fixture-model")
    fallback = client.post(
        "/lessons/regenerate", data=form, base_url="https://coach.invalid", headers=headers
    )
    assert malformed.status_code == fallback.status_code == 303
    assert b"private generator error" not in fallback.data

    def changed(_facts):
        writer = Database(path)
        try:
            review_evidence(writer, second_id, decision="reject", actor="fixture")
        finally:
            writer.close()
        return '{"order":[1,0]}'

    app.extensions["lesson_generator"] = (changed, "fixture-model")
    stale = client.post(
        "/lessons/regenerate", data=form, base_url="https://coach.invalid", headers=headers
    )
    assert stale.status_code == 400 and b"lesson source changed" not in stale.data
    history = client.get("/lessons", base_url="https://coach.invalid", headers=headers)
    assert history.status_code == 200 and history.data.count(b"fork / execute") == 4
    check = Database(path)
    records = [
        get(check, LEARNER, int(response.location.rsplit("/", 1)[1]))
        for response in (first, second, malformed, fallback)
    ]
    assert records[0]["lesson"] == canonical
    assert records[0]["inputs"]["generation"]["status"] == "not_requested"
    assert records[1]["lesson"]["examples"] == list(reversed(canonical["examples"]))
    assert records[1]["generator_model"] == "fixture-model"
    assert records[1]["prompt_version"] == "lesson-order-v1"
    assert records[1]["inputs"]["generation"]["input"]["lesson"] == canonical
    for record in records[2:]:
        assert record["lesson"] == canonical and record["generator_model"] == "deterministic"
        assert record["inputs"]["generation"]["status"] == "fallback"
        assert record["inputs"]["generation"]["attempted_model"] == "fixture-model"
    assert check.connection.execute("SELECT COUNT(*) FROM lesson_versions").fetchone()[0] == 4
    assert (
        check.connection.execute("SELECT COUNT(*) FROM evidence_review_events").fetchone()[0] == 3
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


def _default_course_readiness_workflow(
    db, learner, project, path, client, headers, csrf, offer_slot, request_file, monkeypatch
):
    import json
    import sqlite3

    import pytest

    from chess_coach import tactical_course, tactical_course_patterns, tactical_course_worker
    from chess_coach.tactical_course_budget import Budget, PreviewUnavailable
    from chess_coach.tactical_course_choice import SLICE_SECONDS
    from chess_coach.tactical_course_selection import CURRENT_PAIRS
    from chess_coach.tactical_export import build as build_export

    base = "https://coach.invalid"
    course_url = "/coaching/tactical-course"
    post_headers = headers | {"Origin": base}
    old_offer = offer_slot.read_bytes()

    def candidates(_db, _subject, _budget, *, pairs):
        rows = []
        for skill, operation in pairs:
            deferred = (skill, operation) == ("hanging_piece", "prevent")
            rows.append(
                {
                    "skill": skill,
                    "operation": operation,
                    "examined": None if deferred else 3,
                    "limited": deferred,
                    "excluded": {} if deferred else {"private-test-marker": 1},
                    "status": "deferred: time budget" if deferred else "complete",
                }
            )
        groups = (
            [{"lesson": {"skill": "fork", "operation": "execute"}}]
            if ("fork", "execute") in pairs
            else []
        )
        return groups, rows

    def enqueue_default():
        response = client.post(
            course_url + "/prepare",
            data={"csrf": csrf},
            base_url=base,
            headers=post_headers,
        )
        assert response.status_code == 303

    with monkeypatch.context() as patch:
        patch.setattr(tactical_course, "candidates", candidates)
        patch.setattr(tactical_course_patterns, "own", lambda *_args: None)
        enqueue_default()
        tactical_course_worker.run(db, learner, project)
        assert offer_slot.read_bytes() == old_offer
        saved = json.loads(request_file.read_text())
        assert saved["state"] == "unavailable"
        assert [(r["skill"], r["operation"]) for r in saved["coverage"]] == list(CURRENT_PAIRS)
        assert "private-test-marker" not in json.dumps(saved)
        page = client.get(course_url, base_url=base, headers=headers)
        assert b"default preparation could not produce a course" in page.data
        assert b"no qualified group in the checked sample" in page.data
        assert b"owned source unavailable" in page.data and b"deferred" in page.data
        assert b"historical checks within bounded samples" in page.data
        assert b"previous course remains available" in page.data
        selected_budget = Budget(db, slice_seconds=SLICE_SECONDS)
        empty = tactical_course.build(
            db, learner, "test", budget=selected_budget, selected=["fork:execute"]
        )
        with pytest.raises(ValueError, match="unsupported pattern count"):
            build_export(db, learner, "test", empty, selected_budget)
        with pytest.raises(PreviewUnavailable):
            tactical_course.build(db, learner, "test")

        saved_bytes = request_file.read_bytes()
        forged = json.loads(saved_bytes)
        forged["coverage"][0]["skill"] = "invalid"
        request_file.write_text(json.dumps(forged))
        invalid = client.get(course_url, base_url=base, headers=headers)
        assert b"default preparation could not produce a course" not in invalid.data
        request_file.write_bytes(saved_bytes)

        original = tactical_course.readiness_selection

        def changed_source(*args):
            value = original(*args)
            with sqlite3.connect(path) as writer:
                writer.execute("UPDATE games SET event=event WHERE id=1")
            return value

        enqueue_default()
        with patch.context() as stale:
            stale.setattr(tactical_course, "readiness_selection", changed_source)
            tactical_course_worker.run(db, learner, project)
        assert offer_slot.read_bytes() == old_offer
        stale_result = json.loads(request_file.read_text())
        assert stale_result["state"] == "unavailable" and "coverage" not in stale_result

        # A source commit after the JSON is staged must not publish readiness.
        from contextlib import contextmanager

        from chess_coach import tactical_course_worker_guard

        real_stage = tactical_course_worker_guard.staged

        @contextmanager
        def changed_during_stage(slot, value):
            with real_stage(slot, value) as temporary:
                with sqlite3.connect(path) as writer:
                    writer.execute("UPDATE games SET event=event WHERE id=1")
                yield temporary

        enqueue_default()
        with patch.context() as staged_change:
            staged_change.setattr(tactical_course_worker_guard, "staged", changed_during_stage)
            tactical_course_worker.run(db, learner, project)
        assert offer_slot.read_bytes() == old_offer
        staged_result = json.loads(request_file.read_text())
        assert staged_result["state"] == "unavailable" and "coverage" not in staged_result

        enqueue_default()

        def replaced_request(*args):
            value = original(*args)
            item = json.loads(request_file.read_text())
            item["id"] = "f" * 32
            request_file.write_text(json.dumps(item))
            return value

        with patch.context() as replaced:
            replaced.setattr(tactical_course, "readiness_selection", replaced_request)
            tactical_course_worker.run(db, learner, project)
        assert offer_slot.read_bytes() == old_offer
        superseding = json.loads(request_file.read_text())
        assert superseding["id"] == "f" * 32 and "coverage" not in superseding
        request_file.write_bytes(saved_bytes)


def test_repeated_failure_coaching_preview_is_private_and_historical(tmp_path, monkeypatch):
    import json
    import sys

    import pytest

    # Exercise released v6 reconstruction through its real builder and sources.
    from chess_coach import tactical_course
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
    from tests.capture_certificate_fixture import certify
    from tests.capture_certificate_fixture import project as capture_project
    from tests.test_material_pipeline import LEARNER, make_game
    from tests.test_unified_sessions import token

    current_policy = tactical_course._policy

    def legacy_policy(selected):
        if selected is None:
            return (
                tactical_course.THEMATIC_VERSION,
                tactical_course.THEMATIC_POLICY,
                tactical_course.CURRENT_PAIRS,
                None,
            )
        chosen = tactical_course.pairs(selected)
        if chosen == [("hanging_piece", "execute")]:
            return (
                tactical_course.NAMED_VERSION,
                tactical_course.NAMED_POLICY,
                chosen,
                tactical_course.SELECTED_SECONDS,
            )
        return current_policy(selected)

    monkeypatch.setattr(tactical_course, "_policy", legacy_policy)
    project, path = capture_project(tmp_path, "project")
    planning = project / ".runtime" / "planning"
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
    certify(db, LEARNER, project)

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
    assert preview["kind"] == "local-tactical-course-v6"
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
    assert exported["kind"] == "local-tactical-course-export-v6"
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
    from chess_coach.related_capture_position import prompt_key
    from chess_coach.tactical_exposure_admission import eligible
    from chess_coach.tactical_exposure_check import check as exposure_check

    taught = chapter["source_snapshot"]["prompt_fen"]
    taught_key = prompt_key(taught)
    assert exposure_check(db, LEARNER, taught_key) == "provided"
    assert not eligible(db, LEARNER, {"prompt_key": taught_key})
    assert exposure_check(db, "other", taught_key) == "not_recorded"
    unprovided = prompt_key(chess.STARTING_FEN)
    assert exposure_check(db, LEARNER, unprovided) == "not_recorded"
    assert eligible(db, LEARNER, {"prompt_key": unprovided})
    supplied = chess.Board(taught)
    supplied.push_uci(chapter["source_snapshot"]["lines"][0].split()[0])
    assert exposure_check(db, LEARNER, prompt_key(supplied.fen())) == "provided"
    chapter_count = len(exported["export"]["chapters"])
    assert f"{chapter_count} chapter".encode() in shown.data
    version = exported["export_sha256"]
    download_url = course_url + "?download=1&version=" + version
    assert b"Download this version as PGN" in shown.data
    assert course_client.get(download_url, base_url="https://coach.invalid").status_code == 403
    before_files = {
        p: p.read_bytes() if p.exists() else None
        for p in (
            offer_slot,
            planning / "tactical-study-request.json",
            planning / "tactical-course-request.json",
        )
    }
    with monkeypatch.context() as patch:

        def forbidden(*_args, **_kwargs):
            raise AssertionError("download must not prepare, publish or read publication status")

        patch.setattr("chess_coach.tactical_export.build", forbidden)
        patch.setattr("chess_coach.web_tactical_course.status", forbidden)
        patch.setattr("chess_coach.web_tactical_course.preparation", forbidden)
        download = course_client.get(
            download_url + "&chapter=bad&line=bad&status=bad",
            base_url="https://coach.invalid",
            headers=course_headers,
        )
    expected_pgn = "\n\n".join(c["pgn"] for c in exported["export"]["chapters"]) + "\n"
    assert download.status_code == 200 and download.get_data(as_text=True) == expected_pgn
    assert download.mimetype == "application/x-chess-pgn"
    assert download.headers["Content-Disposition"] == 'attachment; filename="tactical-course.pgn"'
    assert download.headers["Cache-Control"] == "no-store"
    assert (
        db.connection.execute(
            "SELECT COUNT(*) FROM tactical_exposures WHERE kind='download'"
        ).fetchone()[0]
        > 0
    )
    with monkeypatch.context() as patch:
        patch.setattr(
            "chess_coach.web_tactical_exposure.record_exposure",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(sqlite3.OperationalError("synthetic")),
        )
        assert (
            course_client.get(
                course_url, base_url="https://coach.invalid", headers=course_headers
            ).status_code
            == 503
        )
        assert (
            course_client.get(
                download_url, base_url="https://coach.invalid", headers=course_headers
            ).status_code
            == 503
        )
    assert db.connection.total_changes == before_course_page
    assert all(
        (p.read_bytes() if p.exists() else None) == value for p, value in before_files.items()
    )
    for query in ("?download=1", "?download=1&version=" + "0" * 64):
        assert (
            course_client.get(
                course_url + query, base_url="https://coach.invalid", headers=course_headers
            ).status_code
            == 409
        )
    # Distinct chapters exercise ordering even when this private fixture has one chapter.
    with monkeypatch.context() as patch:
        from chess_coach import web_tactical_course

        original_offered = web_tactical_course.offered
        item, course = original_offered(project, path, LEARNER, "test")
        chapters = [{"pgn": "first"}, {"pgn": "second"}]
        patch.setattr(
            web_tactical_course, "offered", lambda *_: (item, {**course, "chapters": chapters})
        )
        ordered = course_client.get(
            download_url, base_url="https://coach.invalid", headers=course_headers
        )
        assert ordered.get_data(as_text=True) == "first\n\nsecond\n"
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
    assert (
        course_client.get(
            download_url, base_url="https://coach.invalid", headers=course_headers
        ).status_code
        == 404
    )
    export_path.write_bytes(exported_bytes)
    export_path.chmod(0o400)

    # Preparation is local, preserves the old offer until completion, and never queues a Study.
    from chess_coach import tactical_course_worker

    with course_client.session_transaction(base_url="https://coach.invalid") as session:
        course_csrf = session["csrf"]
    post_headers = course_headers | {"Origin": "https://coach.invalid"}
    local_url = course_url + "/prepare"
    assert (
        course_client.post(
            local_url, base_url="https://coach.invalid", headers=post_headers
        ).status_code
        == 403
    )
    response = course_client.post(
        local_url,
        data={"csrf": course_csrf},
        base_url="https://coach.invalid",
        headers=post_headers,
    )
    assert response.status_code == 303 and offer_slot.read_bytes() == original_offer
    assert not (planning / "tactical-study-request.json").exists()
    assert (
        b"preparation is queued"
        in course_client.get(
            course_url, base_url="https://coach.invalid", headers=course_headers
        ).data
    )
    import time

    from chess_coach import study_worker, tactical_course_worker_state

    original_write = tactical_course_worker_state.write

    def interrupted_write(path, value):
        if value["state"] == "complete":
            raise OSError("interrupted after publication")
        return original_write(path, value)

    with monkeypatch.context() as patch:
        patch.setenv("CHESS_PROJECT_ROOT", str(project))
        patch.setattr(study_worker, "active_deadline", lambda *_: "cooldown")
        patch.setattr(tactical_course_worker_state, "write", interrupted_write)
        study_worker.after_pipeline(db, LEARNER, time.monotonic())
    request_file = planning / "tactical-course-request.json"
    pending_bytes = request_file.read_bytes()
    assert json.loads(pending_bytes)["state"] == "running"
    published_bytes = offer_slot.read_bytes()
    offer_slot.write_bytes(original_offer)
    course_client.post(
        local_url,
        data={"csrf": course_csrf},
        base_url="https://coach.invalid",
        headers=post_headers,
    )
    assert request_file.read_bytes() == pending_bytes
    offer_slot.write_bytes(published_bytes)
    prepared_offer = json.loads(published_bytes)
    assert prepared_offer["hash"] == exported["export_sha256"]
    assert (planning / prepared_offer["file"]).is_file()
    from chess_coach.tactical_course_capacity import output as automatic_output

    saved_path, needed = automatic_output(project, planning, exported, Budget(db))
    assert not needed and saved_path.name == prepared_offer["file"]
    saved_bytes = saved_path.read_bytes()
    saved_path.chmod(0o600)
    saved_path.write_text("{}")
    assert (
        b"preparation completed"
        not in course_client.get(
            course_url, base_url="https://coach.invalid", headers=course_headers
        ).data
    )
    saved_path.write_bytes(saved_bytes)
    saved_path.chmod(0o400)
    assert (
        b"preparation completed"
        in course_client.get(
            course_url, base_url="https://coach.invalid", headers=course_headers
        ).data
    )
    assert not (planning / "tactical-study-request.json").exists()
    # A restart recognizes the same offer; a newer manual offer is not mislabeled.
    tactical_course_worker.run(db, LEARNER, project)
    assert json.loads(offer_slot.read_bytes()) == prepared_offer
    from chess_coach.tactical_course_offer import offer as manual_offer

    manual_offer(project, path, LEARNER, export_path, exported, Budget(db), enabled=True)
    manual_bytes = offer_slot.read_bytes()
    assert (
        b"newer course replaced"
        in course_client.get(
            course_url, base_url="https://coach.invalid", headers=course_headers
        ).data
    )
    course_client.post(
        local_url,
        data={"csrf": course_csrf},
        base_url="https://coach.invalid",
        headers=post_headers,
    )
    with monkeypatch.context() as patch:
        patch.setattr(
            tactical_course_worker,
            "build_preview",
            lambda *_a, **_k: (_ for _ in ()).throw(ValueError("unavailable")),
        )
        tactical_course_worker.run(db, LEARNER, project)
    assert offer_slot.read_bytes() == manual_bytes
    with monkeypatch.context() as patch:
        patch.setattr(
            "chess_coach.web_tactical_course.offered",
            lambda *_: (_ for _ in ()).throw(ValueError("unavailable")),
        )
        missing = course_client.get(
            course_url, base_url="https://coach.invalid", headers=course_headers
        )
        assert b"preparation is unavailable" in missing.data
        assert b"previous course remains" not in missing.data
    assert (
        b"preparation is unavailable"
        in course_client.get(
            course_url, base_url="https://coach.invalid", headers=course_headers
        ).data
    )
    offer_slot.write_bytes(original_offer)
    _default_course_readiness_workflow(
        db,
        LEARNER,
        project,
        path,
        course_client,
        course_headers,
        course_csrf,
        offer_slot,
        request_file,
        monkeypatch,
    )

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

    # A selected course uses the same background and exact-offer publication flow.
    selected_form = {"csrf": course_csrf, "mode": "selected", "pair": "fork:execute"}
    assert (
        course_client.post(
            local_url,
            data={
                **selected_form,
                "pair": [
                    "fork:execute",
                    "calculation:execute",
                    "mate_in_one:execute",
                    "hanging_piece:execute",
                ],
            },
            base_url="https://coach.invalid",
            headers=post_headers,
        ).status_code
        == 409
    )
    assert (
        course_client.post(
            local_url, data=selected_form, base_url="https://coach.invalid", headers=post_headers
        ).status_code
        == 303
    )
    tactical_course_worker.run(db, LEARNER, project)
    assert offer_slot.read_bytes() == original_offer
    unavailable_page = course_client.get(
        course_url, base_url="https://coach.invalid", headers=course_headers
    )
    assert b"selected preparation could not produce a course" in unavailable_page.data
    assert b"source records examined" in unavailable_page.data

    selected_form["pair"] = ["fork:execute", "hanging_piece:execute"]
    assert (
        course_client.post(
            local_url, data=selected_form, base_url="https://coach.invalid", headers=post_headers
        ).status_code
        == 303
    )
    selected_request = request_file.read_bytes()
    assert (
        course_client.post(
            local_url, data=selected_form, base_url="https://coach.invalid", headers=post_headers
        ).status_code
        == 303
    )
    assert request_file.read_bytes() == selected_request
    assert (
        course_client.post(
            local_url,
            data={**selected_form, "pair": list(reversed(selected_form["pair"]))},
            base_url="https://coach.invalid",
            headers=post_headers,
        ).status_code
        == 303
    )
    assert request_file.read_bytes() == selected_request
    assert (
        course_client.post(
            local_url,
            data={**selected_form, "pair": "fork:execute"},
            base_url="https://coach.invalid",
            headers=post_headers,
        ).status_code
        == 409
    )
    assert request_file.read_bytes() == selected_request

    # An altered same-id request cannot receive another selection's result.
    original_build = tactical_course_worker.build_preview

    def changed_selection(*args, **kwargs):
        candidate = original_build(*args, **kwargs)
        altered = json.loads(request_file.read_text())
        altered["selection"] = ["fork:execute"]
        request_file.write_text(json.dumps(altered))
        return candidate

    with monkeypatch.context() as patch:
        patch.setattr(tactical_course_worker, "build_preview", changed_selection)
        tactical_course_worker.run(db, LEARNER, project)
    assert offer_slot.read_bytes() == original_offer
    assert json.loads(request_file.read_text())["selection"] == ["fork:execute"]
    request_file.write_bytes(selected_request)

    tactical_course_worker.run(db, LEARNER, project)
    selected_offer = json.loads(offer_slot.read_text())
    selected_path = planning / selected_offer["file"]
    selected_export = json.loads(selected_path.read_text())
    selected_v5_hash = selected_export["export_sha256"]
    selected_scope = selected_export["export"]["selection"]
    assert selected_export["kind"] == "local-tactical-course-export-v7"
    assert selected_scope["pairs"] == [["hanging_piece", "execute"], ["fork", "execute"]]
    assert selected_scope["work_policy"] == "selected-tactical-work-v1"
    assert (selected_scope["related_match_seconds"], selected_scope["total_seconds"]) == (8, 60)
    assert selected_export["export"]["patterns"][0]["kind"] == "capture"
    assert "Worked example, ungraded" in selected_export["export"]["chapters"][0]["pgn"]
    with monkeypatch.context() as patch:
        patch.setenv("LICHESS_STUDY_TOKEN", "fixture-token")
        patch.setenv("CHESS_PROJECT_ROOT", str(project))
        assert (
            course_client.post(
                course_url + "/study",
                data={"csrf": course_csrf, "version": selected_v5_hash},
                base_url="https://coach.invalid",
                headers=post_headers,
            ).status_code
            == 303
        )
        selected_study_request = json.loads(request_slot.read_text())
        assert selected_study_request["version"] == selected_v5_hash
        assert selected_study_request["file"] == selected_path.name
    offer_slot.write_bytes(original_offer)

    # A synthetic v1 contract retains its scope, hash, export and Study reconstruction.
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

    with study_revalidate(
        path, legacy_export, legacy_export["export_sha256"], project_root=project
    ) as check:
        check()
    selected_preview = study_preview(selected_export, selected_v5_hash)
    selected_preview_file = planning / "selected-preview.json"
    selected_preview_file.write_text(json.dumps(selected_preview))
    selected_preview_file.chmod(0o600)
    selected_copy = planning / "selected-export.json"
    export_candidate(
        project, selected_preview_file, selected_preview["preview_sha256"], selected_copy
    )
    assert json.loads(selected_copy.read_text()) == selected_export
    with study_revalidate(path, selected_export, selected_v5_hash, project_root=project) as check:
        check()
    changed_policy = json.loads(json.dumps(selected_preview))
    changed_policy["preview"]["selection"]["related_match_seconds"] = 9
    changed_policy["preview_sha256"] = preview_hash(changed_policy["preview"])
    from chess_coach.tactical_course_choice import SLICE_SECONDS as SELECTED_SECONDS

    with pytest.raises(ValueError):
        build_export(
            db, LEARNER, "test", changed_policy, Budget(db, slice_seconds=SELECTED_SECONDS)
        )
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
    # The same target has two legal captures; a real proof must not turn the other into a wrong move.
    multiple = chess.Board("4k3/p7/8/8/3q4/1N6/8/3RK3 b - - 0 1")
    db.connection.execute(
        """INSERT INTO puzzles(puzzle_id,corpus_id,fen,source,solution,rating,rating_deviation,themes_json,objective)
        VALUES('fixture-multiple',?,?,'https://example.invalid','a7a6 d1d4',1200,80,'["hangingPiece"]','unknown')""",
        (corpus_id, multiple.fen()),
    )
    db.connection.execute(
        "INSERT INTO puzzle_themes VALUES(?,?,'hangingPiece',1200)", (corpus_id, "fixture-multiple")
    )
    db.connection.execute("UPDATE puzzle_corpora SET state='ready' WHERE id=?", (corpus_id,))
    db.connection.commit()
    from tests.capture_certificate_fixture import prepare_corpus

    position_id = json.loads(first_content)["preview"]["chapters"][0]["source"]["position_id"]
    prepare_corpus(db, LEARNER, project, "test", position_id)
    related_preview_path = planning / "related-preview.json"
    related_output = planning / "related-export.json"
    prepare(project, related_preview_path)
    related_preview = json.loads(related_preview_path.read_bytes())
    from chess_coach.related_capture import _selection as capture_selection

    old_selection = capture_selection(db, LEARNER, position_id, "test")
    new_selection = capture_selection(
        db, LEARNER, position_id, "test", familiar_data=paged_familiarity(db, LEARNER, Budget(db))
    )
    assert new_selection == old_selection
    assert old_selection is not None
    source, baseline, corpus, ordered, _, _ = old_selection
    assert source["provenance"]["position_id"] == position_id
    assert source["provenance"]["evidence_id"] == selected_id
    candidate = next(item for item in ordered if item["key"] == "fixture-related")
    assert (candidate["type"], candidate["version"]) == ("corpus", "test")
    assert eligible(db, LEARNER, candidate)

    # Use the worker's real assessment and rebind it to this exact source and puzzle.
    from chess_coach.related_capture_assessment import setup as assessment_setup
    from chess_coach.related_capture_features import certified_features
    from chess_coach.related_capture_prepared_assessment import assessment

    prepared = assessment(
        db,
        "test",
        candidate["key"],
        source,
        baseline,
        corpus,
        LEARNER,
        original_familiarity(db, LEARNER)[1],
    )
    assert prepared["source_fingerprint"] == assessment_setup(db, "test", candidate["key"])[2]
    assert prepared["history_mode"] == "zeroing_setup"
    assert prepared["target"] == "d4" and prepared["proof"]["status"] == "correct"
    context = prepared["context"]
    assert context is not None and context["corpus_checksum"] == "checksum"
    source_feature = certified_features(source["prompt_fen"], source["lines"][0].split())
    assert source_feature is not None
    assert context["source_mechanism"] == {
        field: source_feature[field] for field in ("mover", "target", "geometry")
    }
    assert context["content_rating"] == 1200 and context["content_deviation"] == 80
    alternate = next(item for item in ordered if item["key"] == "fixture-multiple")
    alternate_proof = assessment(
        db,
        "test",
        alternate["key"],
        source,
        baseline,
        corpus,
        LEARNER,
        original_familiarity(db, LEARNER)[1],
    )
    from chess_coach.tactical_course_capture_chapter import chapter as capture_chapter

    ungraded = capture_chapter(db, LEARNER, old_selection, alternate, alternate_proof)
    assert ungraded["mode"] == "conceal" and "ungraded" in ungraded["pgn"]
    alternate_board = chess.Board(ungraded["source_snapshot"]["prompt_fen"])
    assert {move.uci() for move in alternate_board.legal_moves if move.to_square == chess.D4} == {
        "b3d4",
        "d1d4",
    }

    # The selected course uses the genuine prepared assessment, not a worked-line substitute.
    from chess_coach.course_gamebook import capture as faithful_capture
    from chess_coach.fact_fingerprint import canonical
    from chess_coach.tactical_course import build as build_course

    learning_tables = (
        "unified_sessions",
        "unified_session_events",
        "training_attempts",
        "mastery_events",
    )
    learning_before = {
        table: db.connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        for table in learning_tables
    }
    # Exercise the actual current default route before either related chapter is served.
    with monkeypatch.context() as current_default:
        current_default.setattr(tactical_course, "_policy", current_policy)
        default_course = build_course(db, LEARNER, "test", budget=Budget(db))
        assert default_course["kind"] == "local-tactical-course-v15"
        explain, worked_default, exercise = default_course["preview"]["chapters"]
        assert [part["role"] for part in (explain, worked_default, exercise)] == [
            "explanation",
            "worked",
            "practice",
        ]
        assert explain["source"] == worked_default["source"]
        assert explain["source"]["evidence_id"] == selected_id
        assert exercise["source"]["binding"]["assessment"] == prepared
        explanation = chess.pgn.read_game(io.StringIO(explain["pgn"]))
        assert explanation is not None and not explanation.errors
        explanation_note = " ".join(explanation.comment.split())
        assert "White to move" in explanation_note and "rook" in explanation_note
        assert "queen on d4" in explanation_note and "Rxd4" in explanation_note
        assert "net gain of at least three material points" in explanation_note
        assert "Played" in explanation_note and "Source review:" in explanation_note
        default_export = build_export(db, LEARNER, "test", default_course, Budget(db))
        assert default_export["kind"] == "local-tactical-course-export-v15"
        assert study_preview(default_export, default_export["export_sha256"]) == default_course
        with study_revalidate(
            path, default_export, default_export["export_sha256"], project_root=project
        ) as check:
            check()
        invalid_roles = json.loads(json.dumps(default_course))
        invalid_roles["preview"]["chapters"][0]["role"] = "worked"
        invalid_roles["preview_sha256"] = preview_hash(invalid_roles["preview"])
        with pytest.raises(ValueError, match="capture chapter order differs"):
            build_export(db, LEARNER, "test", invalid_roles, Budget(db))
        invalid_source = json.loads(json.dumps(default_course))
        invalid_source["preview"]["chapters"][0]["source"]["evidence_id"] += 1
        invalid_source["preview_sha256"] = preview_hash(invalid_source["preview"])
        with pytest.raises(ValueError, match="course chapter differs"):
            build_export(db, LEARNER, "test", invalid_source, Budget(db))
        missing = build_course(db, LEARNER, "not-configured", budget=Budget(db))
        assert [part["role"] for part in missing["preview"]["chapters"]] == [
            "explanation",
            "worked",
        ]
        assert missing["preview"]["selection"]["unavailable"][0]["reason"] == (
            "related corpus or compatible unfamiliar example unavailable"
        )
        assert build_export(db, LEARNER, "not-configured", missing, Budget(db))
        unknown = json.loads(json.dumps(default_course))
        unknown["kind"] = unknown["preview"]["kind"] = "local-tactical-course-v99"
        unknown["preview_sha256"] = preview_hash(unknown["preview"])
        with pytest.raises(ValueError, match="unsupported preview"):
            build_export(db, LEARNER, "test", unknown, Budget(db))
        old_offer, old_request = offer_slot.read_bytes(), request_file.read_bytes()
        try:
            response = course_client.post(
                local_url,
                data={"csrf": course_csrf},
                base_url="https://coach.invalid",
                headers=post_headers,
            )
            assert response.status_code == 303
            tactical_course_worker.run(db, LEARNER, project)
            default_offer_bytes = offer_slot.read_bytes()
            default_offer = json.loads(default_offer_bytes)
            worker_default = json.loads((planning / default_offer["file"]).read_text())
            assert canonical(worker_default) == canonical(default_export)
            # Produce the released v9 layout through its actual historical worker policy.
            with monkeypatch.context() as historical:
                historical.setattr(
                    tactical_course,
                    "_policy",
                    lambda _selected: (
                        tactical_course.DEFAULT_ROLES_VERSION,
                        tactical_course.DEFAULT_ROLES_POLICY,
                        tactical_course.CURRENT_PAIRS,
                        None,
                    ),
                )
                response = course_client.post(
                    local_url,
                    data={"csrf": course_csrf},
                    base_url="https://coach.invalid",
                    headers=post_headers,
                )
                assert response.status_code == 303
                tactical_course_worker.run(db, LEARNER, project)
                historical_offer_bytes = offer_slot.read_bytes()
                historical_offer = json.loads(historical_offer_bytes)
                historical_export = json.loads((planning / historical_offer["file"]).read_text())
                assert historical_export["kind"] == "local-tactical-course-export-v9"
        finally:
            offer_slot.write_bytes(old_offer)
            request_file.write_bytes(old_request)
    # The real selected contract uses the same roles before related practice is served.
    with monkeypatch.context() as current_selected:
        current_selected.setattr(tactical_course, "_policy", current_policy)
        selected_roles = build_course(
            db,
            LEARNER,
            "test",
            selected=["hanging_piece:execute"],
            budget=Budget(db, slice_seconds=SELECTED_SECONDS),
        )
        assert selected_roles["kind"] == "local-tactical-course-v10"
        assert canonical(selected_roles["preview"]["chapters"]) == canonical(
            default_course["preview"]["chapters"]
        )
        assert selected_roles["preview"]["selection"]["pairs"] == [["hanging_piece", "execute"]]
        assert selected_roles["preview"]["selection"]["related_match_seconds"] == SELECTED_SECONDS
        selected_roles_export = build_export(
            db, LEARNER, "test", selected_roles, Budget(db, slice_seconds=SELECTED_SECONDS)
        )
        assert selected_roles_export["kind"] == "local-tactical-course-export-v10"
        assert (
            study_preview(selected_roles_export, selected_roles_export["export_sha256"])
            == selected_roles
        )
        with study_revalidate(
            path,
            selected_roles_export,
            selected_roles_export["export_sha256"],
            project_root=project,
        ) as check:
            check()
        with pytest.raises(ValueError, match="selected course work policy differs"):
            build_export(db, LEARNER, "test", selected_roles, Budget(db))
        selected_tampered = json.loads(json.dumps(selected_roles))
        selected_tampered["preview"]["chapters"][0]["source"]["evidence_id"] += 1
        selected_tampered["preview_sha256"] = preview_hash(selected_tampered["preview"])
        with pytest.raises(ValueError, match="course chapter differs"):
            build_export(
                db, LEARNER, "test", selected_tampered, Budget(db, slice_seconds=SELECTED_SECONDS)
            )
        selected_mixed = json.loads(json.dumps(selected_roles))
        selected_mixed["preview"]["selection"]["pairs"].append(["fork", "execute"])
        selected_mixed["preview_sha256"] = preview_hash(selected_mixed["preview"])
        with pytest.raises(ValueError, match="named capture selection differs"):
            build_export(
                db, LEARNER, "test", selected_mixed, Budget(db, slice_seconds=SELECTED_SECONDS)
            )
        selected_missing = build_course(
            db,
            LEARNER,
            "not-configured",
            selected=["hanging_piece:execute"],
            budget=Budget(db, slice_seconds=SELECTED_SECONDS),
        )
        assert [part["role"] for part in selected_missing["preview"]["chapters"]] == [
            "explanation",
            "worked",
        ]
        assert selected_missing["preview"]["selection"]["unavailable"][0]["reason"] == (
            "related corpus or compatible unfamiliar example unavailable"
        )
        assert build_export(
            db,
            LEARNER,
            "not-configured",
            selected_missing,
            Budget(db, slice_seconds=SELECTED_SECONDS),
        )
        selected_preview_path = planning / "selected-roles-preview.json"
        selected_preview_path.write_text(json.dumps(selected_roles))
        selected_preview_path.chmod(0o600)
        selected_output_path = planning / "selected-roles-export.json"
        export_candidate(
            project, selected_preview_path, selected_roles["preview_sha256"], selected_output_path
        )
        assert canonical(json.loads(selected_output_path.read_text())) == canonical(
            selected_roles_export
        )
        old_offer, old_request = offer_slot.read_bytes(), request_file.read_bytes()
        try:
            response = course_client.post(
                local_url,
                data={"csrf": course_csrf, "mode": "selected", "pair": "hanging_piece:execute"},
                base_url="https://coach.invalid",
                headers=post_headers,
            )
            assert response.status_code == 303
            tactical_course_worker.run(db, LEARNER, project)
            roles_offer_bytes = offer_slot.read_bytes()
            roles_offer = json.loads(roles_offer_bytes)
            roles_worker = json.loads((planning / roles_offer["file"]).read_text())
            assert canonical(roles_worker) == canonical(selected_roles_export)
        finally:
            offer_slot.write_bytes(old_offer)
            request_file.write_bytes(old_request)

    # Reconstruct the released v8 contract through its actual two-role builder.
    named = build_course(
        db,
        LEARNER,
        "test",
        selected=["hanging_piece:execute"],
        budget=Budget(db, slice_seconds=SELECTED_SECONDS),
    )
    assert named["kind"] == "local-tactical-course-v8"
    assert named["preview"]["selection"]["pairs"] == [["hanging_piece", "execute"]]
    worked, practice = named["preview"]["chapters"]
    assert worked["source"]["type"] == "own-game"
    assert practice["source"]["type"] == "corpus"
    assert (
        practice["source"]["version"] == "test" and practice["source"]["key"] == "fixture-related"
    )
    assert practice["source"]["binding"]["evidence_id"] == selected_id
    assert practice["source"]["binding"]["assessment"] == prepared
    assert practice["mode"] == "gamebook" and faithful_capture(practice["source_snapshot"])
    parsed_practice = chess.pgn.read_game(io.StringIO(practice["pgn"]))
    assert parsed_practice is not None and not parsed_practice.errors
    assert (
        parsed_practice.headers["White"] == "White" and parsed_practice.headers["Black"] == "Black"
    )
    practice_note = " ".join(parsed_practice.comment.split())
    assert practice["orientation"] == "white" and "White to move" in practice_note
    assert "queen on d4" in practice_note and "In Lichess, use Preview" in practice_note
    assert "checked automatically and completes this one-move exercise" in practice_note
    assert "Use your coach for practice that is checked and recorded" in practice_note
    assert parsed_practice.variations[0].move.uci() == "d1d4"
    named_export = build_export(
        db, LEARNER, "test", named, Budget(db, slice_seconds=SELECTED_SECONDS)
    )
    assert named_export["kind"] == "local-tactical-course-export-v8"
    assert study_preview(named_export, named_export["export_sha256"]) == named
    with study_revalidate(
        path, named_export, named_export["export_sha256"], project_root=project
    ) as check:
        check()
    altered = json.loads(json.dumps(named))
    altered["preview"]["chapters"][1]["source"]["binding"]["assessment"]["source_fingerprint"] = (
        "0" * 64
    )
    altered["preview_sha256"] = preview_hash(altered["preview"])
    with pytest.raises(ValueError):
        build_export(db, LEARNER, "test", altered, Budget(db, slice_seconds=SELECTED_SECONDS))
    altered = json.loads(json.dumps(named))
    altered["preview"]["selection"]["pairs"].append(["fork", "execute"])
    altered["preview_sha256"] = preview_hash(altered["preview"])
    with pytest.raises(ValueError, match="named capture selection differs"):
        build_export(db, LEARNER, "test", altered, Budget(db, slice_seconds=SELECTED_SECONDS))

    saved_offer, saved_request = offer_slot.read_bytes(), request_file.read_bytes()
    try:
        response = course_client.post(
            local_url,
            data={"csrf": course_csrf, "mode": "selected", "pair": "hanging_piece:execute"},
            base_url="https://coach.invalid",
            headers=post_headers,
        )
        assert response.status_code == 303
        tactical_course_worker.run(db, LEARNER, project)
        named_offer_bytes = offer_slot.read_bytes()
        named_offer = json.loads(named_offer_bytes)
        worker_export = json.loads((planning / named_offer["file"]).read_text())
        assert worker_export["export_sha256"] == named_export["export_sha256"]
        assert canonical(worker_export) == canonical(named_export)
    finally:
        offer_slot.write_bytes(saved_offer)
        request_file.write_bytes(saved_request)
    assert learning_before == {
        table: db.connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        for table in learning_tables
    }
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
    selected_calls = []

    def selected_publish(database, intent_path, course, *, action, check=None):
        selected_calls.append((intent_path, course, action, check))
        return "selected destination"

    with monkeypatch.context() as patch:
        patch.setattr(tactical_session, "_publish", selected_publish)
        assert (
            tactical_session.publish_locked(project, selected_path, selected_v5_hash)
            == "selected destination"
        )
    assert selected_calls[0][1]["course_sha256"] == selected_v5_hash
    assert selected_calls[0][2].keywords["strict"] is True
    assert selected_calls[0][3] is selected_calls[0][2].keywords["check"]

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

    # Serving the new practice records exposure; preserve the older unseen checks first.
    prior_offer = offer_slot.read_bytes()
    try:
        offer_slot.write_bytes(named_offer_bytes)
        shown_practice = course_client.get(
            course_url + "?version=" + named_offer["hash"] + "&chapter=1",
            base_url="https://coach.invalid",
            headers=course_headers,
        )
        assert shown_practice.status_code == 200
        assert b"Open related capture practice in the coach" in shown_practice.data
        assert b"Moves in a Study do not update your coach practice record" in shown_practice.data
        assert (
            db.connection.execute(
                "SELECT 1 FROM tactical_exposures WHERE artifact_hash=? AND chapter_index=1 AND kind='served'",
                (named_offer["hash"],),
            ).fetchone()
            is not None
        )
    finally:
        offer_slot.write_bytes(prior_offer)
    # An already delivered prompt makes the newer default unavailable across artifacts.
    try:
        offer_slot.write_bytes(default_offer_bytes)
        stale_default = course_client.get(
            course_url + "?version=" + default_offer["hash"] + "&chapter=2",
            base_url="https://coach.invalid",
            headers=course_headers,
        )
        assert (
            stale_default.status_code == 200
            and b"No current prepared course is available" in stale_default.data
        )
        assert (
            db.connection.execute(
                "SELECT 1 FROM tactical_exposures WHERE artifact_hash=? AND chapter_index=2 AND kind='served'",
                (default_offer["hash"],),
            ).fetchone()
            is None
        )
    finally:
        offer_slot.write_bytes(prior_offer)
    # The real v9 view records its own delivery after the older baseline checks.
    try:
        offer_slot.write_bytes(historical_offer_bytes)
        shown_default = course_client.get(
            course_url + "?version=" + historical_offer["hash"] + "&chapter=2",
            base_url="https://coach.invalid",
            headers=course_headers,
        )
        assert shown_default.status_code == 200
        assert b"Open related capture practice in the coach" in shown_default.data
        assert (
            db.connection.execute(
                "SELECT 1 FROM tactical_exposures WHERE artifact_hash=? AND chapter_index=2 AND kind='served'",
                (historical_offer["hash"],),
            ).fetchone()
            is not None
        )
    finally:
        offer_slot.write_bytes(prior_offer)
    # The actual selected v10 view and download record their own exposure.
    try:
        offer_slot.write_bytes(roles_offer_bytes)
        selected_page = course_client.get(
            course_url + "?version=" + roles_offer["hash"] + "&chapter=2",
            base_url="https://coach.invalid",
            headers=course_headers,
        )
        assert selected_page.status_code == 200
        assert b"Open related capture practice in the coach" in selected_page.data
        assert (
            db.connection.execute(
                "SELECT 1 FROM tactical_exposures WHERE artifact_hash=? AND chapter_index=2 AND kind='served'",
                (roles_offer["hash"],),
            ).fetchone()
            is not None
        )
        selected_download = course_client.get(
            course_url + "?download=1&version=" + roles_offer["hash"],
            base_url="https://coach.invalid",
            headers=course_headers,
        )
        assert selected_download.status_code == 200
        assert (
            selected_download.get_data(as_text=True)
            == "\n\n".join(part["pgn"] for part in selected_roles_export["export"]["chapters"])
            + "\n"
        )
    finally:
        offer_slot.write_bytes(prior_offer)
    assert learning_before == {
        table: db.connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        for table in learning_tables
    }

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
    with (
        pytest.raises(ValueError),
        study_revalidate(path, selected_export, selected_v5_hash, project_root=project),
    ):
        pass
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
    certify(db, LEARNER, project)
    prepare(project, reviewed_first)
    review_evidence(db, other_id, decision="accept", actor="fixture")
    certify(db, LEARNER, project)
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

    # SQLite wraps a signal raised inside a UDF; ordinary callback errors remain errors.
    import signal

    old_handler = signal.getsignal(signal.SIGALRM)

    def alarm_in_callback():
        signal.raise_signal(signal.SIGALRM)

    db.connection.create_function("synthetic_course_callback", 0, alarm_in_callback)
    with pytest.raises(PreviewDeadline), Budget(db).scope(snapshot=True):
        db.connection.execute("SELECT synthetic_course_callback()").fetchone()
    assert signal.getsignal(signal.SIGALRM) == old_handler
    assert signal.getitimer(signal.ITIMER_REAL) == (0.0, 0.0)
    assert not db.connection.in_transaction

    with monkeypatch.context() as patch:
        real_monotonic = time.monotonic
        with pytest.raises(PreviewDeadline), Budget(db).scope(snapshot=True):
            patch.setattr(time, "monotonic", lambda: real_monotonic() + 100)
            db.connection.execute(
                "WITH RECURSIVE n(x) AS (VALUES(1) UNION ALL "
                "SELECT x+1 FROM n WHERE x<10000) SELECT sum(x) FROM n"
            ).fetchone()
    assert not db.connection.in_transaction

    with monkeypatch.context() as patch:
        real_monotonic = time.monotonic

        def bad_callback():
            patch.setattr(time, "monotonic", lambda: real_monotonic() + 100)
            raise ValueError("synthetic invalid data")

        db.connection.create_function("synthetic_course_callback", 0, bad_callback)
        with (
            pytest.raises(sqlite3.OperationalError, match="user-defined function raised exception"),
            Budget(db).scope(snapshot=True),
        ):
            db.connection.execute("SELECT synthetic_course_callback()").fetchone()
    assert not db.connection.in_transaction
    assert signal.getsignal(signal.SIGALRM) == old_handler
    assert signal.getitimer(signal.ITIMER_REAL) == (0.0, 0.0)
    assert db.connection.execute("SELECT 1").fetchone()[0] == 1

    from chess_coach.tactical_course_deadline import DeadlineConflict

    signal.setitimer(signal.ITIMER_REAL, 30)
    try:
        with pytest.raises(DeadlineConflict), Budget(db).scope(snapshot=True):
            pass
        assert signal.getitimer(signal.ITIMER_REAL)[0] > 0
        assert signal.getsignal(signal.SIGALRM) == old_handler
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)

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

    read_only = Database(path, capture_root=project)
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

    reading = Database(path, capture_root=project)
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
    db = Database(path, capture_root=project)
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

                def add_sample(db, *, fen=fen, second=False):
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
                    if second:
                        db.connection.execute(
                            """INSERT INTO puzzles(puzzle_id,corpus_id,fen,source,solution,rating,
                            rating_deviation,themes_json,objective) SELECT 'sample2',corpus_id,?,
                            source,solution,rating,rating_deviation,themes_json,objective
                            FROM puzzles WHERE puzzle_id='sample' AND corpus_id=?""",
                            ("4k3/7p/8/2b5/8/3R4/PP6/7K b - - 0 1", corpus),
                        )
                        db.connection.execute(
                            "INSERT INTO puzzle_themes VALUES(?,'sample2','defensiveMove',1200)",
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
                add_sample(assessed, second=True)
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

                    def assessment_get(path, client=assessment_client, headers=assessment_headers):
                        return client.get(path, base_url="https://coach.invalid", headers=headers)

                    assessment_preview = assessment_get(
                        f"/evidence/{assessed_id}/related-created-exposure"
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
                    assessment_page = assessment_get(begun.headers["Location"])
                    assert b"rook on d3" in assessment_page.data
                    followup_url = f"/evidence/{assessed_id}/related-created-exposure"
                    followup_text = b"Find another unfamiliar example with this exposure pattern"
                    assert followup_text not in assessment_page.data
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
                    pending_page = assessment_get(answered.headers["Location"])
                    assert b"Verification is queued" in pending_page.data
                    assert followup_text not in pending_page.data
                    assert verify_objectives(assessed, LEARNER)["outcomes"] == {"correct": 1}
                    import json

                    stored = assessed.connection.execute(
                        "SELECT result_json FROM objective_results"
                    ).fetchone()[0]
                    assert json.loads(stored)["learning_eligible"] is False
                    result_page = assessment_get(answered.headers["Location"])
                    assert b"Verified correct" in result_page.data
                    assert (
                        followup_text in result_page.data
                        and followup_url.encode() in result_page.data
                    )
                    assert (
                        show(assessed, attempt, LEARNER)["verification"]["assistance"]
                        == "unassisted"
                    )
                    before = assessed.connection.total_changes
                    followup = assessment_get(followup_url)
                    assert followup.status_code == 200 and b"Replay this example" in followup.data
                    assert assessed.connection.total_changes == before
                    next_start = assessment_client.post(
                        f"{followup_url}/start",
                        base_url="https://coach.invalid",
                        headers=assessment_headers | {"Origin": "https://coach.invalid"},
                        data={
                            "csrf": token(followup, "csrf"),
                            "reference": token(followup, "reference"),
                        },
                    )
                    assert next_start.status_code == 303
                    next_attempt = next_start.headers["Location"].rsplit("/", 1)[-1]
                    prompts = assessed.connection.execute(
                        "SELECT prompt_fen FROM unified_sessions WHERE attempt_id IN (?,?)",
                        (attempt, next_attempt),
                    ).fetchall()
                    assert len(prompts) == 2 and prompts[0][0] != prompts[1][0]
                    empty = assessment_get(followup_url)
                    assert b"insufficient compatible unfamiliar examples" in empty.data
                    with assessment_patch.context() as control:
                        for verification in (
                            {"status": "correct", "assistance": "hinted"},
                            {"status": "unresolved", "assistance": "unassisted"},
                        ):
                            control.setattr(
                                "chess_coach.objective_session_view.latest",
                                lambda *_, value=verification: value,
                            )
                            assert (
                                followup_text
                                not in assessment_get(answered.headers["Location"]).data
                            )
                    review_evidence(assessed, assessed_id, decision="reject", actor="fixture")
                    stale = assessment_get(answered.headers["Location"])
                    assert stale.status_code == 404 and followup_text not in stale.data
                assessed.close()

                # A separate encounter verifies the miss cue with the actual objective worker.
                from chess_coach.related_created import start_related as start_created

                missed = make_protection_game(Path(":memory:"), patch, created=True)
                missed_id = material_decision(missed, 1, LEARNER)["evidence_ids"][0]
                add_sample(missed, fen="4k3/7p/8/2b5/8/3R3b/1P2P3/5b1K b - - 0 1")
                candidate = created_preview(missed, LEARNER, missed_id, "test")
                start_created(
                    missed,
                    attempt_id="missed",
                    subject=LEARNER,
                    evidence_id=missed_id,
                    corpus_version="test",
                    reference=candidate["items"][0]["reference"],
                    assessment=True,
                )
                submit(missed, "missed", LEARNER, event_id="answer", move="e2e3")
                assert verify_objectives(missed, LEARNER)["outcomes"] == {"incorrect": 1}
                missed_state = show(missed, "missed", LEARNER)
                assert missed_state["created_target"] == "d3"
                assert missed_state["verification"]["capture_san"] == "Bxd3"
                with patch.context() as next_action:
                    next_action.setattr(
                        "chess_coach.web_unified_practice.database", lambda db=missed: db
                    )
                    page = assessment_app.test_client().get(
                        "/unified/missed",
                        base_url="https://coach.invalid",
                        headers=assessment_headers,
                    )
                    assert followup_text in page.data
                    assert b"check what can capture the named piece after your move" in page.data
                    assert b"even if that piece stays put" in page.data
                missed.close()

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
                assert followup_text not in result.data
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

    data_dir = tmp_path / ".runtime" / "data"
    data_dir.mkdir(parents=True, mode=0o700)
    planning = tmp_path / ".runtime" / "planning"
    planning.mkdir(mode=0o700)
    path = data_dir / "protection-coaching.sqlite"
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

    from chess_coach import tactical_course, tactical_course_budget, tactical_course_resolve
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
        current_policy = tactical_course._policy

        def released_v13(selected):
            if selected is None:
                return (
                    tactical_course.DEFAULT_FORK_VERSION,
                    tactical_course.DEFAULT_FORK_POLICY,
                    tactical_course.CURRENT_PAIRS,
                    None,
                )
            return current_policy(selected)

        with patch.context() as historical:
            historical.setattr(tactical_course, "_policy", released_v13)
            historical_course = tactical_preview(db, LEARNER, "test")
        course = tactical_preview(db, LEARNER, "test")
        exported = tactical_export(db, LEARNER, "test", course, CourseBudget(db))
    assert historical_course["kind"] == "local-tactical-course-v13"
    assert course["kind"] == "local-tactical-course-v15"
    assert next(p for p in course["preview"]["patterns"] if p["kind"] == "protection")
    assert expected[1] in historical_course["preview"]["chapters"]
    assert [ch["role"] for ch in course["preview"]["chapters"]] == [
        "explanation",
        "worked",
        "practice",
    ]
    assert exported["export"]["chapters"] == course["preview"]["chapters"]
    pattern = next(p for p in course["preview"]["patterns"] if p["kind"] == "protection")
    assert pattern["local_challenge"] == "/plan/protection/finder"
    related = next(ch for ch in course["preview"]["chapters"] if ch["source"]["type"] == "corpus")
    assert related["mode"] == "conceal" and "Ungraded rehearsal" in related["pgn"]
    assert "profitable immediate capture" in related["pgn"] and "CC0" in related["pgn"]

    from copy import deepcopy

    from chess_coach.course_preview import preview_hash
    from chess_coach.tactical_study_preview import preview as study_preview

    legacy = deepcopy(historical_course)
    legacy["kind"] = legacy["preview"]["kind"] = "local-tactical-course-v2"
    legacy["preview"]["policy"] = "provisional-recurring-tactics-v2"
    legacy["preview"]["selection"].pop("protection_per_band")
    legacy["preview"]["patterns"][0]["local_challenge"] = None
    legacy["preview"]["chapters"].remove(
        next(ch for ch in legacy["preview"]["chapters"] if ch["source"]["type"] == "corpus")
    )
    legacy["preview"]["selection"]["unavailable"].append(
        {"skill": "hanging_piece", "operation": "prevent", "reason": "related matching unsupported"}
    )
    legacy["preview_sha256"] = preview_hash(legacy["preview"])
    legacy_export = tactical_export(db, LEARNER, "test", legacy, CourseBudget(db))
    assert study_preview(legacy_export, legacy_export["export_sha256"]) == legacy

    from chess_coach.tactical_course_choice import SLICE_SECONDS as SELECTED_SECONDS

    historical_export = tactical_export(db, LEARNER, "test", historical_course, CourseBudget(db))
    assert study_preview(historical_export, historical_export["export_sha256"]) == historical_course
    old_default = deepcopy(historical_course)
    old_default["kind"] = old_default["preview"]["kind"] = "local-tactical-course-v4"
    old_default["preview"]["policy"] = "provisional-recurring-tactics-v4"
    old_default["preview_sha256"] = preview_hash(old_default["preview"])
    old_default_export = tactical_export(db, LEARNER, "test", old_default, CourseBudget(db))
    assert study_preview(old_default_export, old_default_export["export_sha256"]) == old_default
    selected_strict = tactical_preview(
        db,
        LEARNER,
        "test",
        selected=["hanging_piece:prevent"],
        budget=CourseBudget(db, slice_seconds=SELECTED_SECONDS),
    )
    assert selected_strict["kind"] == "local-tactical-course-v14"
    selected_chapters = selected_strict["preview"]["chapters"]
    assert [item["role"] for item in selected_chapters] == ["explanation", "worked", "practice"]
    assert (
        selected_chapters[0]["source"]["type"]
        == selected_chapters[1]["source"]["type"]
        == "own-game"
    )
    assert selected_chapters[2]["source"]["type"] == "corpus"
    assert selected_chapters[1]["source"]["version"] == "protect-threatened-piece-own-v1"
    assert selected_chapters[1]["source_snapshot"]["objective"] == "protect_threatened_piece"
    assert "Played a3." in selected_chapters[1]["pgn"]
    assert (
        "shown defense was checked separately from the played move" in selected_chapters[1]["pgn"]
    )
    assert "no profitable immediate capture" in selected_chapters[0]["pgn"]
    assert "Ungraded rehearsal" in selected_chapters[2]["pgn"]
    assert "profitable immediate capture" in selected_chapters[2]["pgn"]
    selected_strict_export = tactical_export(
        db, LEARNER, "test", selected_strict, CourseBudget(db, slice_seconds=SELECTED_SECONDS)
    )
    assert (
        study_preview(selected_strict_export, selected_strict_export["export_sha256"])
        == selected_strict
    )

    # Recheck an actual changed review without persisting the fixture mutation.
    evidence_id = selected_strict["preview"]["patterns"][0]["supporting_sources"][0]["evidence_id"]
    check_budget = CourseBudget(db, slice_seconds=SELECTED_SECONDS)
    db.connection.execute("SAVEPOINT protection_course_change")
    try:
        review_evidence(db, evidence_id, decision="reject", actor="fixture")
        with pytest.raises(ValueError):
            tactical_export(db, LEARNER, "test", selected_strict, check_budget)
    finally:
        db.connection.execute("ROLLBACK TO SAVEPOINT protection_course_change")
        db.connection.execute("RELEASE SAVEPOINT protection_course_change")

    from chess_coach import (
        objective_protection_snapshot,
        related_protection_features,
        tactical_course,
    )
    from chess_coach.tactical_course_offer import offer as offer_selected
    from chess_coach.tactical_course_publish import publish as publish_selected
    from chess_coach.tactical_study_current import revalidate as current_study

    selected_hash = selected_strict_export["export_sha256"]
    with current_study(
        path,
        selected_strict_export,
        selected_hash,
        project_root=tmp_path,
        subject=LEARNER,
        corpus="test",
    ) as check:
        check()
    selected_path = planning / "selected-protection-v14.json"
    publish_selected(selected_path, selected_strict_export, CourseBudget(db), readonly=True)
    offer_selected(
        tmp_path,
        path,
        LEARNER,
        selected_path,
        selected_strict_export,
        CourseBudget(db),
        enabled=True,
    )
    selected_app = create_app(
        db_path=path,
        subject=LEARNER,
        actor="fixture",
        corpus="test",
        login="login",
        origin="https://coach.invalid",
        project_root=tmp_path,
    )
    selected_client = selected_app.test_client()
    selected_headers = {"Tailscale-User-Login": "login"}

    def no_course_proof(*_args, **_kwargs):
        raise AssertionError("protection proof ran on course read")

    with monkeypatch.context() as reading:
        for module in (objective_protection_snapshot, related_protection_features):
            reading.setattr(module, "probe", no_course_proof)
            reading.setattr(module, "judge", no_course_proof)
        selected_page = selected_client.get(
            f"/coaching/tactical-course?version={selected_hash}",
            base_url="https://coach.invalid",
            headers=selected_headers,
        )
    assert selected_page.status_code == 200
    assert b"Understand the threatened piece" in selected_page.data
    assert b"no profitable immediate capture" in selected_page.data

    original_policy = tactical_course._policy

    def released_protection(selection):
        if selection == ["hanging_piece:prevent"]:
            return (
                tactical_course.THEMATIC_SELECTED_VERSION,
                tactical_course.THEMATIC_SELECTED_POLICY,
                [("hanging_piece", "prevent")],
                SELECTED_SECONDS,
            )
        return original_policy(selection)

    with monkeypatch.context() as historical:
        historical.setattr(tactical_course, "_policy", released_protection)
        old_selected = tactical_preview(
            db,
            LEARNER,
            "test",
            selected=["hanging_piece:prevent"],
            budget=CourseBudget(db, slice_seconds=SELECTED_SECONDS),
        )
    assert old_selected["kind"] == "local-tactical-course-v7"
    old_v7_export = tactical_export(
        db, LEARNER, "test", old_selected, CourseBudget(db, slice_seconds=SELECTED_SECONDS)
    )
    assert study_preview(old_v7_export, old_v7_export["export_sha256"]) == old_selected
    old_selected["kind"] = old_selected["preview"]["kind"] = "local-tactical-course-v5"
    old_selected["preview"]["policy"] = "provisional-recurring-tactics-v5"
    old_selected["preview_sha256"] = preview_hash(old_selected["preview"])
    old_selected_export = tactical_export(
        db, LEARNER, "test", old_selected, CourseBudget(db, slice_seconds=SELECTED_SECONDS)
    )
    assert study_preview(old_selected_export, old_selected_export["export_sha256"]) == old_selected

    with monkeypatch.context() as patch:
        from chess_coach import tactical_course_related

        original_selection = tactical_course_related.protection_selection

        def no_match(*args, **kwargs):
            selection = original_selection(*args, **kwargs)
            return (*selection[:3], [], *selection[4:])

        patch.setattr(tactical_course_related, "protection_selection", no_match)
        from chess_coach.tactical_exposure_record import record as record_delivery
        from chess_coach.tactical_study_current import revalidate as revalidate_study

        learner_counts = tuple(
            db.connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in (
                "evidence_mappings",
                "evidence_review_events",
                "training_attempts",
                "training_completions",
            )
        )
        default = tactical_preview(db, LEARNER, "test")
        selected = tactical_preview(
            db,
            LEARNER,
            "test",
            selected=["hanging_piece:prevent"],
            budget=CourseBudget(db, slice_seconds=SELECTED_SECONDS),
        )
        assert (default["kind"], selected["kind"]) == (
            "local-tactical-course-v15",
            "local-tactical-course-v14",
        )
        assert [item["role"] for item in selected["preview"]["chapters"]] == [
            "explanation",
            "worked",
            "practice",
        ]
        from chess_coach.tactical_course_protection import ContextUnavailable

        def unavailable_context(*_args):
            raise ContextUnavailable("fixture")

        with patch.context() as missing_context:
            missing_context.setattr(tactical_course_resolve, "teaching_source", unavailable_context)
            context_course = tactical_preview(db, LEARNER, "test")
            assert any(
                "Thematic defensive practice" in chapter["pgn"]
                for chapter in context_course["preview"]["chapters"]
            )
            assert tactical_export(db, LEARNER, "test", context_course, CourseBudget(db))
        db.connection.execute(
            "INSERT INTO puzzle_corpora(version,source,checksum,state) "
            "VALUES('unlicensed','https://example.invalid/','fixture','staging')"
        )
        unlicensed_id = db.connection.execute(
            "SELECT id FROM puzzle_corpora WHERE version='unlicensed'"
        ).fetchone()[0]
        db.connection.execute(
            """INSERT INTO puzzles(puzzle_id,corpus_id,fen,source,solution,rating,
            rating_deviation,themes_json,objective)
            SELECT puzzle_id,?,fen,source,solution,rating,rating_deviation,themes_json,objective
            FROM puzzles WHERE corpus_id=?""",
            (unlicensed_id, corpus_id),
        )
        db.connection.execute(
            "INSERT INTO puzzle_themes SELECT ?,puzzle_id,theme,rating FROM puzzle_themes "
            "WHERE corpus_id=?",
            (unlicensed_id, corpus_id),
        )
        db.connection.execute(
            "UPDATE puzzle_corpora SET state='ready' WHERE id=?", (unlicensed_id,)
        )
        db.connection.commit()
        unlicensed = tactical_preview(db, LEARNER, "unlicensed")
        assert not any(ch["source"]["type"] == "corpus" for ch in unlicensed["preview"]["chapters"])
        partial = tactical_preview(
            db,
            LEARNER,
            "unlicensed",
            selected=["hanging_piece:prevent"],
            budget=CourseBudget(db, slice_seconds=SELECTED_SECONDS),
        )
        assert [item["role"] for item in partial["preview"]["chapters"]] == [
            "explanation",
            "worked",
        ]
        assert partial["preview"]["selection"]["unavailable"]
        partial_export = tactical_export(
            db, LEARNER, "unlicensed", partial, CourseBudget(db, slice_seconds=SELECTED_SECONDS)
        )
        assert study_preview(partial_export, partial_export["export_sha256"]) == partial
        for prepared, budget in (
            (default, CourseBudget(db)),
            (selected, CourseBudget(db, slice_seconds=SELECTED_SECONDS)),
        ):
            worked = next(
                ch for ch in prepared["preview"]["chapters"] if ch["source"]["type"] == "corpus"
            )
            assert worked["mode"] == "conceal"
            assert "Thematic defensive practice, not a matched test" in worked["pgn"]
            assert "Ungraded rehearsal. White to move" in worked["pgn"]
            assert "other legal moves and later risks are ungraded" in worked["pgn"]
            assert "CC0" in worked["pgn"]
            candidate = tactical_export(db, LEARNER, "test", prepared, budget)
            assert study_preview(candidate, candidate["export_sha256"]) == prepared
            if prepared is default:
                default_export = candidate
            else:
                selected_export = candidate
        patch.setenv("CHESS_SUBJECT", LEARNER)
        patch.setenv("CHESS_CORPUS", "test")
        with revalidate_study(path, selected_export, selected_export["export_sha256"]) as check:
            check()
        chapter_index = next(
            i
            for i, ch in enumerate(default_export["export"]["chapters"])
            if ch["source"]["type"] == "corpus"
        )
        worked = default_export["export"]["chapters"][chapter_index]
        own_hash = default_export["export_sha256"]
        import chess_coach.web_tactical_course as web_course

        default_path = planning / "default-protection-v15.json"
        publish_selected(default_path, default_export, CourseBudget(db), readonly=True)
        offer_selected(
            tmp_path, path, LEARNER, default_path, default_export, CourseBudget(db), enabled=True
        )
        patch.setattr(web_course, "status", lambda *_args: {"configured": False})
        patch.setattr(web_course, "preparation", lambda *_args: None)
        patch.setattr(web_course, "preparation_details", lambda: None)
        app = create_app(
            db_path=path,
            subject=LEARNER,
            actor="fixture",
            corpus="test",
            login="login",
            origin="https://coach.invalid",
            project_root=tmp_path,
        )
        client = app.test_client()
        url = f"/coaching/tactical-course?version={own_hash}&chapter={chapter_index}"
        assert client.get(url, base_url="https://coach.invalid").status_code == 403
        with patch.context() as reading:
            for module in (objective_protection_snapshot, related_protection_features):
                reading.setattr(module, "probe", no_course_proof)
                reading.setattr(module, "judge", no_course_proof)
            page = client.get(
                url, base_url="https://coach.invalid", headers={"Tailscale-User-Login": "login"}
            )
        assert page.status_code == 200
        assert b"Thematic defensive practice, not a matched test" in page.data
        assert b"Learner side: White" in page.data and b"ungraded" in page.data
        with patch.context() as reading:
            for module in (objective_protection_snapshot, related_protection_features):
                reading.setattr(module, "probe", no_course_proof)
                reading.setattr(module, "judge", no_course_proof)
            download = client.get(
                f"/coaching/tactical-course?version={own_hash}&download=1",
                base_url="https://coach.invalid",
                headers={"Tailscale-User-Login": "login"},
            )
        assert download.status_code == 200 and b"Thematic defensive practice" in download.data
        with (
            pytest.raises(ValueError),
            revalidate_study(path, selected_export, selected_export["export_sha256"]),
        ):
            pass
        with revalidate_study(path, default_export, own_hash) as check:
            check()

        import httpx

        import chess_coach.study_anonymous as anonymous
        from chess_coach.study_publisher import publish
        from chess_coach.study_remote import Remote
        from tests.test_private_study import Provider

        class OwnerProvider(Provider):
            def request(self, method, url, **kwargs):
                path = httpx.URL(url).path
                if path == "/api/account":
                    return httpx.Response(
                        200,
                        json={"id": LEARNER, "username": LEARNER},
                        request=httpx.Request(method, url),
                    )
                if path == f"/api/study/by/{LEARNER}":
                    url = url.replace(f"/by/{LEARNER}", "/by/learner")
                return super().request(method, url, **kwargs)

        provider = OwnerProvider()
        provider.owner = LEARNER
        provider.timeout_create = provider.timeout_upload = False
        patch.setattr(anonymous, "request", provider.anonymous)
        remote = Remote("fixture-token", LEARNER, provider)
        intent = planning / f"tactical-study-{own_hash}-intent.json"
        publish(
            remote,
            intent,
            {"course": default_export["export"], "course_sha256": own_hash},
            strict=True,
        )
        assert any("Thematic defensive practice" in item["pgn"] for item in provider.uploaded)
        with revalidate_study(path, default_export, own_hash) as check:
            check()
        other = {**default_export["export"], "policy": "independent fixture"}
        other_hash = preview_hash(other)
        other_provider = OwnerProvider()
        other_provider.owner = LEARNER
        other_provider.timeout_create = other_provider.timeout_upload = False
        patch.setattr(anonymous, "request", other_provider.anonymous)
        publish(
            Remote("fixture-token", LEARNER, other_provider),
            planning / f"tactical-study-{other_hash}-intent.json",
            {"course": other, "course_sha256": other_hash},
            strict=True,
        )
        with pytest.raises(ValueError), revalidate_study(path, default_export, own_hash):
            pass
        record_delivery(db, LEARNER, "f" * 64, [(chapter_index, worked)], "download")
        with pytest.raises(ValueError), revalidate_study(path, default_export, own_hash):
            pass
        assert learner_counts == tuple(
            db.connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in (
                "evidence_mappings",
                "evidence_review_events",
                "training_attempts",
                "training_completions",
            )
        )
        before_course = db.connection.total_changes
    with monkeypatch.context() as patch:
        patch.setattr(
            "chess_coach.tactical_course_protection.current",
            lambda *_a, **_k: (_ for _ in ()).throw(ValueError("source changed")),
        )
        with pytest.raises(ValueError):
            tactical_export(db, LEARNER, "test", course, CourseBudget(db))
    assert db.connection.total_changes == before_course
    offer_selected(
        tmp_path,
        path,
        LEARNER,
        selected_path,
        selected_strict_export,
        CourseBudget(db),
        enabled=True,
    )
    learning_tables = (
        "evidence_mappings",
        "evidence_review_events",
        "training_attempts",
        "training_completions",
    )
    before_read = tuple(
        db.connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        for table in learning_tables
    )
    with monkeypatch.context() as reading:
        for module in (objective_protection_snapshot, related_protection_features):
            reading.setattr(module, "probe", no_course_proof)
            reading.setattr(module, "judge", no_course_proof)
        download = selected_client.get(
            f"/coaching/tactical-course?version={selected_hash}&download=1",
            base_url="https://coach.invalid",
            headers=selected_headers,
        )
    assert download.status_code == 200
    assert (
        b"Understand the threatened piece" in download.data
        and b"Practice a defense" in download.data
    )
    assert before_read == tuple(
        db.connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        for table in learning_tables
    )
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
