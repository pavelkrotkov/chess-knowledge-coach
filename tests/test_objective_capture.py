"""Synthetic bounded capture objectives preserve source and event history."""

import json

import chess
import pytest

from chess_coach.evidence_review import review_evidence
from chess_coach.material_detector import process_decision
from chess_coach.objective_capture_contract import GAIN_VERSION, TARGET_VERSION
from chess_coach.objective_capture_judge import judge
from chess_coach.objective_status import inspect
from chess_coach.objective_worker import process
from chess_coach.unified_session_events import hint, show, submit
from chess_coach.unified_sessions import start
from tests.capture_certificate_fixture import certify
from tests.capture_certificate_fixture import project as capture_project
from tests.test_material_pipeline import LEARNER, make_game


def evaluate(board, move, objective="capture_named_target", target="d4"):
    return judge(
        board,
        board.parse_uci(move),
        objective,
        chess.parse_square(target),
        3,
        lambda: 0.0,
        0.0,
        5.0,
        {},
    )


@pytest.mark.parametrize("version", [TARGET_VERSION, GAIN_VERSION])
def test_owned_session_immutable_retry_and_stale_review(tmp_path, monkeypatch, version):
    if version == TARGET_VERSION:
        _daily_capture_workflow(tmp_path, monkeypatch)
        _capture_practice_priority_workflow(tmp_path, monkeypatch)
        _retained_capture_workflow(tmp_path, monkeypatch)
    root, path = capture_project(tmp_path, "capture-project")
    db = make_game(path, monkeypatch)
    evidence = process_decision(db, 1, LEARNER)["evidence_ids"][0]
    certify(db, LEARNER, root)
    state = start(
        db,
        attempt_id="one",
        subject=LEARNER,
        source_type="own-game",
        version=version,
        key=str(evidence),
    )
    assert state["gain_threshold"] == 3
    if version == TARGET_VERSION:
        assert state["objective_target"] == "d4"
    else:
        assert "objective_target" not in state
    before = db.connection.execute("SELECT COUNT(*) FROM mastery_events").fetchone()[0]
    response = submit(db, "one", LEARNER, event_id="move", move="e1f1")
    assert response["feedback"] == "needs_verification"
    frozen = db.connection.execute("SELECT response_json FROM unified_session_events").fetchone()[0]
    assert process(db, LEARNER)["processed"] == 1
    outcome = inspect(db, LEARNER, "one", "move")
    assert outcome["status"] == ("incorrect" if version == TARGET_VERSION else "unresolved")
    assert submit(db, "one", LEARNER, event_id="move", move="e1f1") == response
    assert (
        db.connection.execute("SELECT response_json FROM unified_session_events").fetchone()[0]
        == frozen
    )
    assert db.connection.execute("SELECT COUNT(*) FROM mastery_events").fetchone()[0] == before
    assert show(db, "one", LEARNER)["verification"]["status"] == outcome["status"]
    if version == TARGET_VERSION:
        from chess_coach.unified_session_state import session_row

        for attempt in ("legacy-exemplar", "enrolled-exemplar"):
            start(
                db,
                attempt_id=attempt,
                subject=LEARNER,
                source_type="own-game",
                version=version,
                key=str(evidence),
                training=attempt == "enrolled-exemplar",
            )
        enrolled = session_row(db, "enrolled-exemplar", LEARNER)
        exemplar = json.loads(enrolled["lines_json"])[0][0]
        legacy = submit(db, "legacy-exemplar", LEARNER, event_id="answer", move=exemplar)
        assert legacy["feedback"] == "objective_verified"
        queued = submit(db, "enrolled-exemplar", LEARNER, event_id="answer", move=exemplar)
        assert queued["feedback"] == "needs_verification"
        assert process(db, LEARNER)["outcomes"] == {"correct": 1}
        assert inspect(db, LEARNER, "enrolled-exemplar", "answer")["status"] == "correct"
        learning = show(db, "enrolled-exemplar", LEARNER)["learning"]
        assert learning["outcome"] == "success"
        assert learning["rating"] == "good"
        assert learning["evidence_id"] is not None
        from datetime import UTC, datetime, timedelta

        from chess_coach.curriculum import daily_plan
        from chess_coach.mastery_sources import evidence_rows
        from chess_coach.mastery_training_context import training_context
        from chess_coach.unified_training_complete import complete

        assert complete(db, "enrolled-exemplar", LEARNER, event_id="answer") == {
            key: value for key, value in learning.items() if key != "state"
        }
        candidate = next(
            row
            for row in evidence_rows(db, LEARNER, "hanging_piece", "execute")
            if row["id"] == learning["evidence_id"]
        )
        assert training_context(db, candidate)[0]["attempt_id"] == "enrolled-exemplar"
        from chess_coach.mastery_checks import basic_reason

        assert basic_reason(db, candidate, LEARNER) == "unreviewed_or_invalid_review"
        review_evidence(db, learning["evidence_id"], decision="accept", actor="fixture_reviewer")
        candidate = next(
            row
            for row in evidence_rows(db, LEARNER, "hanging_piece", "execute")
            if row["id"] == learning["evidence_id"]
        )
        assert basic_reason(db, candidate, LEARNER) is None
        plan = daily_plan(
            db,
            subject=LEARNER,
            corpus_version="fixture-v1",
            as_of=datetime.now(UTC) + timedelta(days=2),
        )
        due = next(item for item in plan["items"] if item.get("item_id") == learning["item_id"])
        assert due["source_type"] == "own-game" and due["source_key"] == str(evidence)
        start(
            db,
            attempt_id="due-again",
            subject=LEARNER,
            source_type=due["source_type"],
            version=due["source_version"],
            key=due["source_key"],
            training=True,
            item_id=due["item_id"],
        )
        assert show(db, "due-again", LEARNER)["learning"]["item_id"] == learning["item_id"]
        old_due = learning["due"]
        hint(db, "due-again", LEARNER, event_id="hint")
        submit(db, "due-again", LEARNER, event_id="answer", move=exemplar)
        process(db, LEARNER)
        assisted = show(db, "due-again", LEARNER)["learning"]
        assert assisted["assistance"] == "assisted"
        assert assisted["evidence_id"] is None and assisted["rating"] is None
        assert assisted["due"] == old_due
        start(
            db,
            attempt_id="miss",
            subject=LEARNER,
            source_type="own-game",
            version=version,
            key=str(evidence),
            training=True,
            item_id=learning["item_id"],
        )
        submit(db, "miss", LEARNER, event_id="answer", move="e1f1")
        before_evidence = db.connection.execute(
            "SELECT COUNT(*) FROM evidence_mappings"
        ).fetchone()[0]
        with monkeypatch.context() as patch:

            def fail_review(*args, **kwargs):
                raise ValueError("synthetic scheduling failure")

            patch.setattr(
                "chess_coach.unified_capture_completion.review_item_in_transaction", fail_review
            )
            process(db, LEARNER)
        assert (
            db.connection.execute("SELECT COUNT(*) FROM evidence_mappings").fetchone()[0]
            == before_evidence
        )
        assert show(db, "miss", LEARNER)["learning"]["state"] == "pending"
        missed = complete(db, "miss", LEARNER)
        assert missed["outcome"] == "failure" and missed["rating"] == "again"
        assert complete(db, "miss", LEARNER) == missed
        start(
            db,
            attempt_id="older",
            subject=LEARNER,
            source_type="own-game",
            version=version,
            key=str(evidence),
            training=True,
            item_id=learning["item_id"],
        )
        submit(db, "older", LEARNER, event_id="answer", move="e1f1")
        with monkeypatch.context() as patch:
            patch.setattr(
                "chess_coach.unified_capture_completion.review_item_in_transaction", fail_review
            )
            process(db, LEARNER)
        start(
            db,
            attempt_id="newer",
            subject=LEARNER,
            source_type="own-game",
            version=version,
            key=str(evidence),
            training=True,
            item_id=learning["item_id"],
        )
        submit(db, "newer", LEARNER, event_id="answer", move=exemplar)
        process(db, LEARNER)
        assert show(db, "newer", LEARNER)["learning"]["rating"] == "good"
        assert show(db, "older", LEARNER)["learning"]["state"] == "superseded"
        before_evidence = db.connection.execute(
            "SELECT COUNT(*) FROM evidence_mappings"
        ).fetchone()[0]
        with pytest.raises(ValueError, match="precede"):
            complete(db, "older", LEARNER)
        assert (
            db.connection.execute("SELECT COUNT(*) FROM evidence_mappings").fetchone()[0]
            == before_evidence
        )
        start(
            db,
            attempt_id="unknown",
            subject=LEARNER,
            source_type="own-game",
            version=version,
            key=str(evidence),
            training=True,
            item_id=learning["item_id"],
        )
        submit(db, "unknown", LEARNER, event_id="answer", move=exemplar)
        from chess_coach.objective_verify import unresolved

        process(
            db, LEARNER, verifier=lambda db, request, clock, seconds: unresolved(request, "timeout")
        )
        assert show(db, "unknown", LEARNER)["learning"]["state"] == "unresolved"
        with pytest.raises(ValueError):
            complete(db, "unknown", LEARNER)
        from chess_coach.mate_assessment_events import replay

        event_before = db.connection.execute(
            "SELECT response_json FROM unified_session_events WHERE attempt_id=? AND event_id=?",
            ("enrolled-exemplar", "answer"),
        ).fetchone()[0]
        assert replay(db, session_row(db, "enrolled-exemplar", LEARNER))["outcome"] == "unresolved"
        assert (
            db.connection.execute(
                "SELECT response_json FROM unified_session_events WHERE attempt_id=? AND event_id=?",
                ("enrolled-exemplar", "answer"),
            ).fetchone()[0]
            == event_before
        )
        assert submit(db, "enrolled-exemplar", LEARNER, event_id="answer", move=exemplar) == queued
    review_evidence(db, evidence, decision="reject", actor="fixture_reviewer")
    with pytest.raises(ValueError):
        show(db, "one", LEARNER)
    assert json.loads(frozen)["feedback"] == "needs_verification"

    if version == TARGET_VERSION:
        black_root, black_path = capture_project(tmp_path, "black-capture-project")
        black_db = make_game(black_path, monkeypatch, black=True)
        black_evidence = process_decision(black_db, 1, LEARNER)["evidence_ids"][0]
        certify(black_db, LEARNER, black_root)
        black_state = start(
            black_db,
            attempt_id="black-alternative",
            subject=LEARNER,
            source_type="own-game",
            version=version,
            key=str(black_evidence),
            training=True,
        )
        assert black_state["learner_color"] == "black" and black_state["objective_target"] == "d5"
        black_row = session_row(black_db, "black-alternative", LEARNER)
        black_exemplar = json.loads(black_row["lines_json"])[0][0]
        board = chess.Board(black_row["prompt_fen"])
        alternative = chess.Move.from_uci("a5d5")
        assert black_exemplar == "d8d5" and alternative != chess.Move.from_uci(black_exemplar)
        assert board.piece_at(alternative.from_square) == chess.Piece(chess.ROOK, chess.BLACK)
        assert alternative in board.legal_moves and board.is_capture(alternative)
        queued = submit(
            black_db, "black-alternative", LEARNER, event_id="answer", move=alternative.uci()
        )
        assert queued["feedback"] == "needs_verification"
        assert process(black_db, LEARNER)["outcomes"] == {"correct": 1}
        checked = inspect(black_db, LEARNER, "black-alternative", "answer")
        assert checked["status"] == "correct" and checked["reason"] == "bounded_capture_proved"
        stored_proof = json.loads(
            black_db.connection.execute(
                "SELECT result_json FROM objective_results WHERE attempt_id=? AND event_id=?",
                ("black-alternative", "answer"),
            ).fetchone()[0]
        )
        assert stored_proof["move"] == "a5d5" and stored_proof["proven_gain_floor"] == 3
        black_learning = show(black_db, "black-alternative", LEARNER)["learning"]
        assert black_learning["outcome"] == "success" and black_learning["rating"] == "good"
        assert black_learning["evidence_id"] is not None
        assert (
            black_db.connection.execute(
                "SELECT human_validated FROM evidence_mappings WHERE id=?",
                (black_learning["evidence_id"],),
            ).fetchone()[0]
            == 0
        )
        black_plan = daily_plan(
            black_db,
            subject=LEARNER,
            corpus_version="fixture-v1",
            as_of=datetime.now(UTC) + timedelta(days=2),
        )
        black_due = next(
            item for item in black_plan["items"] if item.get("item_id") == black_learning["item_id"]
        )
        assert black_due["source_version"] == version and black_due["source_key"] == str(
            black_evidence
        )
        start(
            black_db,
            attempt_id="black-due",
            subject=LEARNER,
            source_type=black_due["source_type"],
            version=black_due["source_version"],
            key=black_due["source_key"],
            training=True,
            item_id=black_due["item_id"],
        )
        black_relaunch = show(black_db, "black-due", LEARNER)
        assert black_relaunch["learner_color"] == "black"
        assert black_relaunch["learning"]["item_id"] == black_learning["item_id"]
        black_db.close()


def test_browser_and_cli_resume_show_the_bound_objective(tmp_path, monkeypatch, capsys):
    from argparse import Namespace

    from chess_coach.cli_parser import build_parser
    from chess_coach.cli_unified_practice import handle_show, handle_start
    from chess_coach.web import create_app
    from tests.capture_certificate_fixture import cli as fresh_cli
    from tests.test_unified_sessions import token

    root, path = capture_project(tmp_path, "browser-project")
    db = make_game(path, monkeypatch)
    evidence = process_decision(db, 1, LEARNER)["evidence_ids"][0]
    certify(db, LEARNER, root)
    handle_start(
        db,
        Namespace(
            attempt="cli",
            subject=LEARNER,
            source="own-game",
            version=TARGET_VERSION,
            key=str(evidence),
        ),
    )
    assert json.loads(capsys.readouterr().out)["objective_target"] == "d4"
    handle_show(db, Namespace(attempt="cli", subject=LEARNER))
    assert json.loads(capsys.readouterr().out)["gain_threshold"] == 3

    def cli(command, *arguments, scoped=True, check=True):
        options = [command, "--subject", LEARNER, *arguments]
        if scoped:
            options.extend(["--project-root", str(root)])
        return fresh_cli(path, *options, check=check)

    listed = json.loads(cli("list-own-game-practice").stdout)
    assert any(item["key"].endswith(":" + str(evidence)) for item in listed["candidates"])
    shown_cli = cli("show-unified", "--attempt", "cli")
    assert json.loads(shown_cli.stdout)["objective_target"] == "d4"
    assert cli("show-unified", "--attempt", "cli", scoped=False, check=False).returncode != 0
    hint_cli = cli("hint-unified", "--attempt", "cli", "--event", "cli-hint")
    assert json.loads(hint_cli.stdout)["feedback"] == "hint"
    move_cli = cli("move-unified", "--attempt", "cli", "--event", "cli-move", "--move", "a1a2")
    assert json.loads(move_cli.stdout)["feedback"] == "illegal"
    related_cli = cli("related-captures", "--position", "1", "--corpus", "legacy")
    assert json.loads(related_cli.stdout)["status"] == "corpus unavailable"
    parsed = build_parser().parse_args(
        [
            "start-related-capture",
            "--subject",
            LEARNER,
            "--position",
            "1",
            "--corpus",
            "legacy",
            "--attempt",
            "fixture",
            "--reference",
            "fixture",
            "--project-root",
            str(root),
        ]
    )
    assert parsed.project_root == str(root)
    db.close()
    app = create_app(
        db_path=path,
        project_root=root,
        subject=LEARNER,
        actor="operator",
        corpus="legacy",
        login="fixture",
        origin="https://coach.invalid",
    )
    client = app.test_client()
    headers = {"Tailscale-User-Login": "fixture"}
    library = client.get(
        "/library?family=capture", base_url="https://coach.invalid", headers=headers
    )
    assert library.status_code == 200 and b"Capture the named target" in library.data
    post = client.post(
        "/unified/start",
        base_url="https://coach.invalid",
        headers=headers | {"Origin": "https://coach.invalid"},
        data={
            "csrf": token(library, "csrf"),
            "source_type": "own-game",
            "version": TARGET_VERSION,
            "key": str(evidence),
            "training": "1",
        },
    )
    assert post.status_code == 303
    page = client.get(post.headers["Location"], base_url="https://coach.invalid", headers=headers)
    assert b"Capture the piece on d4" in page.data and b"at least 3 material points" in page.data
    browser_attempt, browser_event = token(page, "attempt"), token(page, "event")
    move = client.post(
        "/unified/move",
        base_url="https://coach.invalid",
        headers=headers | {"Origin": "https://coach.invalid"},
        data={
            "csrf": token(page, "csrf"),
            "attempt": browser_attempt,
            "event": browser_event,
            "move": "e1f1",
        },
    )
    assert move.status_code == 303
    pending = client.get(
        move.headers["Location"], base_url="https://coach.invalid", headers=headers
    )
    assert b"Verification is queued" in pending.data
    from chess_coach.db import Database

    db = Database(path, capture_root=root)
    missing_scope = cli("process-objective-verifications", scoped=False, check=False)
    assert missing_scope.returncode != 0 and "--project-root" in missing_scope.stderr
    assert db.connection.execute("SELECT count(*) FROM objective_results").fetchone()[0] == 0
    processed = json.loads(cli("process-objective-verifications").stdout)
    assert processed["outcomes"] == {"incorrect": 1}
    status = json.loads(
        cli(
            "show-objective-verification",
            f"--attempt={browser_attempt}",
            f"--event={browser_event}",
        ).stdout
    )
    assert status["status"] == "incorrect"
    completion = json.loads(cli("complete-unified-learning", f"--attempt={browser_attempt}").stdout)
    assert completion["outcome"] == "failure"
    item_id = db.connection.execute(
        "SELECT item_id FROM unified_training_enrollments ORDER BY rowid DESC LIMIT 1"
    ).fetchone()[0]
    db.connection.execute(
        "UPDATE training_items SET due='2000-01-01T00:00:00+00:00' WHERE id=?", (item_id,)
    )
    db.connection.commit()
    db.close()
    resumed = client.get(
        move.headers["Location"], base_url="https://coach.invalid", headers=headers
    )
    assert b"This move did not capture the named target" in resumed.data
    assert b"Learning result: failure" in resumed.data and b"unreviewed" in resumed.data
    plan = client.get("/plan", base_url="https://coach.invalid", headers=headers)
    assert plan.status_code == 200 and b"Capture the named target." in plan.data
    assert (f'name="item_id" value="{item_id}"').encode() in plan.data
    again = client.post(
        "/unified/start",
        base_url="https://coach.invalid",
        headers=headers | {"Origin": "https://coach.invalid"},
        data={
            "csrf": token(plan, "csrf"),
            "source_type": "own-game",
            "version": TARGET_VERSION,
            "key": str(evidence),
            "training": "1",
            "item_id": str(item_id),
        },
    )
    assert again.status_code == 303
    again_page = client.get(
        again.headers["Location"], base_url="https://coach.invalid", headers=headers
    )
    assert b"Capture the piece on d4" in again_page.data


@pytest.mark.parametrize("mode", ["correct", "assisted", "incorrect", "unresolved", "tampered"])
def test_unfamiliar_capture_assessment_browser_and_currentness(tmp_path, monkeypatch, mode):
    import re

    from chess_coach.capture_plan_history import latest
    from chess_coach.db import Database
    from chess_coach.unified_session_events import show
    from chess_coach.web import create_app
    from tests.test_unified_sessions import token

    root, path = capture_project(tmp_path, "transfer-project")
    db = make_game(path, monkeypatch)
    # Admit two independently dated games, with the original source checked last.
    import sys

    from chess_coach.ingest import ingest_pgn
    from chess_coach.pipeline_config import PipelineConfig
    from chess_coach.pipeline_inputs import engine_identity, game_input
    from chess_coach.pipeline_work import run_analysis

    pgn = db.connection.execute("SELECT pgn FROM games WHERE id=1").fetchone()[0]
    ingest_pgn(db, pgn.replace("2026.01.01", "2026.01.02"))
    config = PipelineConfig(learner=LEARNER, engine_path=sys.executable, nodes=100)
    assert (
        run_analysis(db, 2, game_input(db, 2), config, engine_identity(sys.executable))["status"]
        == "complete"
    )
    supporting = db.connection.execute(
        "SELECT id FROM positions WHERE game_id=2 ORDER BY ply LIMIT 1"
    ).fetchone()[0]
    assert process_decision(db, supporting, LEARNER)["evidence_ids"]
    evidence = process_decision(db, 1, LEARNER)["evidence_ids"][0]
    certify(db, LEARNER, root)
    db.connection.execute(
        "INSERT INTO puzzle_corpora(version,source,checksum,state) VALUES('capture','fixture','checksum','staging')"
    )
    corpus = db.connection.execute("SELECT id FROM puzzle_corpora").fetchone()[0]
    for file in ("a", "b", "c", "f", "g"):
        board = chess.Board("4k3/8/8/8/3q4/8/8/3RK3 b - - 0 1")
        board.set_piece_at(chess.parse_square(file + "7"), chess.Piece(chess.PAWN, chess.BLACK))
        key = "private-fixture-" + file
        db.connection.execute(
            """INSERT INTO puzzles(puzzle_id,corpus_id,fen,source,solution,rating,rating_deviation,themes_json,objective)
            VALUES(?,?,?,'https://example.invalid',?,1200,80,'["hangingPiece"]','unknown')""",
            (key, corpus, board.fen(), file + "7" + file + "6 d1d4"),
        )
        db.connection.execute(
            "INSERT INTO puzzle_themes VALUES(?,?,'hangingPiece',1200)", (corpus, key)
        )
    if mode == "correct":
        for file in ("d", "e"):
            harder_board = chess.Board("4k3/8/8/8/3q4/8/8/3RK3 b - - 0 1")
            harder_board.set_piece_at(
                chess.parse_square(file + "7"), chess.Piece(chess.PAWN, chess.BLACK)
            )
            db.connection.execute(
                """INSERT INTO puzzles(puzzle_id,corpus_id,fen,source,solution,rating,rating_deviation,themes_json,objective)
                VALUES(?,?,?,'https://example.invalid',?,1400,80,'["hangingPiece"]','unknown')""",
                (
                    "harder-fixture-" + file,
                    corpus,
                    harder_board.fen(),
                    file + "7" + file + "6 d1d4",
                ),
            )
            db.connection.execute(
                "INSERT INTO puzzle_themes VALUES(?,?,'hangingPiece',1400)",
                (corpus, "harder-fixture-" + file),
            )
    no_reset = chess.Board("4k3/8/8/8/3q4/8/8/3RK3 b - - 0 1")
    db.connection.execute(
        """INSERT INTO puzzles(puzzle_id,corpus_id,fen,source,solution,rating,rating_deviation,themes_json,objective)
        VALUES('private-fixture-no-reset',?,?,'https://example.invalid','e8f8 d1d4',1200,80,'["hangingPiece"]','unknown')""",
        (corpus, no_reset.fen()),
    )
    db.connection.execute(
        "INSERT INTO puzzle_themes VALUES(?,?,'hangingPiece',1200)",
        (corpus, "private-fixture-no-reset"),
    )
    if mode == "correct":
        unresolved_board = chess.Board("4k3/3p4/8/4P3/3q4/8/8/3RK3 b - - 0 1")
        db.connection.execute(
            """INSERT INTO puzzles(puzzle_id,corpus_id,fen,source,solution,rating,
            rating_deviation,themes_json,objective)
            VALUES('unresolved-fixture',?,?,'https://example.invalid',
            'd7d5 d1d4',1200,80,'["hangingPiece"]','unknown')""",
            (corpus, unresolved_board.fen()),
        )
        db.connection.execute(
            "INSERT INTO puzzle_themes VALUES(?,'unresolved-fixture','hangingPiece',1200)",
            (corpus,),
        )
    db.connection.execute("UPDATE puzzle_corpora SET state='ready' WHERE id=?", (corpus,))
    db.connection.commit()
    if mode == "correct":
        import hashlib
        import io

        from chess_coach.public_training import import_collection
        from tests.test_public_training import file_set

        known_game = db.connection.execute("SELECT source_id FROM games WHERE id=1").fetchone()[0]
        future = chess.pgn.read_game(io.StringIO(pgn))
        assert future is not None
        future.headers["UTCDate"] = "2026.01.03"
        future_pgn = str(future)
        future_id = hashlib.sha256(future_pgn.encode()).hexdigest()
        public_board = chess.Board("4k3/8/8/7p/3q4/8/8/3RK3 w - - 0 1")
        alternate = chess.Board("4k3/8/7p/8/3q4/8/8/3RK3 w - - 0 1")
        for version, source_url, board in (
            ("fixture-public-a", "https://lichess.org/" + known_game, public_board),
            ("fixture-public-b", "https://lichess.org/" + future_id, public_board),
            ("fixture-public-c", "https://example.invalid/public", alternate),
        ):
            folder = root / version
            folder.mkdir()
            content, manifest, metadata = file_set(
                folder, rows=[("private-fixture-a", board.fen(), "legal_line", ["d1d4"])]
            )
            metadata.update(version=version, source_url=source_url)
            manifest.write_text(json.dumps(metadata))
            assert (
                import_collection(db, content, content, manifest, project_root=root)["accepted"]
                == 1
            )
    # The real worker builds this finite window over several bounded turns.
    import time

    import chess_coach.capture_certificate_refresh as certificate_refresh
    import chess_coach.capture_certificate_worker as certificate_worker
    import chess_coach.related_capture_assessment as candidate_assessment
    import chess_coach.related_capture_features as candidate_features
    from chess_coach.pipeline_lock import pipeline_lock
    from chess_coach.related_capture import preview as prepared_preview
    from chess_coach.related_capture_context import baseline, bounds
    from chess_coach.related_capture_familiar import familiarity
    from chess_coach.related_capture_pool import complete as prepared_window
    from chess_coach.related_capture_pool import load as load_pool
    from chess_coach.related_capture_source import source_for_position

    assert prepared_preview(db, LEARNER, 1, "capture")["status"] == "capture preparation pending"
    lower, upper = bounds(baseline(db, source_for_position(db, LEARNER, 1)))
    familiar_games = familiarity(db, LEARNER)[1]
    original_visit = certificate_worker._visit
    original_owned_proof = certificate_refresh.prove
    original_gain = candidate_features.capture_gain
    original_judge = candidate_assessment.judge
    with monkeypatch.context() as accounting:
        visits, proofs, interruptions, pending_passes = [], [], [], []

        def visit(*args):
            try:
                result = original_visit(*args)
            except TimeoutError:
                visits.append(1)
                raise
            visits.extend([1] * int(result[0]))
            return result

        def owned_proof(*args, **kwargs):
            proofs.append("owned")
            return original_owned_proof(*args, **kwargs)

        def candidate_gain(*args, **kwargs):
            proofs.append("feature")
            if mode == "correct" and not interruptions:
                interruptions.append(True)
                raise TimeoutError("synthetic candidate deadline")
            return original_gain(*args, **kwargs)

        def candidate_judge(*args, **kwargs):
            proofs.append("assessment")
            return original_judge(*args, **kwargs)

        accounting.setattr(certificate_worker, "_visit", visit)
        accounting.setattr(certificate_refresh, "prove", owned_proof)
        accounting.setattr(candidate_features, "capture_gain", candidate_gain)
        accounting.setattr(candidate_assessment, "judge", candidate_judge)
        for _ in range(80):
            visits.clear()
            proofs.clear()
            with pipeline_lock(db.path):
                certificate_worker.run(db, LEARNER, root, time.monotonic() + 5)
            assert len(visits) <= certificate_worker.SCAN
            assert len(proofs) <= certificate_worker.PROOFS
            pool = load_pool(db, root)
            if pool and pool.get("pending_scope") == ["capture", "checksum", lower, upper]:
                pending_passes.append(True)
            if (
                prepared_window(db, root, "capture", lower, upper, LEARNER, familiar_games)
                is not None
            ):
                break
        else:
            pytest.fail("the finite capture window did not finish preparation")

    if mode == "correct":
        assert interruptions and pending_passes
        window = prepared_window(db, root, "capture", lower, upper, LEARNER, familiar_games)
        assert window is not None
        unavailable = [
            entry
            for entry in window["entries"].values()
            if entry.get("reason") == "exchange_unresolved"
        ]
        assert len(unavailable) == 1 and unavailable[0].get("feature") is None
        assert (
            prepared_preview(db, LEARNER, 1, "capture")["excluded"]["qualification_unavailable"]
            == 1
        )

    if mode == "correct":
        from chess_coach.recurrence_snapshot import read_snapshot
        from chess_coach.tactical_course_related import unfamiliar

        with read_snapshot(db):
            course_chapter = unfamiliar(
                db,
                LEARNER,
                "capture",
                {"kind": "capture", "position_id": 1, "evidence_id": evidence},
            )
        assert course_chapter["mode"] == "conceal"
        assert "Pattern-cued unfamiliar worked example" in course_chapter["pgn"]
        assert "Worked example, ungraded" in course_chapter["pgn"]
        with pytest.raises(ValueError, match="differs"):
            unfamiliar(
                db,
                LEARNER,
                "capture",
                {"kind": "capture", "position_id": 1, "evidence_id": evidence + 1},
            )
        import time

        from chess_coach.tactical_course_budget import Budget, PreviewUnavailable
        from chess_coach.tactical_course_resolve import related

        choice = {"kind": "capture", "position_id": 1, "evidence_id": evidence}
        matched, reason = related(db, LEARNER, "capture", choice, Budget(db))
        assert reason is None and matched["mode"] == "conceal"

        def slow_match(*_args, **_kwargs):
            time.sleep(0.05)

        with monkeypatch.context() as patch:
            patch.setattr("chess_coach.tactical_course_budget.SLICE_SECONDS", 0.01)
            patch.setattr("chess_coach.tactical_course_resolve.with_reason", slow_match)
            item, reason = related(
                db,
                LEARNER,
                "capture",
                {"kind": "capture", "position_id": 1, "evidence_id": evidence},
                Budget(db),
            )
        assert item is None and reason == "related matching deferred: time budget"

        def slow_sql(connection_db, *_args, **_kwargs):
            connection_db.connection.execute(
                "WITH RECURSIVE n(x) AS (VALUES(0) UNION ALL SELECT x+1 FROM n WHERE x<100000000) SELECT sum(x) FROM n"
            ).fetchone()

        with monkeypatch.context() as patch:
            patch.setattr("chess_coach.tactical_course_budget.SLICE_SECONDS", 0.01)
            patch.setattr("chess_coach.tactical_course_resolve.with_reason", slow_sql)
            item, reason = related(db, LEARNER, "capture", choice, Budget(db))
        assert item is None and reason == "related matching deferred: time budget"
        assert not db.connection.in_transaction

        def concurrent_slow(*_args):
            import sqlite3

            with sqlite3.connect(path) as other:
                other.execute("UPDATE games SET event=event WHERE id=1")
            time.sleep(0.5)

        with monkeypatch.context() as patch:
            patch.setattr("chess_coach.tactical_course_budget.SLICE_SECONDS", 0.2)
            patch.setattr("chess_coach.tactical_course_resolve.with_reason", concurrent_slow)
            with pytest.raises(PreviewUnavailable, match="changed"):
                related(db, LEARNER, "capture", choice, Budget(db))
    db.close()
    app = create_app(
        db_path=path,
        project_root=root,
        subject=LEARNER,
        actor="operator",
        corpus="capture",
        login="fixture",
        origin="https://coach.invalid",
    )
    client = app.test_client()
    headers = {"Tailscale-User-Login": "fixture"}
    import sqlite3

    from tests.capture_certificate_fixture import cli as fresh_cli

    tables = (
        "unified_sessions",
        "unified_session_events",
        "objective_requests",
        "objective_results",
        "unified_training_enrollments",
        "training_items",
        "mastery_events",
    )

    def learning_rows():
        with sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True) as reader:
            reader.execute("PRAGMA query_only=ON")
            return tuple(
                tuple(reader.execute(f"SELECT * FROM {table} ORDER BY rowid").fetchall())
                for table in tables
            )

    with sqlite3.connect(path) as reader:
        before_gets = tuple(
            reader.execute(f"SELECT count(*) FROM {table}").fetchone()[0] for table in tables
        )

    def forbidden_proof(*_args, **_kwargs):
        raise AssertionError("candidate admission proof ran in a consumer")

    with monkeypatch.context() as guard:
        guard.setattr(candidate_features, "capture_gain", forbidden_proof)
        guard.setattr(candidate_assessment, "judge", forbidden_proof)
        page = client.get(
            "/decisions/1/related-captures", base_url="https://coach.invalid", headers=headers
        )
        assert page.status_code == 200 and b"Check my capture choice" in page.data
        assert b"private-fixture" not in page.data and b"b7b6 d1d4" not in page.data
        if mode == "correct":
            assert b"outside the current capture proof coverage" in page.data
            fresh = Database(path, capture_root=root)
            assert prepared_preview(fresh, LEARNER, 1, "capture")["items"]
            fresh.close()
            command = fresh_cli(
                path,
                "related-captures",
                "--subject",
                LEARNER,
                "--position",
                "1",
                "--corpus",
                "capture",
                "--project-root",
                str(root),
                proof_free_candidates=True,
            )
            assert json.loads(command.stdout)["items"]
    with sqlite3.connect(path) as reader:
        assert before_gets == tuple(
            reader.execute(f"SELECT count(*) FROM {table}").fetchone()[0] for table in tables
        )

    def assessment_page(response):
        from html import unescape

        url = "/decisions/1/related-captures"
        while True:
            html = response.get_data(as_text=True)
            form = next(
                (
                    section
                    for section in re.findall(r"<section>.*?</section>", html, re.DOTALL)
                    if "content rating 1200" in section and 'name="assessment"' in section
                ),
                None,
            )
            if form is not None:
                return response, url, form
            link = re.search(r'href="([^"]*cursor=[^"]+)"', html)
            assert link
            url = unescape(link.group(1))
            with sqlite3.connect(path) as reader:
                before = tuple(
                    reader.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
                    for table in tables
                )
            with monkeypatch.context() as guard:
                guard.setattr(candidate_features, "capture_gain", forbidden_proof)
                guard.setattr(candidate_assessment, "judge", forbidden_proof)
                response = client.get(url, base_url="https://coach.invalid", headers=headers)
            assert response.status_code == 200
            with sqlite3.connect(path) as reader:
                assert before == tuple(
                    reader.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
                    for table in tables
                )

    first_page = page
    page, assessment_url, assessment_form = assessment_page(page)
    match = re.search(r'name="reference" value="([^"]+)"', assessment_form)
    assert match
    reference = match.group(1)
    if mode == "correct":
        from copy import deepcopy

        from chess_coach.related_capture_pool import load as load_pool
        from chess_coach.related_capture_pool import location as pool_location
        from chess_coach.short_mate_trend_store import write as write_pool

        pool_path = pool_location(db, root)
        assert pool_path is not None
        pool = load_pool(db, root)
        assert pool is not None and pool["complete"] is not None
        old_pool = deepcopy(pool)
        pool["prior"] = {
            "building": {
                "scope": ["other-ready-version", "checksum", lower, upper],
                "band": 0,
                "count": 0,
                "last": None,
                "keys": [],
                "limited": False,
                "pending": [],
            },
            "entries": {},
        }
        write_pool(pool_path, pool)
        with monkeypatch.context() as guard:
            guard.setattr(candidate_features, "capture_gain", forbidden_proof)
            guard.setattr(candidate_assessment, "judge", forbidden_proof)
            unchanged = client.get(
                assessment_url, base_url="https://coach.invalid", headers=headers
            )
        assert unchanged.status_code == 200 and reference.encode() in unchanged.data
        pool = deepcopy(old_pool)
        pool["complete"]["limited"] = not pool["complete"]["limited"]
        write_pool(pool_path, pool)
        changed = client.post(
            "/decisions/1/related-captures/start",
            base_url="https://coach.invalid",
            headers=headers | {"Origin": "https://coach.invalid"},
            data={"csrf": token(page, "csrf"), "reference": reference, "assessment": "1"},
        )
        assert changed.status_code == 400
        with sqlite3.connect(path) as reader:
            assert before_gets == tuple(
                reader.execute(f"SELECT count(*) FROM {table}").fetchone()[0] for table in tables
            )
        write_pool(pool_path, old_pool)

    if mode == "correct":
        import base64
        import sqlite3
        from html import unescape
        from urllib.parse import parse_qs, urlparse

        from chess_coach import related_capture_prepared_assessment
        from chess_coach.fact_fingerprint import canonical, digest

        link = re.search(r'href="([^"]*cursor=[^"]+)"', first_page.get_data(as_text=True))
        assert link
        cursor = parse_qs(urlparse(unescape(link.group(1))).query)["cursor"][0]
        _, tag = json.loads(base64.urlsafe_b64decode(cursor))
        from chess_coach.related_capture import preview

        check_db = Database(path, capture_root=root)
        first = preview(check_db, LEARNER, 1, "capture", secret=app.secret_key)
        later = preview(check_db, LEARNER, 1, "capture", cursor, secret=app.secret_key)
        no_reset.push_uci("e8f8")
        no_reset_item = next(
            item for item in first["items"] + later["items"] if item["fen"] == no_reset.fen()
        )
        assert not no_reset_item.get("assessment_available")
        check_db.close()
        assert all(
            reference != digest(canonical([tag, "corpus", "capture", "private-fixture-" + file]))
            for file in ("a", "b", "c", "f", "g")
        )
        original = related_capture_prepared_assessment.assessment

        def racing(*args, **kwargs):
            result = original(*args, **kwargs)
            with sqlite3.connect(path) as other:
                other.execute("UPDATE games SET event=event WHERE id=1")
            return result

        with monkeypatch.context() as patch:
            patch.setattr(related_capture_prepared_assessment, "assessment", racing)
            changed = client.post(
                "/decisions/1/related-captures/start",
                base_url="https://coach.invalid",
                headers=headers | {"Origin": "https://coach.invalid"},
                data={"csrf": token(page, "csrf"), "reference": reference, "assessment": "1"},
            )
            assert changed.status_code == 400
        with sqlite3.connect(path) as check:
            assert check.execute("SELECT count(*) FROM unified_sessions").fetchone()[0] == 0
        with monkeypatch.context() as patch:
            patch.setattr(
                related_capture_prepared_assessment,
                "assessment",
                lambda *args, **kwargs: (_ for _ in ()).throw(ValueError("unresolved")),
            )
            unavailable = client.post(
                "/decisions/1/related-captures/start",
                base_url="https://coach.invalid",
                headers=headers | {"Origin": "https://coach.invalid"},
                data={"csrf": token(page, "csrf"), "reference": reference, "assessment": "1"},
            )
            assert unavailable.status_code == 400
            assert b"capture could not be verified" in unavailable.data
    with monkeypatch.context() as guard:
        guard.setattr(candidate_features, "capture_gain", forbidden_proof)
        guard.setattr(candidate_assessment, "judge", forbidden_proof)
        post = client.post(
            "/decisions/1/related-captures/start",
            base_url="https://coach.invalid",
            headers=headers | {"Origin": "https://coach.invalid"},
            data={
                "csrf": token(page, "csrf"),
                "reference": reference,
                "assessment": "1",
            },
        )
    assert post.status_code == 303
    shown = client.get(post.headers["Location"], base_url="https://coach.invalid", headers=headers)
    assert b"Capture the piece on d4" in shown.data and b"It is your turn as white" in shown.data
    check_db = Database(path, capture_root=root)
    assert latest(check_db, LEARNER, 1, "capture")["status"] == "incomplete"
    admitted = check_db.connection.execute(
        "SELECT provenance_json FROM unified_sessions"
    ).fetchone()[0]
    context = json.loads(admitted)["related_capture"]["assessment"]["context"]
    assert context["content_rating"] == 1200 and context["content_deviation"] == 80
    assert context["corpus_checksum"] == "checksum" and context["mechanism"]["target"]
    check_db.close()
    attempt = token(shown, "attempt")

    def daily_attempt():
        with monkeypatch.context() as patch:
            patch.setattr("chess_coach.web_protection_plan.report", lambda *_: None)
            patch.setattr("chess_coach.web_protection_plan.fork_recommendation", lambda *_: None)
            return client.get("/plan", base_url="https://coach.invalid", headers=headers)

    def focus_page(protection_games=2, *, unavailable=False, capture_unavailable=False):
        from chess_coach.tactical_course_budget import PreviewUnavailable

        protection = {
            "source": {
                "games": protection_games,
                "evidence_id": evidence,
                "review_status": "provisional",
                "color": "white",
                "version": "fixture",
                "key": "fixture",
            },
            "groups": 1,
            "scanned": 2,
            "checked": 1,
            "unavailable": 0,
            "limited": True,
            "partial": True,
        }

        def checked_protection(*_args):
            if unavailable:
                raise PreviewUnavailable()
            return protection

        from chess_coach.capture_plan import choose as actual_choose
        from chess_coach.plan_capture_action import resolve_source as actual_resolve

        def checked_choose(*args, **kwargs):
            result = actual_choose(*args, **kwargs)
            assert result["source"] and result["source"]["games"] == 2
            return {**result, "limited": True}

        with monkeypatch.context() as patch:
            patch.setattr("chess_coach.capture_plan.choose", checked_choose)
            patch.setattr("chess_coach.web_protection_plan.report", checked_protection)

            def checked_capture(*args, **kwargs):
                if capture_unavailable:
                    raise ValueError("replay unavailable")
                return actual_resolve(*args, **kwargs)

            patch.setattr("chess_coach.plan_capture_action.resolve_source", checked_capture)
            return client.get("/plan/next-focus", base_url="https://coach.invalid", headers=headers)

    if mode == "correct":
        assert b"Continue your capture assessment" in daily_attempt().data
        initial_focus = focus_page()
        assert b"Next focus: find captures" in initial_focus.data
        assert b"Some candidates were not checked" in initial_focus.data
        assert b"Additional markers were not inspected" in initial_focus.data
        assert b"Protection has more supporting games" in focus_page(3).data
        unavailable_capture = focus_page(capture_unavailable=True)
        assert b"Next focus: protect a piece" in unavailable_capture.data
        assert b"capture check was unavailable" in unavailable_capture.data
    if mode == "assisted":
        for endpoint in ("/unified/hint", "/unified/reveal"):
            clue = client.post(
                endpoint,
                base_url="https://coach.invalid",
                headers=headers | {"Origin": "https://coach.invalid"},
                data={
                    "csrf": token(shown, "csrf"),
                    "attempt": attempt,
                    "event": token(shown, "event"),
                },
            )
            assert clue.status_code == (200 if endpoint.endswith("reveal") else 303)
            shown = client.get(
                post.headers["Location"], base_url="https://coach.invalid", headers=headers
            )
    move = client.post(
        "/unified/move",
        base_url="https://coach.invalid",
        headers=headers | {"Origin": "https://coach.invalid"},
        data={
            "csrf": token(shown, "csrf"),
            "attempt": attempt,
            "event": token(shown, "event"),
            "move": "e1f1" if mode == "incorrect" else "d1d4",
        },
    )
    assert move.status_code == 303
    pending = client.get(
        move.headers["Location"], base_url="https://coach.invalid", headers=headers
    )
    assert b"Verification is queued" in pending.data
    if mode == "correct":
        assert b"Check your capture assessment status" in daily_attempt().data
    pending_page = client.get("/plan/captures", base_url="https://coach.invalid", headers=headers)
    assert b"awaiting verification" in pending_page.data
    history_page = client.get(
        "/plan/captures/history", base_url="https://coach.invalid", headers=headers
    )
    assert b"1 pending" in history_page.data and b"puzzle rating 1200" in history_page.data
    with monkeypatch.context() as patch:
        patch.setattr(
            "chess_coach.capture_compare_samples.verify",
            lambda *_args: (_ for _ in ()).throw(
                AssertionError("sparse comparison performed proof work")
            ),
        )
        sparse_page = client.get(
            "/plan/captures/comparison", base_url="https://coach.invalid", headers=headers
        )
    assert (
        sparse_page.status_code == 200
        and b"largest group has 1 recorded matches" in sparse_page.data
    )
    assert b"not verified comparison results" in sparse_page.data
    db = Database(path, capture_root=root)
    pending_history = latest(db, LEARNER, 1, "capture")
    assert pending_history["status"] == "pending"
    assert pending_history["hints"] == (2 if mode == "assisted" else 0)
    if mode == "unresolved":
        monkeypatch.setattr(
            "chess_coach.objective_verify_dispatch.verify_capture",
            lambda *args: {**args[7], "status": "unresolved", "reason": "proof_limit"},
        )
    if mode == "tampered":
        from chess_coach import objective_verify_dispatch

        original_verify = objective_verify_dispatch.verify_capture

        def mismatched_move(*args):
            result = original_verify(*args)
            return {**result, "move": "a1a2"}

        monkeypatch.setattr(objective_verify_dispatch, "verify_capture", mismatched_move)
    expected = "correct" if mode in {"correct", "assisted", "tampered"} else mode
    assert process(db, LEARNER)["outcomes"] == {expected: 1}
    result = show(db, attempt, LEARNER)["verification"]
    assert result["status"] == expected
    assert result["assistance"] == ("revealed" if mode == "assisted" else "unassisted")
    history = latest(db, LEARNER, 1, "capture")
    assert history["status"] == ("unavailable" if mode == "tampered" else expected)
    assert latest(db, LEARNER, 1, "different")["status"] == "none"
    assert history["hints"] == (2 if mode == "assisted" else 0)
    focus = focus_page()
    if mode == "correct":
        assert b"Next focus: protect a piece" in focus.data
        assert b"verified correct without assistance" in focus.data
        assert b"Replay the prepared defensive line" in focus.data
        fallback = focus_page(unavailable=True)
        assert b"Next focus: find captures" in fallback.data
        assert b"matching comparison context" in fallback.data
    else:
        assert b"Next focus: find captures" in focus.data
        if mode == "incorrect":
            assert b"missed the target" in focus.data
            assert b"fresh verified assessment" in focus.data
    if mode == "correct":
        import chess_coach.capture_finder_proof as finder_proof
        import chess_coach.related_capture_assessment_context as assessment_context

        original_context = assessment_context.capture
        before = learning_rows()
        with monkeypatch.context() as guard:
            guard.setattr(candidate_features, "capture_gain", forbidden_proof)
            guard.setattr(candidate_assessment, "judge", forbidden_proof)
            guard.setattr(finder_proof, "certificate", forbidden_proof)
            guard.setattr("chess_coach.related_capture_match._prompt", forbidden_proof)
            matched_page = client.get(
                f"/plan/captures/find-verified?attempt={attempt}&position=1",
                base_url="https://coach.invalid",
                headers=headers,
            )
        assert learning_rows() == before
        assert matched_page.status_code == 200
        assert b"passed the bounded capture proof" in matched_page.data
        assert b"same comparison context" in matched_page.data
        from chess_coach.capture_compare_signature import signature
        from chess_coach.fact_fingerprint import canonical
        from chess_coach.related_capture_start import _admit

        form = next(
            form
            for form in re.findall(
                r"<form\b.*?</form>", matched_page.get_data(as_text=True), re.DOTALL
            )
            if 'name="assessment"' in form
        )
        reference_match = re.search(r'name="reference" value="([^"]+)"', form)
        assert reference_match
        matched_reference = reference_match.group(1)
        with monkeypatch.context() as guard:
            guard.setattr(candidate_features, "capture_gain", forbidden_proof)
            guard.setattr(candidate_assessment, "judge", forbidden_proof)
            guard.setattr(finder_proof, "certificate", forbidden_proof)
            admitted_again = _admit(
                db, LEARNER, 1, "capture", matched_reference, app.secret_key, True, finder=True
            )
        assert learning_rows() == before
        next_context = json.loads(canonical(admitted_again[3]["assessment"]["context"]))
        assert signature(next_context, "capture") == signature(context, "capture")

        finder_form = {
            "csrf": token(matched_page, "csrf"),
            "reference": matched_reference,
            "assessment": "1",
            "finder": token(matched_page, "finder"),
        }
        current_pool = load_pool(db, root)
        assert current_pool is not None and current_pool["complete"] is not None
        changed_pool = deepcopy(current_pool)
        changed_pool["complete"]["limited"] = not changed_pool["complete"]["limited"]
        write_pool(pool_path, changed_pool)
        with monkeypatch.context() as guard:
            guard.setattr(candidate_features, "capture_gain", forbidden_proof)
            guard.setattr(candidate_assessment, "judge", forbidden_proof)
            guard.setattr(finder_proof, "certificate", forbidden_proof)
            refused = client.post(
                "/decisions/1/related-captures/start",
                base_url="https://coach.invalid",
                headers=headers | {"Origin": "https://coach.invalid"},
                data=finder_form,
            )
        assert refused.status_code == 400 and learning_rows() == before
        pending_pool = deepcopy(current_pool)
        pending_pool["complete"] = None
        write_pool(pool_path, pending_pool)
        with monkeypatch.context() as guard:
            guard.setattr(candidate_features, "capture_gain", forbidden_proof)
            guard.setattr(candidate_assessment, "judge", forbidden_proof)
            guard.setattr(finder_proof, "certificate", forbidden_proof)
            pending_finder = client.get(
                f"/plan/captures/find-verified?attempt={attempt}&position=1",
                base_url="https://coach.invalid",
                headers=headers,
            )
        assert b"Capture preparation is pending" in pending_finder.data
        assert learning_rows() == before
        write_pool(pool_path, current_pool)
        with monkeypatch.context() as guard:
            guard.setattr(candidate_features, "capture_gain", forbidden_proof)
            guard.setattr(candidate_assessment, "judge", forbidden_proof)
            guard.setattr(finder_proof, "certificate", forbidden_proof)
            second_post = client.post(
                "/decisions/1/related-captures/start",
                base_url="https://coach.invalid",
                headers=headers | {"Origin": "https://coach.invalid"},
                data=finder_form,
            )
        assert second_post.status_code == 303
        second_shown = client.get(
            second_post.headers["Location"], base_url="https://coach.invalid", headers=headers
        )
        second_attempt = token(second_shown, "attempt")
        second_move = client.post(
            "/unified/move",
            base_url="https://coach.invalid",
            headers=headers | {"Origin": "https://coach.invalid"},
            data={
                "csrf": token(second_shown, "csrf"),
                "attempt": second_attempt,
                "event": token(second_shown, "event"),
                "move": "d1d4",
            },
        )
        assert second_move.status_code == 303
        assert process(db, LEARNER)["outcomes"] == {"correct": 1}

        def no_match(*args, **kwargs):
            context = original_context(*args, **kwargs)
            context["content_rating"] += 200
            return context

        with monkeypatch.context() as patch:
            patch.setattr(assessment_context, "capture", no_match)
            patch.setattr(
                finder_proof,
                "certificate",
                lambda *_: (_ for _ in ()).throw(AssertionError("proved a mismatched candidate")),
            )
            empty = client.get(
                f"/plan/captures/find-verified?attempt={attempt}&position=1",
                base_url="https://coach.invalid",
                headers=headers,
            )
        assert b"with the same comparison context" in empty.data
        assert b"Find a verified unfamiliar capture of the same pattern" in empty.data
        assert b"/plan/captures/find-verified?position=1" in empty.data
    else:
        blocked = client.get(
            f"/plan/captures/find-verified?attempt={attempt}&position=1",
            base_url="https://coach.invalid",
            headers=headers,
        )
        assert b"with the same comparison context" in blocked.data
    finished = client.get(
        move.headers["Location"], base_url="https://coach.invalid", headers=headers
    )
    text = {
        "correct": b"bounded capture objective is verified",
        "assisted": b"A continuation was revealed",
        "incorrect": b"This move did not capture the named target",
        "unresolved": b"The move remains ungraded",
        "tampered": b"bounded capture objective is verified",
    }
    assert text[mode] in finished.data
    daily = daily_attempt()
    assert daily.status_code == 200
    assert (
        b"Find a verified unfamiliar capture with matching comparison context" in daily.data
    ) == (mode == "correct")
    assert (b"Find another verified unfamiliar capture of this pattern" in daily.data) == (
        mode == "correct"
    )
    assert (b"find a fresh verified assessment of this pattern" in daily.data) == (
        mode == "incorrect"
    )
    if mode in {"assisted", "unresolved"}:
        assert b"does not advance this recommendation" in daily.data
    if mode == "tampered":
        assert b"latest assessment could not be checked" in daily.data
    adaptive = client.get("/plan/captures", base_url="https://coach.invalid", headers=headers)
    adaptive_text = {
        "correct": b"first move was verified without a hint or reveal",
        "assisted": b"first move was verified with assistance",
        "incorrect": b"checked first move did not capture the named target",
        "unresolved": b"first move remains ungraded",
        "tampered": b"latest assessment could not be checked",
    }
    assert adaptive_text[mode] in adaptive.data
    assert b"View first-encounter capture history" in adaptive.data
    assert b"Capture choices in your games" in adaptive.data
    count_text = {
        "correct": b"2 correct without assistance",
        "assisted": b"1 assisted",
        "incorrect": b"1 incorrect without assistance",
        "unresolved": b"1 ungraded",
        "tampered": b"1 unavailable or stale",
    }
    history_page = client.get(
        "/plan/captures/history", base_url="https://coach.invalid", headers=headers
    )
    assert count_text[mode] in history_page.data
    assert (b"Explore another unfamiliar capture example" in adaptive.data) == (
        mode in {"correct", "incorrect"}
    )
    assert b"Comparisons need more comparable first attempts" in adaptive.data
    assert db.connection.execute("SELECT COUNT(*) FROM training_attempts").fetchone()[0] == 0
    if mode == "correct":
        again = client.get(
            "/decisions/1/related-captures", base_url="https://coach.invalid", headers=headers
        )
        rehearsal = client.post(
            "/decisions/1/related-captures/start",
            base_url="https://coach.invalid",
            headers=headers | {"Origin": "https://coach.invalid"},
            data={"csrf": token(again, "csrf"), "reference": token(again, "reference")},
        )
        assert rehearsal.status_code == 303
        rehearsal_page = client.get(
            rehearsal.headers["Location"], base_url="https://coach.invalid", headers=headers
        )
        assert b"Find a continuation" in rehearsal_page.data
        current_result = latest(db, LEARNER, 1, "capture")
        assert current_result["status"] == "correct"
        event = db.connection.execute(
            "SELECT e.event_id,e.created_at FROM objective_requests r JOIN unified_session_events e "
            "ON e.attempt_id=r.attempt_id AND e.event_id=r.event_id WHERE r.attempt_id=?",
            (current_result["attempt_id"],),
        ).fetchone()
        assert current_result["answered_at"] == event["created_at"]
        import chess_coach.objective_current as capture_current

        prefix = capture_current.prefix

        def changed_prefix(*args):
            events = prefix(*args)
            events[-1]["created_at"] = "2020-01-01T00:00:00+00:00"
            return events

        with monkeypatch.context() as patch:
            patch.setattr(capture_current, "prefix", changed_prefix)
            assert latest(db, LEARNER, 1, "capture")["status"] == "stale"
        # A second unfamiliar prompt shares source checking, while old snapshots
        # without admission context remain descriptive and unranked.
        next_page = client.get(
            "/decisions/1/related-captures", base_url="https://coach.invalid", headers=headers
        )
        next_page, _, next_form = assessment_page(next_page)
        next_match = re.search(r"name=\"reference\" value=\"([^\"]+)\"", next_form)
        assert next_match
        next_ref = next_match.group(1)
        with monkeypatch.context() as patch:
            patch.setattr(
                "chess_coach.related_capture_assessment_context.capture",
                lambda *args: (_ for _ in ()).throw(ValueError()),
            )
            second = client.post(
                "/decisions/1/related-captures/start",
                base_url="https://coach.invalid",
                headers=headers | {"Origin": "https://coach.invalid"},
                data={"csrf": token(next_page, "csrf"), "reference": next_ref, "assessment": "1"},
            )
        assert second.status_code == 303
        import chess_coach.related_capture_source as source_module
        from chess_coach.capture_history_first import report as first_history

        original_source = source_module.source_for_position
        checks = []

        def counted_source(*args, **kwargs):
            checks.append(True)
            return original_source(*args, **kwargs)

        with monkeypatch.context() as patch:
            patch.setattr(source_module, "source_for_position", counted_source)
            assessed = first_history(db, LEARNER, "capture")
        assert assessed["counts"]["unassisted_correct"] == 2
        assert assessed["counts"]["incomplete"] == 1 and len(checks) == 1
        assert {entry["rating"] for entry in assessed["items"]} == {None, 1200}
        from chess_coach.capture_history_first import HistoryDeadline

        checks = []

        def expiring_check():
            checks.append(True)
            if len(checks) == 2:
                raise HistoryDeadline()

        with pytest.raises(HistoryDeadline):
            original_source(db, LEARNER, 1, check=expiring_check)
        assert len(checks) == 2
        with monkeypatch.context() as patch:
            patch.setattr("chess_coach.capture_history_first.SECONDS", 0)
            partial = client.get(
                "/plan/captures/history", base_url="https://coach.invalid", headers=headers
            )
        assert b"Capture assessments in inspected sessions" in partial.data
        assert b"earlier encounters may be missing" in partial.data
        # A second owned source contributes another independently admitted prompt.
        import sys

        from chess import pgn

        from chess_coach.ingest import ingest_pgn
        from chess_coach.pipeline_config import PipelineConfig
        from chess_coach.pipeline_inputs import engine_identity, game_input
        from chess_coach.pipeline_work import run_analysis
        from chess_coach.related_capture import preview as capture_preview
        from chess_coach.related_capture_start import start_related

        new_board = chess.Board("4k3/7p/8/8/3q4/8/8/3RK3 w - - 0 1")
        new_game = pgn.Game()
        new_game.setup(new_board)
        new_game.headers["White"] = LEARNER
        new_game.headers["Black"] = "fixture_opponent"
        new_game.headers["UTCDate"] = "2026.01.02"
        new_game.headers["UTCTime"] = "12:00:00"
        node = new_game.add_variation(new_board.parse_uci("e1f1"))
        new_board.push_uci("e1f1")
        node.add_variation(new_board.parse_uci("e8f8"))
        ingest_pgn(db, str(new_game))
        game_id = db.connection.execute("SELECT MAX(id) FROM games").fetchone()[0]
        position = db.connection.execute(
            "SELECT id FROM positions WHERE game_id=? ORDER BY ply LIMIT 1", (game_id,)
        ).fetchone()[0]
        config = PipelineConfig(learner=LEARNER, engine_path=sys.executable, nodes=100)
        run_analysis(db, game_id, game_input(db, game_id), config, engine_identity(sys.executable))
        assert process_decision(db, position, LEARNER)["evidence_ids"]
        certify(db, LEARNER, root)
        cursor = None
        while True:
            second_source = capture_preview(
                db, LEARNER, position, "capture", cursor, secret=app.secret_key
            )
            reference = next(
                (
                    value["reference"]
                    for value in second_source["items"]
                    if value.get("assessment_available") and value.get("rating") == 1200
                ),
                None,
            )
            if reference is not None:
                break
            cursor = second_source["next_cursor"]
            assert cursor
        start_related(
            db,
            attempt_id="another-source",
            subject=LEARNER,
            position=position,
            corpus_version="capture",
            reference=reference,
            assessment=True,
            secret=app.secret_key,
        )
        across_sources = first_history(db, LEARNER, "capture")
        assert across_sources["counts"]["unassisted_correct"] == 2
        assert across_sources["counts"]["incomplete"] == 2
        # Two synthetic nonoverlapping, matched cohorts exercise the comparison
        # gates without creating or publishing any learner attempts.
        import chess_coach.capture_compare_report as comparison_report
        import chess_coach.capture_compare_select as comparison_select
        import chess_coach.capture_compare_verify as comparison_verify
        from chess_coach.capture_compare_scope import scope as comparison_scope

        original_row = dict(
            db.connection.execute(
                "SELECT * FROM unified_sessions WHERE attempt_id=?", (attempt,)
            ).fetchone()
        )
        # Screen side before same-game deduplication for the harder search.
        from chess_coach.capture_difficulty_binding import options as difficulty_options
        from chess_coach.capture_difficulty_history import _ordered
        from chess_coach.related_capture_rank import rank
        from chess_coach.related_capture_source import source_for_position

        setup = chess.Board("4k3/4p3/8/8/3q4/8/8/3RK3 b - - 0 1")
        shared = {
            "type": "corpus",
            "version": "capture",
            "game": "same-game",
            "opening": None,
            "rating": 1400,
            "rating_deviation": 80,
        }
        pool = [
            dict(shared, key="a", fen=setup.mirror().fen(), solution="e2e3 d8d5"),
            dict(shared, key="z", fen=setup.fen(), solution="e7e6 d1d4"),
        ]
        owned = source_for_position(db, LEARNER, 1)
        assert rank(owned, pool, set(), 1400)[0]["key"] == "a"
        score = difficulty_options({"side": "white", "band": 1400})["score"]
        assert rank(owned, pool, set(), 1400, score=score)[0]["key"] == "z"
        dated = [{"started_at": f"2026-01-01T00:00:0{x}+00:00"} for x in (3, 2, 1)]
        _ordered(dated, dated[2]["started_at"])
        with pytest.raises(ValueError):
            _ordered(dated, dated[1]["started_at"])
        with pytest.raises(ValueError):
            _ordered([dated[0], dated[1], dated[1]], dated[2]["started_at"])

        # Use the two real verified results while isolating this control from
        # unrelated later incomplete fixture attempts.
        import chess_coach.capture_difficulty_history as difficulty_history
        import chess_coach.capture_finder as difficulty_finder
        import chess_coach.capture_finder_search as difficulty_search
        from chess_coach.capture_difficulty import eligible

        pair = [
            dict(
                db.connection.execute(
                    "SELECT * FROM unified_sessions WHERE attempt_id=?", (value,)
                ).fetchone()
            )
            for value in (second_attempt, attempt)
        ]
        with monkeypatch.context() as patch:
            patch.setattr(difficulty_history, "_rows", lambda *_: pair)
            assert eligible(db, LEARNER, "capture", 1, second_attempt)["band"] == 1400
            with pytest.raises(ValueError):
                eligible(db, LEARNER, "capture", 1, attempt)
            patch.setattr(
                difficulty_finder,
                "_groups",
                lambda *_: ({("capture", "v"): [{"position_id": 1}]}, False, 1),
            )
            patch.setattr(
                difficulty_search, "witnesses", lambda *_args, **_kwargs: iter([{"position_id": 1}])
            )
            harder = client.get(
                f"/plan/captures/find-verified?position=1&attempt={second_attempt}&harder=1",
                base_url="https://coach.invalid",
                headers=headers,
            )
            assert b"1400" in harder.data and b"Check my capture choice" in harder.data
            started = client.post(
                "/decisions/1/related-captures/start",
                base_url="https://coach.invalid",
                headers=headers | {"Origin": "https://coach.invalid"},
                data={
                    "csrf": token(harder, "csrf"),
                    "reference": token(harder, "reference"),
                    "assessment": "1",
                    "harder_attempt": second_attempt,
                    "finder": token(harder, "finder"),
                },
            )
            assert started.status_code == 303
            binding = json.loads(
                db.connection.execute(
                    "SELECT provenance_json FROM unified_sessions ORDER BY rowid DESC LIMIT 1"
                ).fetchone()[0]
            )["related_capture"]
            assert binding["progression"]["prior_attempts"] == [attempt, second_attempt]
        synthetic = []
        for index in range(20):
            position_board = chess.Board.empty()
            position_board.set_piece_at(index, chess.Piece(chess.PAWN, chess.WHITE))
            row = dict(
                original_row,
                attempt_id=f"cohort-{index:02}",
                prompt_fen=position_board.fen(),
                started_at=f"2026-01-01T00:00:{index:02}+00:00",
            )
            synthetic.append(row)
        assert comparison_scope(synthetic[0], "capture") is not None
        bad_context = json.loads(synthetic[0]["provenance_json"])
        bad_context["related_capture"]["assessment"]["context"]["same_geometry"] ^= True
        assert (
            comparison_scope(dict(synthetic[0], provenance_json=json.dumps(bad_context)), "capture")
            is None
        )

        def synthetic_item(_db, row, _corpus, _cache, _check):
            number = int(row["attempt_id"].split("-")[-1])
            return {
                "attempt_id": row["attempt_id"],
                "started_at": row["started_at"],
                "answered_at": row["started_at"].replace("+00:00", ".500000+00:00"),
                "status": "correct" if number < 15 else "incorrect",
                "hints": 0,
                "reveals": 0,
            }

        with monkeypatch.context() as patch:
            patch.setattr(comparison_select, "rows", lambda *_args: (synthetic[:19], False))
            patch.setattr(
                "chess_coach.capture_compare_samples.verify",
                lambda *_args: (_ for _ in ()).throw(AssertionError("sparse proof")),
            )
            assert comparison_report.report(db, LEARNER, "capture")["status"] == "sparse"
            duplicate = [
                *synthetic[:19],
                dict(synthetic[19], prompt_fen=synthetic[0]["prompt_fen"]),
            ]
            patch.setattr(comparison_select, "rows", lambda *_args: (duplicate, False))
            assert comparison_report.report(db, LEARNER, "capture")["status"] == "sparse"
            different = json.loads(synthetic[19]["provenance_json"])
            different["related_capture"]["assessment"]["context"]["content_rating"] = 1600
            split = [*synthetic[:19], dict(synthetic[19], provenance_json=json.dumps(different))]
            patch.setattr(comparison_select, "rows", lambda *_args: (split, False))
            assert comparison_report.report(db, LEARNER, "capture")["status"] == "sparse"
        with monkeypatch.context() as patch:
            patch.setattr(comparison_select, "rows", lambda *_args: (synthetic, False))
            patch.setattr(comparison_verify, "item", synthetic_item)
            matched = comparison_report.report(db, LEARNER, "capture")
            assert matched["status"] == "comparable" and matched["checked"] == 20
            assert matched["earlier"]["unassisted"]["verified"] == 10
            assert matched["later"]["unassisted"]["verified"] == 5
            assert matched["later"]["unassisted"]["incorrect"] == 5
            assert matched["earlier"]["end"] < matched["later"]["start"]
            compared_page = client.get(
                "/plan/captures/comparison", base_url="https://coach.invalid", headers=headers
            )
            assert (
                compared_page.status_code == 200 and b"Both matched samples" in compared_page.data
            )
            assert b"10 correct" in compared_page.data and b"5 incorrect" in compared_page.data
            from chess_coach.capture_compare_chronology import answer_end
            from chess_coach.capture_compare_game import relation
            from chess_coach.capture_compare_verify import verify

            entries, complete = verify(db, synthetic, "capture")
            assert complete and answer_end(entries) == "2026-01-01T00:00:19.500000+00:00"
            sample = {
                "games": 20,
                "oldest": "2026-01-02T00:00:00+00:00",
                "newest": "2026-01-03T00:00:00+00:00",
                "complete": True,
                "opportunities": 5,
                "played": 3,
                "other": 2,
                "opportunity_unresolved": 0,
                "unknown": 0,
                "unchecked": 0,
            }
            games = {
                "comparable": True,
                "historical": False,
                "earlier": sample,
                "newer": sample,
                "bounds": {"status": "available"},
            }
            assert relation(matched, games) == "later"
            patch.setattr("chess_coach.capture_compare_game.capture", lambda *_: games)
            page = client.get(
                "/plan/captures/comparison", base_url="https://coach.invalid", headers=headers
            )
            assert b"Both comparable game windows start after" in page.data
            assert b"5 proved opportunities" in page.data
            games["earlier"] = {**sample, "oldest": "2026-01-01T00:00:19.500000+00:00"}
            assert relation(matched, games) == "newer_only"
            page = client.get(
                "/plan/captures/comparison", base_url="https://coach.invalid", headers=headers
            )
            assert b"The more recent game window starts after" in page.data
            assert b"pair is not a fully later comparison" in page.data
            games["newer"] = {**sample, "oldest": "2026-01-01T00:00:19+00:00"}
            assert relation(matched, games) == "overlap"
            assert (
                relation(matched, {**games, "newer": {**sample, "oldest": None}})
                == "dates_unavailable"
            )
            assert (
                answer_end(
                    [
                        {**entry, "answered_at": None} if i == 0 else entry
                        for i, entry in enumerate(entries)
                    ]
                )
                is None
            )
            assert (
                answer_end(
                    [
                        {**entry, "answered_at": entries[9]["answered_at"]} if i == 10 else entry
                        for i, entry in enumerate(entries)
                    ]
                )
                is None
            )
            assert (
                answer_end(
                    [
                        {**entry, "answered_at": entry["started_at"]} if i == 0 else entry
                        for i, entry in enumerate(entries)
                    ]
                )
                is None
            )
            assert relation(matched, {**games, "comparable": False}) == "games_unavailable"
            assert (
                relation(matched, {**games, "earlier": {**sample, "oldest": None}})
                == "dates_unavailable"
            )
            assert (
                relation(matched, {**games, "earlier": {**sample, "unchecked": 1}})
                == "games_incomplete"
            )
            tied = list(synthetic)
            tied[10] = dict(tied[10], started_at=tied[9]["started_at"])
            patch.setattr(comparison_select, "rows", lambda *_args: (tied, False))
            assert comparison_report.report(db, LEARNER, "capture")["status"] == "unavailable"
            patch.setattr(comparison_select, "rows", lambda *_args: (synthetic, False))
            patch.setattr(
                comparison_verify, "item", lambda *args: {**synthetic_item(*args), "hints": 1}
            )
            assert comparison_report.report(db, LEARNER, "capture")["status"] == "unavailable"
            patch.setattr(
                comparison_verify,
                "item",
                lambda *args: {"status": "stale", "started_at": args[1]["started_at"]},
            )
            assert comparison_report.report(db, LEARNER, "capture")["status"] == "unavailable"
            patch.setattr(comparison_verify, "SECONDS", 0)
            assert comparison_report.report(db, LEARNER, "capture")["checked"] == 0
        # The omitted middle record must not tie either selected cutoff.
        board21 = chess.Board.empty()
        board21.set_piece_at(20, chess.Piece(chess.PAWN, chess.WHITE))
        extra = dict(
            synthetic[19],
            attempt_id="cohort-20",
            prompt_fen=board21.fen(),
            started_at="2026-01-01T00:00:20+00:00",
        )
        for tied_index in (9, 11):
            twenty_one = [*synthetic, extra]
            twenty_one[10] = dict(twenty_one[10], started_at=twenty_one[tied_index]["started_at"])
            with monkeypatch.context() as patch:
                patch.setattr(
                    comparison_select, "rows", lambda *_args, rows=twenty_one: (rows, False)
                )
                patch.setattr(
                    "chess_coach.capture_compare_samples.verify",
                    lambda *_args: (_ for _ in ()).throw(AssertionError("tied boundary proof")),
                )
                ambiguous = comparison_report.report(db, LEARNER, "capture")
            assert (
                ambiguous["status"] == "unavailable" and ambiguous["reason"] == "ambiguous_boundary"
            )
            assert ambiguous["checked"] == 0
        with monkeypatch.context() as patch:
            patch.setattr(comparison_select, "rows", lambda *_args: (synthetic, True))
            patch.setattr(
                "chess_coach.capture_compare_samples.verify",
                lambda *_args: (_ for _ in ()).throw(AssertionError("incomplete proof")),
            )
            assert comparison_report.report(db, LEARNER, "capture")["status"] == "incomplete"
        # The opt-in finder uses the already prepared candidates from current sources.
        import chess_coach.capture_finder as finder
        import chess_coach.capture_finder_proof as finder_proof
        import chess_coach.capture_finder_search as finder_search

        filtered = []
        with monkeypatch.context() as patch:
            patch.setattr(
                finder,
                "_groups",
                lambda *_: ({("capture", "v"): [{"position_id": 1}, {"position_id": 2}]}, False, 2),
            )
            patch.setattr(finder, "familiarity", lambda *_: {})
            patch.setattr(finder, "search", lambda *args: filtered.append(args[5]))
            scoped = client.get(
                "/plan/captures/find-verified?position=2",
                base_url="https://coach.invalid",
                headers=headers,
            )
            invalid = client.get(
                "/plan/captures/find-verified?position=9223372036854775808",
                base_url="https://coach.invalid",
                headers=headers,
            )
        assert scoped.status_code == invalid.status_code == 200
        assert filtered == [{("capture", "v"): [{"position_id": 2}]}]

        before_count = db.connection.execute("SELECT COUNT(*) FROM unified_sessions").fetchone()[0]
        before = learning_rows()
        with monkeypatch.context() as guard:
            guard.setattr(candidate_features, "capture_gain", forbidden_proof)
            guard.setattr(candidate_assessment, "judge", forbidden_proof)
            guard.setattr(finder_proof, "certificate", forbidden_proof)
            guard.setattr("chess_coach.related_capture_match._prompt", forbidden_proof)
            found = client.get(
                "/plan/captures/find-verified", base_url="https://coach.invalid", headers=headers
            )
        assert learning_rows() == before
        assert found.status_code == 200 and b"passed the bounded capture proof" in found.data
        assert (
            db.connection.execute("SELECT COUNT(*) FROM unified_sessions").fetchone()[0]
            == before_count
        )
        assert b"private-fixture" not in found.data
        proved_forms = re.findall(r"<form\b.*?</form>", found.get_data(as_text=True), re.DOTALL)
        proved_form = next(form for form in proved_forms if 'name="assessment"' in form)
        form_action = re.search(r"action=\"([^\"]+)\"", proved_form)
        proved_reference = re.search(r"name=\"reference\" value=\"([^\"]+)\"", proved_form)
        assert form_action and proved_reference
        accepted = client.post(
            form_action.group(1),
            base_url="https://coach.invalid",
            headers=headers | {"Origin": "https://coach.invalid"},
            data={
                "csrf": token(found, "csrf"),
                "reference": proved_reference.group(1),
                "assessment": "1",
                "finder": token(found, "finder"),
            },
        )
        assert accepted.status_code == 303
        stale = client.post(
            form_action.group(1),
            base_url="https://coach.invalid",
            headers=headers | {"Origin": "https://coach.invalid"},
            data={
                "csrf": token(found, "csrf"),
                "reference": proved_reference.group(1),
                "assessment": "1",
                "finder": token(found, "finder"),
            },
        )
        assert stale.status_code == 400
        assert (
            db.connection.execute("SELECT COUNT(*) FROM unified_sessions").fetchone()[0]
            == before_count + 1
        )
        with monkeypatch.context() as patch:
            patch.setattr(finder, "SECONDS", 0)
            patch.setattr(finder, "_groups", lambda *_: (_ for _ in ()).throw(AssertionError()))
            empty = client.get(
                "/plan/captures/find-verified", base_url="https://coach.invalid", headers=headers
            )
        assert empty.status_code == 200 and b"bounded search" in empty.data
        # Unsupported sources are skipped and scope uses the original subject.
        seen_subjects = []

        def unsupported_then_empty(_db, subject, position, _corpus, *_args, **_kwargs):
            seen_subjects.append(subject)
            if position == 1:
                raise ValueError("unsupported mechanism")
            return None

        with monkeypatch.context() as patch:
            patch.setattr(
                finder_search,
                "witnesses",
                lambda *_args, **_kwargs: iter([{"position_id": 1}, {"position_id": 2}]),
            )
            patch.setattr(finder_search, "choose", unsupported_then_empty)
            assert (
                finder_search.search(
                    db,
                    "normalized",
                    "MiXeD",
                    "capture",
                    app.secret_key,
                    {},
                    None,
                    1,
                    lambda _: False,
                )
                is None
            )
        assert seen_subjects == ["MiXeD", "MiXeD"]
        # A proof that completes after the cooperative budget is never shown.
        clock = iter((False, False, True))
        with monkeypatch.context() as patch:
            patch.setattr(finder_proof, "setup", lambda *_args: None)
            patch.setattr(finder_proof, "certificate", lambda *_args: None)
            candidate, used = finder_proof.prove(
                db,
                (None, None, None, [{"type": "corpus", "version": "fixture", "key": "fixture"}]),
                1,
                1,
                lambda _: next(clock),
            )
        assert candidate is None and used == 1
        # Setup may consume the remaining budget; do not start a proof then.
        started = []
        clock = iter((False, True))
        with monkeypatch.context() as patch:
            patch.setattr(finder_proof, "setup", lambda *_args: None)
            patch.setattr(finder_proof, "certificate", lambda *_args: started.append(True))
            candidate, used = finder_proof.prove(
                db,
                (None, None, None, [{"type": "corpus", "version": "fixture", "key": "fixture"}]),
                1,
                4,
                lambda _: next(clock),
            )
        assert candidate is None and used == 0 and not started
        # Cheap preflight skips do not consume the proof budget or hide a later candidate.
        candidates = [
            {"type": "corpus", "version": "fixture", "key": str(index)} for index in range(16)
        ]

        def last_only(_db, _version, key):
            if key != "15":
                raise ValueError("unsupported setup")

        with monkeypatch.context() as patch:
            patch.setattr(finder_proof, "setup", last_only)
            patch.setattr(finder_proof, "certificate", lambda *_args: None)
            candidate, used = finder_proof.prove(
                db, (None, None, None, candidates), 1, 12, lambda _: False
            )
        assert candidate["key"] == "15" and used == 1
        proofs = []

        def unresolved(*args):
            proofs.append(True)
            raise ValueError("unresolved")

        with monkeypatch.context() as patch:
            patch.setattr(finder_proof, "setup", lambda *_args: None)
            patch.setattr(finder_proof, "certificate", unresolved)
            candidate, used = finder_proof.prove(
                db, (None, None, None, candidates), 1, 12, lambda _: False
            )
        assert candidate is None and used == 12 and len(proofs) == 12
        proof_quotas = []
        fake_candidate = {
            "type": "corpus",
            "version": "fixture",
            "key": "fixture",
            "prompt_key": " ".join(chess.STARTING_FEN.split()[:4]),
        }

        def per_source(_db, _selection, _deadline, remaining, _expired, *_args, **_kwargs):
            proof_quotas.append(remaining)
            return (None, remaining) if len(proof_quotas) == 1 else (fake_candidate, 1)

        with monkeypatch.context() as patch:
            patch.setattr(
                finder_search,
                "witnesses",
                lambda *_args, **_kwargs: iter([{"position_id": 1}, {"position_id": 2}]),
            )
            patch.setattr(
                finder_search,
                "choose",
                lambda *_args, **_kwargs: (None, None, None, [fake_candidate], None, None),
            )
            patch.setattr(finder_search, "prove", per_source)
            patch.setattr(finder_search, "present", lambda *_args, **_kwargs: {"items": [{}]})
            answer = finder_search.search(
                db,
                LEARNER,
                LEARNER,
                "capture",
                app.secret_key,
                {},
                (set(), set(), None),
                1,
                lambda _: False,
            )
        assert answer[0] == 2 and proof_quotas == [4, 4]
    if mode == "correct":
        from datetime import timedelta

        from chess_coach.capture_history_item import item as history_item
        from chess_coach.course_pgn import chapter as make_chapter
        from chess_coach.mastery_time import parse_utc
        from chess_coach.tactical_exposure_record import record as record_exposure
        from chess_coach.unified_session_state import session_row

        row = session_row(db, attempt, LEARNER)
        actual = history_item(db, row, "capture", {}, lambda: None)
        assert actual["status"] == "correct"
        snapshot = {
            "prompt_fen": row["prompt_fen"],
            "learner_color": row["learner_color"],
            "lines": [" ".join(line) for line in json.loads(row["lines_json"])],
        }
        taught = make_chapter("Synthetic", "Worked example", snapshot, {})
        db.connection.commit()
        record_exposure(db, LEARNER, "a" * 64, [(0, taught)], "served", line=0)
        assert history_item(db, row, "capture", {}, lambda: None)["status"] == "correct"
        answer_time = parse_utc(actual["answered_at"])
        assert answer_time is not None
        before_answer = (answer_time - timedelta(seconds=1)).isoformat()
        record_exposure(db, LEARNER, "b" * 64, [(0, taught)], "served", line=0, when=before_answer)
        withheld = history_item(db, row, "capture", {}, lambda: None)
        assert withheld["status"] == "not_held_out" and withheld["grade"] == "correct"
        assert withheld["eligibility_reason"] == "provided"
        with monkeypatch.context() as patch:
            patch.setattr("chess_coach.capture_plan_history._selected", lambda *_a, **_k: row)
            assert latest(db, LEARNER, 1, "capture")["status"] == "not_held_out"
    if mode == "correct":
        from chess_coach.related_capture import preview as current_preview

        def public_offer(version):
            cursor = None
            while True:
                result = current_preview(db, LEARNER, 1, "capture", cursor, secret=app.secret_key)
                found = next(
                    (
                        item
                        for item in result["items"]
                        if item["type"] == "public" and item["version"] == version
                    ),
                    None,
                )
                if found is not None:
                    return found
                cursor = result["next_cursor"]
                if cursor is None:
                    raise AssertionError("prepared public example unavailable")

        def public_form(version, reference):
            from html import unescape

            url = "/decisions/1/related-captures"
            while True:
                response = client.get(url, base_url="https://coach.invalid", headers=headers)
                assert response.status_code == 200
                html = response.get_data(as_text=True)
                for section in re.findall(r"<section>.*?</section>", html, re.DOTALL):
                    if f"Source: public · version {version}" not in section:
                        continue
                    for form in re.findall(r"<form\b.*?</form>", section, re.DOTALL):
                        if f'name="reference" value="{reference}"' in form:
                            csrf = re.search(r'name="csrf" value="([^"]+)"', form)
                            assert csrf
                            return {"csrf": csrf.group(1), "reference": reference}
                link = re.search(r'href="([^"]*cursor=[^"]+)"', html)
                assert link
                url = unescape(link.group(1))

        def forbidden_prompt(*_args, **_kwargs):
            raise AssertionError("legacy candidate proof ran in ordinary practice")

        from chess_coach import related_capture_preview as preview_module

        actual_familiarity = preview_module.familiarity

        def changed_after_familiarity(*args):
            result = actual_familiarity(*args)
            with sqlite3.connect(path) as other:
                other.execute("UPDATE games SET event=event WHERE id=1")
            return result

        before = learning_rows()
        with monkeypatch.context() as guard:
            guard.setattr(preview_module, "familiarity", changed_after_familiarity)
            guard.setattr(candidate_features, "capture_gain", forbidden_proof)
            guard.setattr(candidate_assessment, "judge", forbidden_proof)
            with pytest.raises(ValueError, match="capture selection changed"):
                current_preview(db, LEARNER, 1, "capture", secret=app.secret_key)
        assert learning_rows() == before

        with monkeypatch.context() as guard:
            guard.setattr(candidate_features, "capture_gain", forbidden_proof)
            guard.setattr(candidate_assessment, "judge", forbidden_proof)
            guard.setattr("chess_coach.related_capture_match._prompt", forbidden_prompt)
            old_public = public_offer("fixture-public-b")
            old_form = public_form("fixture-public-b", old_public["reference"])
        assert learning_rows() == before

        # A newly ingested learner game changes the familiar collection mask.
        ingest_pgn(db, future_pgn)
        before = learning_rows()
        with monkeypatch.context() as guard:
            guard.setattr(candidate_features, "capture_gain", forbidden_proof)
            guard.setattr(candidate_assessment, "judge", forbidden_proof)
            guard.setattr("chess_coach.related_capture_match._prompt", forbidden_prompt)
            refused = client.post(
                "/decisions/1/related-captures/start",
                base_url="https://coach.invalid",
                headers=headers | {"Origin": "https://coach.invalid"},
                data=old_form,
            )
        assert refused.status_code == 400
        assert b"This example changed or the capture could not be verified" in refused.data
        assert learning_rows() == before
        assert current_preview(db, LEARNER, 1, "capture")["status"] == "capture preparation pending"

        familiar_games = familiarity(db, LEARNER)[1]
        for _ in range(80):
            with pipeline_lock(db.path):
                certificate_worker.run(db, LEARNER, root, time.monotonic() + 5)
            if prepared_window(db, root, "capture", lower, upper, LEARNER, familiar_games):
                break
        else:
            pytest.fail("the shifted public window did not finish preparation")

        before = learning_rows()
        with monkeypatch.context() as guard:
            guard.setattr(candidate_features, "capture_gain", forbidden_proof)
            guard.setattr(candidate_assessment, "judge", forbidden_proof)
            guard.setattr("chess_coach.related_capture_match._prompt", forbidden_prompt)
            public = public_offer("fixture-public-c")
            fresh_form = public_form("fixture-public-c", public["reference"])
            cli_cursor = None
            while True:
                extra = [f"--cursor={cli_cursor}"] if cli_cursor else []
                command = fresh_cli(
                    path,
                    "related-captures",
                    "--subject",
                    LEARNER,
                    "--position",
                    "1",
                    "--corpus",
                    "capture",
                    "--project-root",
                    str(root),
                    *extra,
                    proof_free_candidates=True,
                )
                cli_page = json.loads(command.stdout)
                if any(
                    item["type"] == "public" and item["version"] == "fixture-public-c"
                    for item in cli_page["items"]
                ):
                    break
                cli_cursor = cli_page["next_cursor"]
                assert cli_cursor is not None
        assert learning_rows() == before and not public.get("assessment_available")
        with monkeypatch.context() as guard:
            guard.setattr(candidate_features, "capture_gain", forbidden_proof)
            guard.setattr(candidate_assessment, "judge", forbidden_proof)
            guard.setattr("chess_coach.related_capture_match._prompt", forbidden_prompt)
            public_started = client.post(
                "/decisions/1/related-captures/start",
                base_url="https://coach.invalid",
                headers=headers | {"Origin": "https://coach.invalid"},
                data=fresh_form,
            )
        assert public_started.status_code == 303
        row = db.connection.execute(
            "SELECT source_type,source_version,objective FROM unified_sessions ORDER BY rowid DESC LIMIT 1"
        ).fetchone()
        assert tuple(row) == ("public", "fixture-public-c", "legal_line")

    review_evidence(db, evidence, decision="reject", actor="reviewer")
    with pytest.raises(ValueError):
        show(db, attempt, LEARNER)
    assert latest(db, LEARNER, 1, "capture")["status"] == "stale"
    from chess_coach.capture_history_first import report as first_report

    expected_stale = (
        4 + int(form_action.group(1).startswith("/decisions/1/")) if mode == "correct" else 1
    )
    assert first_report(db, LEARNER, "capture")["counts"]["stale"] == expected_stale
    if mode == "correct":
        for index in range(101):
            db.connection.execute(
                """INSERT INTO unified_sessions
                (attempt_id,subject,source_type,source_version,source_key,snapshot_hash,prompt_fen,
                 learner_color,objective,lines_json,provenance_json,current_fen,candidates_json,
                 next_index,status,started_at)
                VALUES(?,?,'public','fixture','fixture','fixture',?,'white','legal_line',
                       '[]','{}',?,'[]',0,'active','9999-01-01T00:00:00+00:00')""",
                (f"unrelated-{index:03}", LEARNER, chess.STARTING_FEN, chess.STARTING_FEN),
            )
        db.connection.commit()
        limited = latest(db, LEARNER, 1, "capture")
        assert limited["status"] == "none" and limited["limited"]
    db.close()


def test_capture_plan_uses_independent_current_sources_and_is_lazy(tmp_path, monkeypatch):
    import sys

    import chess.pgn

    from chess_coach.capture_plan import report
    from chess_coach.ingest import ingest_pgn
    from chess_coach.pipeline_config import PipelineConfig
    from chess_coach.pipeline_inputs import engine_identity, game_input
    from chess_coach.pipeline_work import run_analysis
    from chess_coach.web import create_app

    root, path = capture_project(tmp_path, "capture-plan-project")
    db = make_game(path, monkeypatch)
    first = process_decision(db, 1, LEARNER)["evidence_ids"][0]
    certify(db, LEARNER, root)
    from chess_coach.capture_plan_sources import _groups
    from chess_coach.tactical_course_budget import PreviewUnavailable

    checkpoints = []

    def deadline():
        checkpoints.append(True)
        if len(checkpoints) == 2:
            raise PreviewUnavailable("deadline")

    with pytest.raises(PreviewUnavailable):
        _groups(db, LEARNER, check=deadline)
    assert len(checkpoints) == 2
    initial = report(db, LEARNER, "legacy")
    assert initial["source"]["games"] == 1 and initial["history"]["status"] == "none"
    # A full history still shows the newest distinct first encounters.
    import chess_coach.capture_history_select as history_selection

    samples = []
    for index, square in enumerate(chess.SQUARES[:10]):
        board = chess.Board.empty()
        board.set_piece_at(square, chess.Piece(chess.PAWN, chess.WHITE))
        samples.append(
            {
                "attempt_id": str(index),
                "started_at": "2026-01-01T00:00:00+00:00",
                "prompt_fen": board.fen(),
            }
        )
    samples.append(dict(samples[0]))
    with monkeypatch.context() as patch:
        patch.setattr(history_selection, "rows", lambda *_: (samples, False))
        patch.setattr(history_selection, "is_source", lambda _: True)
        recent, limited = history_selection.select(db, LEARNER)
    assert limited and [row["attempt_id"] for row in recent] == [
        str(index) for index in range(2, 10)
    ]
    before = db.connection.total_changes
    operations = []
    db.connection.set_trace_callback(lambda sql: operations.append(sql.split(None, 1)[0].upper()))
    assert report(db, LEARNER, "legacy")["source"]["games"] == 1
    db.connection.set_trace_callback(None)
    assert not {"BEGIN", "SAVEPOINT"} & set(operations)
    assert db.connection.total_changes == before

    app = create_app(
        db_path=path,
        project_root=root,
        subject=LEARNER,
        actor="operator",
        corpus="legacy",
        login="fixture",
        origin="https://coach.invalid",
    )
    client = app.test_client()
    headers = {"Tailscale-User-Login": "fixture"}
    with monkeypatch.context() as patch:

        def forbidden(*args, **kwargs):
            raise AssertionError("capture analysis ran on the daily plan")

        patch.setattr("chess_coach.capture_finder.find", forbidden)
        plan = client.get("/plan", base_url="https://coach.invalid", headers=headers)
    assert plan.status_code == 200 and b"/plan/captures" in plan.data
    assert b"<h3>Capture practice</h3>" not in plan.data
    with monkeypatch.context() as patch:
        patch.setattr("chess_coach.capture_plan.report", forbidden)
        patch.setattr(
            "chess_coach.web_views.daily_plan",
            lambda *_args, **_kwargs: {
                "items": [],
                "evidence": {"state": "fixture"},
                "corpus_status": "fixture",
                "diagnostic": None,
                "next_cursor": None,
            },
        )
        continuation = client.get(
            "/plan?cursor=next", base_url="https://coach.invalid", headers=headers
        )
    assert continuation.status_code == 200 and b"<h3>Capture practice</h3>" not in continuation.data
    assert b"Practice protecting a piece" not in continuation.data
    with monkeypatch.context() as patch:
        patch.setattr("chess_coach.capture_finder.find", forbidden)
        single = client.get("/plan/captures", base_url="https://coach.invalid", headers=headers)
    assert b"Find a verified unfamiliar capture" in single.data
    assert single.status_code == 200 and b"single game does not establish recurrence" in single.data
    assert b"No certified assessment in the active corpus for this source" in single.data

    board = chess.Board("4k3/7p/8/8/3q4/8/8/3RK3 w - - 0 1")
    game = chess.pgn.Game()
    game.setup(board)
    game.headers["White"] = LEARNER
    game.headers["Black"] = "fixture_opponent"
    game.headers["Result"] = "*"
    game.headers["UTCDate"] = "2026.01.01"
    game.headers["UTCTime"] = "12:01:00"
    node = game.add_variation(board.parse_uci("e1f1"))
    board.push_uci("e1f1")
    node.add_variation(board.parse_uci("e8f8"))
    config = PipelineConfig(learner=LEARNER, engine_path=sys.executable, nodes=100)
    new_evidence = []
    for _ in range(2):
        ingest_pgn(db, str(game))
        game_id = db.connection.execute("SELECT MAX(id) FROM games").fetchone()[0]
        position = db.connection.execute(
            "SELECT id FROM positions WHERE game_id=? ORDER BY ply LIMIT 1", (game_id,)
        ).fetchone()[0]
        assert (
            run_analysis(
                db, game_id, game_input(db, game_id), config, engine_identity(sys.executable)
            )["status"]
            == "complete"
        )
        new_evidence.append(process_decision(db, position, LEARNER)["evidence_ids"][0])
    certify(db, LEARNER, root)

    from chess_coach.recurrence_cursor import MAX_ID
    from chess_coach.recurrence_sources import evidence as recurrence_evidence

    bounded, truncated = recurrence_evidence(
        db, LEARNER, "hanging_piece", "execute", MAX_ID, failure_only=True, limit=1
    )
    assert len(bounded) == 1 and truncated
    repeated = report(db, LEARNER, "legacy")
    assert repeated["source"]["games"] == 2
    assert repeated["source"]["observations"] == 2
    import chess_coach.curriculum_capture_choice as capture_choice

    original_candidates = capture_choice.candidates
    calls = []

    def counted(*args, **kwargs):
        calls.append(True)
        return original_candidates(*args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr("chess_coach.capture_finder.find", forbidden)
        patch.setattr(capture_choice, "candidates", counted)
        daily = client.get("/plan", base_url="https://coach.invalid", headers=headers)
    assert calls == [True]
    assert b"<h3>Capture practice</h3>" in daily.data
    assert b"Replay the prepared capture" in daily.data
    assert f'name="key" value="{repeated["source"]["key"]}"'.encode() in daily.data
    assert b"Find a verified unfamiliar capture" in daily.data
    assert b"Compare matched capture assessments" in daily.data
    with monkeypatch.context() as patch:
        patch.setattr(
            "chess_coach.web_protection_plan.report",
            lambda *_args: (_ for _ in ()).throw(ValueError("unavailable")),
        )
        first_focus = client.get(
            "/plan/next-focus", base_url="https://coach.invalid", headers=headers
        )
    assert b"Next focus: find captures" in first_focus.data
    assert (
        f"/plan/captures/find-verified?position={repeated['source']['position_id']}".encode()
        in first_focus.data
    )
    assert b"protection check was unavailable" in first_focus.data
    assert b"Replay the prepared capture from this game" in first_focus.data
    assert b"separate from a verified unfamiliar assessment" in first_focus.data
    from tests.test_unified_sessions import token

    replay_data = {
        "csrf": token(first_focus, "csrf"),
        "source_type": token(first_focus, "source_type"),
        "version": token(first_focus, "version"),
        "key": token(first_focus, "key"),
    }
    assert replay_data["key"] == repeated["source"]["key"]
    assert replay_data["version"] == repeated["source"]["version"]
    replay = client.post(
        "/unified/start",
        base_url="https://coach.invalid",
        headers=headers | {"Origin": "https://coach.invalid"},
        data=replay_data,
    )
    assert replay.status_code == 303
    replay_page = client.get(
        replay.headers["Location"], base_url="https://coach.invalid", headers=headers
    )
    assert b"one supplied continuation" in replay_page.data
    replay_row = db.connection.execute(
        "SELECT source_key, objective, provenance_json FROM unified_sessions"
    ).fetchone()
    assert replay_row["source_key"] == repeated["source"]["key"]
    assert replay_row["objective"] == "material_capture"
    assert (
        json.loads(replay_row["provenance_json"])["evidence_id"]
        == repeated["source"]["evidence_id"]
    )
    with monkeypatch.context() as patch:
        patch.setattr(
            "chess_coach.web_views.daily_plan",
            lambda *_args, **_kwargs: {
                "items": [
                    {
                        "objective": "Fixture scheduled review",
                        "kind": "review",
                        "reason": "",
                        "due": None,
                        "corpus_version": "legacy",
                        "puzzle_id": "fixture",
                    },
                    {
                        "objective": "Fixture new puzzle",
                        "kind": "new",
                        "reason": "",
                        "due": None,
                        "corpus_version": "legacy",
                        "puzzle_id": "new-fixture",
                    },
                ],
                "scan": {"due_incomplete": False},
                "evidence": {"state": "fixture"},
                "corpus_status": "fixture",
                "diagnostic": None,
                "next_cursor": "fixture-cursor",
                "continuation_reason": "corpus_scan_incomplete",
            },
        )
        scheduled = client.get("/plan", base_url="https://coach.invalid", headers=headers)
    assert scheduled.data.index(b"Fixture scheduled review") < scheduled.data.index(
        b"<h3>Capture practice</h3>"
    )
    assert scheduled.data.index(b"Fixture scheduled review") < scheduled.data.index(
        b"Check your next non-mate practice focus"
    )
    assert scheduled.data.index(b"<h3>Capture practice</h3>") < scheduled.data.index(
        b"Fixture new puzzle"
    )
    assert scheduled.data.count(b"<h3>Capture practice</h3>") == 1
    assert b"cursor=fixture-cursor" in scheduled.data
    assert b"Check your next non-mate practice focus" not in continuation.data

    # Incomplete or full due coverage never triggers the added source check.
    from chess_coach.plan_page_focus import room_after_due as _room_after_due

    due = {
        "objective": "Due",
        "kind": "due",
        "reason": "",
        "due": None,
        "corpus_version": "legacy",
        "puzzle_id": "fixture",
    }
    assert not _room_after_due({"scan": {"due_incomplete": True}, "items": [due]})
    assert not _room_after_due({"scan": {"due_incomplete": False}, "items": [due] * 10})
    with monkeypatch.context() as patch:
        patch.setattr("chess_coach.plan_page.current_focus", forbidden)
        for result in (
            {"scan": {"due_incomplete": True}, "items": [due]},
            {"scan": {"due_incomplete": False}, "items": [due] * 10},
        ):
            page_data = {
                **result,
                "evidence": {"state": "fixture"},
                "corpus_status": "fixture",
                "diagnostic": None,
                "next_cursor": None,
            }
            patch.setattr(
                "chess_coach.web_views.daily_plan", lambda *_, page_data=page_data, **_k: page_data
            )
            page = client.get("/plan", base_url="https://coach.invalid", headers=headers)
            assert page.status_code == 200 and b"<h3>Capture practice</h3>" not in page.data
    from chess_coach.tactical_course_budget import PreviewUnavailable

    with monkeypatch.context() as patch:
        patch.setattr(
            "chess_coach.curriculum_capture_choice.candidates",
            lambda *_, **_kwargs: (_ for _ in ()).throw(PreviewUnavailable()),
        )
        timed_out = client.get("/plan", base_url="https://coach.invalid", headers=headers)
    assert timed_out.status_code == 200 and b"<h3>Capture practice</h3>" not in timed_out.data
    with monkeypatch.context() as patch:
        patch.setattr(
            "chess_coach.curriculum_capture_choice.candidates",
            lambda *_: (_ for _ in ()).throw(ValueError()),
        )
        fallback = client.get("/plan", base_url="https://coach.invalid", headers=headers)
    assert fallback.status_code == 200 and b"<h3>Capture practice</h3>" not in fallback.data
    page = client.get("/plan/captures", base_url="https://coach.invalid", headers=headers)
    assert b"across 2 independent games" in page.data
    assert b"detector was not rerun" in page.data
    linked = client.get(
        f"/decisions/{repeated['source']['position_id']}/related-captures",
        base_url="https://coach.invalid",
        headers=headers,
    )
    assert linked.status_code == 200
    for evidence_id in new_evidence:
        review_evidence(db, evidence_id, decision="reject", actor="reviewer")
    assert report(db, LEARNER, "legacy")["source"]["games"] == 1
    review_evidence(db, first, decision="reject", actor="reviewer")
    assert report(db, LEARNER, "legacy")["source"] is None
    stale_replay = client.post(
        "/unified/start",
        base_url="https://coach.invalid",
        headers=headers | {"Origin": "https://coach.invalid"},
        data=replay_data,
    )
    assert stale_replay.status_code == 400
    assert db.connection.execute("SELECT count(*) FROM unified_sessions").fetchone()[0] == 1
    db.close()


def _daily_capture_workflow(tmp_path, monkeypatch):
    import sys
    from datetime import UTC, datetime, timedelta

    from chess_coach.curriculum import daily_plan
    from chess_coach.curriculum_cursor import new_state
    from chess_coach.curriculum_cursor_codec import decode_cursor, encode_cursor
    from chess_coach.ingest import ingest_pgn
    from chess_coach.pipeline_config import PipelineConfig
    from chess_coach.pipeline_inputs import engine_identity, game_input
    from chess_coach.pipeline_work import run_analysis
    from chess_coach.training import create_training_item, review_item
    from chess_coach.web import create_app
    from tests.test_unified_sessions import token

    root, path = capture_project(tmp_path, "daily-capture-project")
    db = make_game(path, monkeypatch)
    evidence = process_decision(db, 1, LEARNER)["evidence_ids"][0]
    cold = daily_plan(db, subject=LEARNER, corpus_version="plan-fixture")
    assert cold["capture_status"] == "no_source"
    assert all(item["skill"] != "hanging_piece" for item in cold["items"])
    pgn = db.connection.execute("SELECT pgn FROM games WHERE id=1").fetchone()[0]
    ingest_pgn(db, pgn.replace("2026.01.01", "2026.01.02"))
    config = PipelineConfig(learner=LEARNER, engine_path=sys.executable, nodes=100)
    assert (
        run_analysis(db, 2, game_input(db, 2), config, engine_identity(sys.executable))["status"]
        == "complete"
    )
    second = db.connection.execute(
        "SELECT id FROM positions WHERE game_id=2 ORDER BY ply LIMIT 1"
    ).fetchone()[0]
    process_decision(db, second, LEARNER)
    certify(db, LEARNER, root)

    corpus = db.connection.execute(
        "INSERT INTO puzzle_corpora(version,source,checksum,state) "
        "VALUES('plan-fixture','fixture','checksum','staging')"
    ).lastrowid
    db.connection.executemany(
        """INSERT INTO puzzles(puzzle_id,corpus_id,fen,source,solution,rating,
        rating_deviation,themes_json,objective) VALUES(?,?,?,'fixture',?,1200,80,'[]','unknown')""",
        [
            (name, corpus, "7k/1p6/6K1/2Q5/8/8/8/8 b - - 17 14", "b7b6 c5f8")
            for name in ("first", "second")
        ],
    )
    db.connection.execute("UPDATE puzzle_corpora SET state='ready' WHERE id=?", (corpus,))
    db.connection.commit()
    now = datetime.now(UTC)
    now -= timedelta(days=now.date().toordinal() % 4)
    for name in ("first", "second"):
        item = create_training_item(
            db,
            source_type="puzzle",
            source_ref=json.dumps(["plan-fixture", name]),
            skill="mate_in_one",
            operation="execute",
        )
        review_item(db, item, "good", reviewed_at=now)
    before = db.connection.total_changes
    initial = daily_plan(
        db, subject=LEARNER, corpus_version="plan-fixture", limit=5, scan_limit=1, as_of=now
    )
    assert initial["capture_status"] == "deferred" and initial["next_cursor"]
    state = decode_cursor(db, initial["next_cursor"])
    assert state["v"] == 8 and state["phase"] == "capture"
    assert len(state["capture_pending"]) == 64
    assert "fixture_learner" not in initial["next_cursor"]
    assert db.connection.total_changes == before
    from chess_coach.curriculum_canonical_cursor import fields as canonical_fields
    from chess_coach.curriculum_public_cursor import fields as public_fields

    legacy_state = {
        key: value
        for key, value in state.items()
        if key not in {"priority_policy", "priority_goal", "priority"}
    }
    v2 = dict(legacy_state)
    for field in (*public_fields(), *canonical_fields()):
        del v2[field]
    v2["v"] = 2
    for field in (
        "fork_pending",
        "family_turn",
        "family_index",
        "prerequisite_policy",
        "prerequisite_graph",
        "prerequisite_scope",
        "prerequisite_checked",
        "prerequisite_offered",
        "prerequisite_deferred",
    ):
        del v2[field]
    legacy_v2 = daily_plan(
        db,
        subject=LEARNER,
        corpus_version="plan-fixture",
        limit=5,
        scan_limit=1,
        as_of=now,
        cursor=encode_cursor(db, v2),
    )
    assert any(item["skill"] == "hanging_piece" for item in legacy_v2["items"])
    db.connection.execute("BEGIN")
    review_evidence(db, evidence, decision="accept", actor="fixture")
    with pytest.raises(ValueError, match="sources changed"):
        daily_plan(
            db,
            subject=LEARNER,
            corpus_version="plan-fixture",
            limit=5,
            scan_limit=1,
            as_of=now,
            cursor=initial["next_cursor"],
        )
    db.connection.rollback()
    before = db.connection.total_changes
    continuation = daily_plan(
        db,
        subject=LEARNER,
        corpus_version="plan-fixture",
        limit=5,
        scan_limit=1,
        as_of=now,
        cursor=initial["next_cursor"],
    )
    capture = next(item for item in continuation["items"] if item["skill"] == "hanging_piece")
    assert capture["kind"] == "new" and capture["source_version"] == TARGET_VERSION
    assert capture["source_review"] == "unreviewed" and capture["independent_games"] == 2
    assert "Provisional diagnostic" in capture["reason"] and "mastery" in capture["reason"]
    assert db.connection.total_changes == before

    v1 = new_state(db, LEARNER, "plan-fixture", 5, 1, now)
    for field in (*public_fields(), *canonical_fields()):
        del v1[field]
    v1["v"] = 1
    for field in (
        "capture_pending",
        "fork_pending",
        "family_turn",
        "family_index",
        "prerequisite_policy",
        "prerequisite_graph",
        "prerequisite_scope",
        "prerequisite_checked",
        "prerequisite_offered",
        "prerequisite_deferred",
    ):
        del v1[field]
    v1["phase"] = "new"
    legacy = daily_plan(
        db,
        subject=LEARNER,
        corpus_version="plan-fixture",
        limit=5,
        scan_limit=1,
        as_of=now,
        cursor=encode_cursor(db, v1),
    )
    assert all(item["skill"] != "hanging_piece" for item in legacy["items"])
    v3 = dict(legacy_state)
    for field in (*public_fields(), *canonical_fields()):
        del v3[field]
    v3["v"] = 3
    for field in (
        "prerequisite_policy",
        "prerequisite_graph",
        "prerequisite_scope",
        "prerequisite_checked",
        "prerequisite_offered",
        "prerequisite_deferred",
    ):
        del v3[field]
    legacy_v3 = daily_plan(
        db,
        subject=LEARNER,
        corpus_version="plan-fixture",
        limit=5,
        scan_limit=1,
        as_of=now,
        cursor=encode_cursor(db, v3),
    )
    assert any(item["skill"] == "hanging_piece" for item in legacy_v3["items"])

    app = create_app(
        db_path=path,
        project_root=root,
        subject=LEARNER,
        actor="fixture",
        corpus="plan-fixture",
        login="login",
        origin="https://coach.invalid",
    )
    client = app.test_client()
    assert client.get("/plan", base_url="https://coach.invalid").status_code == 403
    page = client.get(
        "/plan", base_url="https://coach.invalid", headers={"Tailscale-User-Login": "login"}
    )
    assert page.status_code == 200
    assert page.data.count(b"<h3>Capture practice</h3>") == 1
    form = page.data.split(b"Capture the queen on d4.", 1)[1].split(b"</form>", 1)[0]
    assert b'name="training" value="1"' in form and b'name="item_id"' not in form
    csrf = token(page, "csrf")
    response = client.post(
        "/unified/start",
        base_url="https://coach.invalid",
        headers={"Tailscale-User-Login": "login", "Origin": "https://coach.invalid"},
        data={
            "csrf": csrf,
            "source_type": "own-game",
            "version": capture["source_version"],
            "key": capture["source_key"],
            "training": "1",
        },
    )
    assert response.status_code == 303
    attempt = response.headers["Location"].rstrip("/").rsplit("/", 1)[-1]
    state = show(db, attempt, LEARNER)
    item_id = state["learning"]["item_id"]
    exemplar = db.connection.execute(
        "SELECT lines_json FROM unified_sessions WHERE attempt_id=?", (attempt,)
    ).fetchone()[0]
    submit(db, attempt, LEARNER, event_id="answer", move=json.loads(exemplar)[0][0])
    process(db, LEARNER)
    assert show(db, attempt, LEARNER)["learning"]["item_id"] == item_id
    already = daily_plan(db, subject=LEARNER, corpus_version="plan-fixture")
    assert already["capture_status"] == "already_scheduled"
    assert not any(
        item["kind"] == "new" and item["prompt_key"] == capture["prompt_key"]
        for item in already["items"]
    )
    due_plan = daily_plan(
        db,
        subject=LEARNER,
        corpus_version="plan-fixture",
        limit=1,
        as_of=datetime.now(UTC) + timedelta(days=2),
    )
    assert due_plan["items"] and due_plan["items"][0]["kind"] == "due"
    assert all(item["kind"] != "new" for item in due_plan["items"])
    again = daily_plan(
        db,
        subject=LEARNER,
        corpus_version="plan-fixture",
        as_of=datetime.now(UTC) + timedelta(days=2),
    )
    assert any(item.get("item_id") == item_id for item in again["items"])
    _scheduled_deadline_controls(db, tmp_path, monkeypatch, now)
    review_evidence(db, int(capture["source_key"]), decision="reject", actor="fixture")
    stale = client.post(
        "/unified/start",
        base_url="https://coach.invalid",
        headers={"Tailscale-User-Login": "login", "Origin": "https://coach.invalid"},
        data={
            "csrf": csrf,
            "source_type": "own-game",
            "version": capture["source_version"],
            "key": capture["source_key"],
            "training": "1",
        },
    )
    assert stale.status_code == 400
    db.close()


def _scheduled_deadline_controls(db, tmp_path, monkeypatch, now):
    from types import SimpleNamespace

    import chess_coach.capture_certificate_reader as certificate_reader
    import chess_coach.curriculum_capture_source as capture_source
    import chess_coach.curriculum_family_mix as family_mix
    import chess_coach.curriculum_new_capture as new_capture
    import chess_coach.curriculum_unified_owned as owned
    import chess_coach.fork_proof as fork_proof
    from chess_coach.curriculum import daily_plan
    from chess_coach.curriculum_conflicts import scheduled_page
    from chess_coach.curriculum_cursor_codec import decode_cursor
    from chess_coach.fact_fingerprint import digest
    from chess_coach.objective_fork_contract import MISS_VERSION
    from chess_coach.tactical_course_budget import PreviewUnavailable
    from tests.objective_fork_support import owned_fork

    def page(cursor=None):
        return daily_plan(
            db,
            subject=LEARNER,
            corpus_version="plan-fixture",
            limit=5,
            scan_limit=1,
            as_of=now,
            cursor=cursor,
        )

    first = page()
    second = page(first["next_cursor"])
    before = decode_cursor(db, second["next_cursor"])
    assert before["phase"] == "capture" and before["scheduled_after"] == 2
    clock = [0.0]
    inside = [False]
    visited = []
    original_capture = owned.capture_candidate
    original_prepare = certificate_reader.prepare
    original_proof = certificate_reader._proof

    def scheduled_capture(*args, **kwargs):
        inside[0] = True
        try:
            return original_capture(*args, **kwargs)
        finally:
            inside[0] = False

    def prepare(*args, **kwargs):
        result = original_prepare(*args, **kwargs)
        if inside[0]:
            visited.append(True)
            clock[0] = 3.0
        return result

    original_resolve = capture_source.resolve_source

    def admission_resolve(*args, **kwargs):
        inside[0] = True
        try:
            return original_resolve(*args, **kwargs)
        finally:
            inside[0] = False

    with monkeypatch.context() as patch:
        patch.setattr(new_capture, "time", SimpleNamespace(monotonic=lambda: clock[0]))
        patch.setattr(family_mix, "time", SimpleNamespace(monotonic=lambda: clock[0]))
        patch.setattr(capture_source, "resolve_source", admission_resolve)
        patch.setattr(certificate_reader, "prepare", prepare)
        admission_expired = page(second["next_cursor"])
    assert visited and admission_expired["continuation_reason"] == "capture_scan_incomplete"
    admission_state = decode_cursor(db, admission_expired["next_cursor"])
    assert (admission_state["capture_pending"], admission_state["scheduled_after"]) == (
        before["capture_pending"],
        before["scheduled_after"],
    )
    assert page(admission_expired["next_cursor"])["capture_status"] == "already_scheduled"
    clock[0] = 0.0
    visited.clear()

    with monkeypatch.context() as patch:
        patch.setattr(new_capture, "time", SimpleNamespace(monotonic=lambda: clock[0]))
        patch.setattr(family_mix, "time", SimpleNamespace(monotonic=lambda: clock[0]))
        patch.setattr(owned, "capture_candidate", scheduled_capture)
        patch.setattr(certificate_reader, "prepare", prepare)
        currentness_expired = page(second["next_cursor"])
    assert visited and currentness_expired["continuation_reason"] == "capture_scan_incomplete"
    currentness_state = decode_cursor(db, currentness_expired["next_cursor"])
    assert (currentness_state["capture_pending"], currentness_state["scheduled_after"]) == (
        before["capture_pending"],
        before["scheduled_after"],
    )
    clock[0] = 0.0
    visited.clear()

    def proof(*args, **kwargs):
        result = original_proof(*args, **kwargs)
        if inside[0]:
            visited.append(True)
            clock[0] = 3.0
        return result

    with monkeypatch.context() as patch:
        patch.setattr(new_capture, "time", SimpleNamespace(monotonic=lambda: clock[0]))
        patch.setattr(family_mix, "time", SimpleNamespace(monotonic=lambda: clock[0]))
        patch.setattr(owned, "capture_candidate", scheduled_capture)
        patch.setattr(certificate_reader, "_proof", proof)
        expired = page(second["next_cursor"])
    assert visited and expired["continuation_reason"] == "capture_scan_incomplete"
    after = decode_cursor(db, expired["next_cursor"])
    assert (after["capture_pending"], after["scheduled_after"]) == (
        before["capture_pending"],
        before["scheduled_after"],
    )
    resumed = page(expired["next_cursor"])
    assert resumed["capture_status"] == "already_scheduled"

    fork_db, evidence = owned_fork(
        tmp_path / "scheduled-fork.sqlite", monkeypatch, "f6g5", with_history=True
    )
    start(
        fork_db,
        attempt_id="scheduled-fork",
        subject=LEARNER,
        source_type="own-game",
        version=MISS_VERSION,
        key=str(evidence),
        training=True,
    )
    branches = []
    original_branch = fork_proof.defense_witness

    def branch(*args, **kwargs):
        value = original_branch(*args, **kwargs)
        branches.append(True)
        return value

    def deadline():
        if branches:
            raise PreviewUnavailable("fixture deadline")

    with monkeypatch.context() as patch:
        patch.setattr(fork_proof, "defense_witness", branch)
        with pytest.raises(PreviewUnavailable):
            scheduled_page(fork_db, "not-a-match", 0, 1, digest(LEARNER), check=deadline)
    assert branches
    matched, _, more, examined, unavailable = scheduled_page(
        fork_db, "not-a-match", 0, 1, digest(LEARNER), check=lambda: None
    )
    assert not matched and not more and examined == 1 and unavailable is None
    fork_db.close()


def _capture_practice_priority_workflow(tmp_path, monkeypatch):
    """Exercise real same-context source and practice selection on one project."""
    import io
    import sys
    from contextlib import redirect_stdout
    from datetime import UTC, datetime, timedelta

    import chess.pgn

    from chess_coach import cli, unified_session_apply, unified_sessions
    from chess_coach.capture_plan_history import latest
    from chess_coach.curriculum import daily_plan
    from chess_coach.curriculum_capture_witnesses import candidates
    from chess_coach.ingest import ingest_pgn
    from chess_coach.pipeline_config import PipelineConfig
    from chess_coach.pipeline_inputs import engine_identity, game_input
    from chess_coach.pipeline_work import run_analysis
    from chess_coach.related_capture import preview
    from chess_coach.related_capture_start import start_related
    from chess_coach.web import create_app

    root, path = capture_project(tmp_path, "capture-priority-project")
    db = make_game(path, monkeypatch)
    first = process_decision(db, 1, LEARNER)["evidence_ids"][0]
    review_evidence(db, first, decision="accept", actor="fixture")

    board = chess.Board("4k3/8/8/8/3q4/8/8/3R1K2 w - - 0 1")
    game = chess.pgn.Game()
    game.setup(board)
    game.headers.update(
        White=LEARNER,
        Black="fixture_opponent",
        Result="*",
        UTCDate="2026.01.02",
        UTCTime="12:00:00",
    )
    node = game.add_variation(board.parse_uci("f1e1"))
    board.push_uci("f1e1")
    node.add_variation(board.parse_uci("e8f8"))
    ingest_pgn(db, str(game))
    config = PipelineConfig(learner=LEARNER, engine_path=sys.executable, nodes=100)
    assert (
        run_analysis(db, 2, game_input(db, 2), config, engine_identity(sys.executable))["status"]
        == "complete"
    )
    position = db.connection.execute(
        "SELECT id FROM positions WHERE game_id=2 ORDER BY ply LIMIT 1"
    ).fetchone()[0]
    second = process_decision(db, position, LEARNER)["evidence_ids"][0]
    review_evidence(db, second, decision="accept", actor="fixture")
    corpus = db.connection.execute(
        "INSERT INTO puzzle_corpora(version,source,checksum,state) VALUES('priority','fixture','checksum','staging')"
    ).lastrowid
    for file in ("a", "b", "c", "d", "f", "g", "h"):
        puzzle = chess.Board("4k3/8/8/8/3q4/8/8/3RK3 b - - 0 1")
        puzzle.set_piece_at(chess.parse_square(file + "7"), chess.Piece(chess.PAWN, chess.BLACK))
        key = "priority-fixture-" + file
        db.connection.execute(
            """INSERT INTO puzzles(puzzle_id,corpus_id,fen,source,solution,rating,
            rating_deviation,themes_json,objective)
            VALUES(?,?,?,'fixture',?,1200,80,'["hangingPiece"]','unknown')""",
            (key, corpus, puzzle.fen(), file + "7" + file + "6 d1d4"),
        )
        db.connection.execute(
            "INSERT INTO puzzle_themes VALUES(?,?,'hangingPiece',1200)", (corpus, key)
        )
    db.connection.execute("UPDATE puzzle_corpora SET state='ready' WHERE id=?", (corpus,))
    base = datetime.now(UTC) - timedelta(minutes=2)
    db.connection.execute(
        "UPDATE tactical_exposure_coverage SET tracking_started_at=? WHERE id=1",
        ((base - timedelta(days=1)).isoformat(),),
    )
    db.connection.commit()
    from chess_coach.capture_certificate_buckets import observe as observe_certificate
    from chess_coach.opening_queue_location import scope as certificate_scope

    db.capture_root = certificate_scope(db, root)

    def forbidden(*_args, **_kwargs):
        raise AssertionError("capture proof ran in a request")

    with monkeypatch.context() as guard:
        guard.setattr("chess_coach.material_opportunity_current.verified_witness", forbidden)
        guard.setattr("chess_coach.objective_capture_snapshot.judge", forbidden)
        before_worker = daily_plan(
            db,
            subject=LEARNER,
            corpus_version="priority",
            limit=1,
            goal="capture",
            project_root=root,
        )
    certify(db, LEARNER, root)
    with pytest.raises(ValueError, match="capture practice changed"):
        daily_plan(
            db,
            subject=LEARNER,
            corpus_version="priority",
            limit=1,
            goal="capture",
            cursor=before_worker["window_cursor"],
            project_root=root,
        )
    for evidence_id in (first, second):
        observed = observe_certificate(db, root, LEARNER, evidence_id)
        assert observed and observed[2]
    from tests.capture_certificate_fixture import prepare_corpus

    prepare_corpus(db, LEARNER, root, "priority", position)
    options, status, _, _ = candidates(db, LEARNER, "priority", lambda: None)
    assert status == "available" and len(options) == 2
    assert options[0][0]["prompt_key"] != options[1][0]["prompt_key"]
    positions = [report["source"]["position_id"] for _, report in options]
    assert set(positions) == {1, position}
    clock = [base]
    original_start_clock, original_event_clock = unified_sessions.now, unified_session_apply.now
    monkeypatch.setattr(unified_sessions, "now", lambda: clock[0].isoformat())
    monkeypatch.setattr(unified_session_apply, "now", lambda: clock[0].isoformat())
    secret = b"capture-priority-fixture"

    # More than the bounded history window predates both qualified observations.
    for index in range(101):
        start(
            db,
            attempt_id=f"zz-older-unrelated-{index:03d}",
            subject=LEARNER,
            source_type="corpus",
            version="priority",
            key="priority-fixture-a",
        )

    def attempt(source_position, outcome, number, *, pause=False):
        selected = preview(db, LEARNER, source_position, "priority", secret=secret)
        entry = next(item for item in selected["items"] if item.get("assessment_available"))
        clock[0] += timedelta(seconds=1)
        attempt_id = f"priority-attempt-{number}"
        start_related(
            db,
            attempt_id=attempt_id,
            subject=LEARNER,
            position=source_position,
            corpus_version="priority",
            reference=entry["reference"],
            assessment=True,
            secret=secret,
        )
        if pause:
            return attempt_id
        answer(attempt_id, source_position, outcome)
        return attempt_id

    def answer(attempt_id, source_position, outcome):
        clock[0] += timedelta(seconds=1)
        submit(
            db,
            attempt_id,
            LEARNER,
            event_id="answer",
            move="d1d4" if outcome == "correct" else "e1f1",
        )
        assert process(db, LEARNER)["outcomes"] == {outcome: 1}
        assert latest(db, LEARNER, source_position, "priority")["status"] == outcome

    def plan(**kwargs):
        return daily_plan(
            db,
            subject=LEARNER,
            corpus_version="priority",
            limit=1,
            goal="capture",
            project_root=root,
            **kwargs,
        )

    from chess_coach.unified_session_events import show as show_unified
    from chess_coach.unified_source_current import snapshot_hash

    existing_key = options[0][0]["source_key"]
    start(
        db,
        attempt_id="existing-certified-capture",
        subject=LEARNER,
        source_type="own-game",
        version=TARGET_VERSION,
        key=existing_key,
        project_root=root,
    )
    existing_hash = db.connection.execute(
        "SELECT snapshot_hash FROM unified_sessions WHERE attempt_id=?",
        ("existing-certified-capture",),
    ).fetchone()[0]
    observed = observe_certificate(db, root, LEARNER, int(existing_key))
    assert observed and existing_hash == snapshot_hash(observed[2]["snapshot"])

    with monkeypatch.context() as guard:
        guard.setattr("chess_coach.material_opportunity_current.verified_witness", forbidden)
        guard.setattr("chess_coach.objective_capture_snapshot.judge", forbidden)
        assert show_unified(db, "existing-certified-capture", LEARNER)["objective"] == (
            "capture_named_target"
        )
        before_read = db.connection.total_changes
        unknown = plan()
        assert db.connection.total_changes == before_read
    assert unknown["items"][0]["source_key"] == options[0][0]["source_key"]
    assert "unknown or tied" in unknown["items"][0]["reason"]

    from chess_coach.tactical_course_budget import PreviewUnavailable

    with monkeypatch.context() as interrupted:
        interrupted.setattr(
            "chess_coach.curriculum_priority_prepare.snapshot",
            lambda *_: (_ for _ in ()).throw(PreviewUnavailable("fixture deadline")),
        )
        deferred = plan()
    assert deferred["continuation_reason"] == "priority_scan_incomplete"
    db.connection.execute("BEGIN")
    with pytest.raises(ValueError, match="capture practice unavailable during caller transaction"):
        plan(cursor=deferred["window_cursor"])
    assert db.connection.in_transaction
    db.connection.rollback()

    # A matching assessment at the 101st timestamp cannot prove latest.
    clock[0] -= timedelta(seconds=1)
    attempt(positions[0], "correct", "boundary")
    boundary = latest(db, LEARNER, positions[0], "priority", prove_latest=True)
    assert boundary["limited"] is True and boundary["latest_proven"] is False
    at_boundary = plan()
    assert at_boundary["items"][0]["source_key"] == options[0][0]["source_key"]
    assert "unknown or tied" in at_boundary["items"][0]["reason"]

    attempt(positions[0], "correct", 1)
    pending = attempt(positions[1], "correct", 2, pause=True)
    partial = plan()
    assert partial["items"][0]["source_key"] == options[0][0]["source_key"]
    assert "unknown or tied" in partial["items"][0]["reason"]
    answer(pending, positions[1], "correct")
    for source_position in positions:
        history = latest(db, LEARNER, source_position, "priority", prove_latest=True)
        assert history["limited"] is True and history["latest_proven"] is True

    boundary_time = db.connection.execute(
        "SELECT started_at FROM unified_sessions WHERE attempt_id='priority-attempt-boundary'"
    ).fetchone()[0]
    first_time = db.connection.execute(
        "SELECT started_at FROM unified_sessions WHERE attempt_id='priority-attempt-1'"
    ).fetchone()[0]
    db.connection.execute(
        "UPDATE unified_sessions SET started_at=? WHERE attempt_id='priority-attempt-boundary'",
        (first_time,),
    )
    db.connection.commit()
    assert latest(db, LEARNER, positions[0], "priority", prove_latest=True)["status"] == "stale"
    db.connection.execute(
        "UPDATE unified_sessions SET started_at=? WHERE attempt_id='priority-attempt-boundary'",
        (boundary_time,),
    )
    db.connection.execute(
        "UPDATE unified_sessions SET started_at='not-a-time' WHERE attempt_id='zz-older-unrelated-000'"
    )
    db.connection.commit()
    malformed = plan()
    assert malformed["items"][0]["source_key"] == options[0][0]["source_key"]
    assert "unknown or tied" in malformed["items"][0]["reason"]
    db.connection.execute(
        "UPDATE unified_sessions SET started_at=? WHERE attempt_id='zz-older-unrelated-000'",
        (base.isoformat(),),
    )
    db.connection.commit()
    before = db.connection.total_changes
    tied = plan()
    assert db.connection.total_changes == before
    assert tied["items"][0]["source_key"] == options[0][0]["source_key"]
    assert "unknown or tied" in tied["items"][0]["reason"]
    assert "importance is unknown" in tied["items"][0]["reason"]
    with monkeypatch.context() as old_policy:
        old_policy.setattr(
            "chess_coach.curriculum_capture_inputs.POLICY", "capture-practice-inputs-v1"
        )
        old_window = plan()["window_cursor"]
    with pytest.raises(ValueError, match="capture practice changed"):
        plan(cursor=old_window)
    unchanged = plan(cursor=tied["window_cursor"])
    assert unchanged["window"]["goal"] == "capture"
    renewed = plan(cursor=tied["window_cursor"], renew=True)
    assert renewed["window"]["goal"] == "capture"

    from chess_coach.capture_game_trend_paths import location as trend_location
    from tests.native_pair_probe import Forms

    app = create_app(
        db_path=path,
        subject=LEARNER,
        actor="fixture",
        corpus="priority",
        login="fixture",
        origin="https://coach.invalid",
        project_root=root,
    )
    client = app.test_client()
    headers = {"Tailscale-User-Login": "fixture"}

    def learning_counts():
        tables = (
            "unified_sessions",
            "unified_session_events",
            "objective_requests",
            "objective_results",
            "unified_training_enrollments",
            "training_items",
            "training_attempts",
            "mastery_events",
        )
        return tuple(
            db.connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0] for table in tables
        )

    def guidance(expected, text, link):
        before = learning_counts()
        for query in ("", "?goal=capture&minutes=1"):
            response = client.get(
                "/plan" + query, base_url="https://coach.invalid", headers=headers
            )
            assert response.status_code == 200 and text in response.data
            assert link in response.data
            assert f'name="key" value="{options[0][0]["source_key"]}"'.encode() not in response.data
        ordinary = daily_plan(
            db, subject=LEARNER, corpus_version="priority", limit=1, project_root=root
        )
        window = plan(duration_minutes=1)
        for page in (ordinary, window):
            assert page["capture_status"] == "history_unavailable"
            assert page["capture_focus"]["source"]["position_id"] == positions[0]
            assert page["capture_focus"]["history"]["status"] == expected
            assert all(
                item.get("source_key") != options[0][0]["source_key"] for item in page["items"]
            )
        assert learning_counts() == before

    active = attempt(positions[0], "correct", "guidance", pause=True)
    guidance("incomplete", b"Continue your capture assessment", f"/unified/{active}".encode())
    before_changed = learning_counts()
    with monkeypatch.context() as changed:
        changed.setattr("chess_coach.plan_page_options.current_generation", lambda *_: -1)
        page = client.get(
            "/plan?goal=capture&minutes=1", base_url="https://coach.invalid", headers=headers
        )
    assert page.status_code == 200 and b"Continue your capture assessment" not in page.data
    assert learning_counts() == before_changed
    submit(db, active, LEARNER, event_id="answer", move="d1d4")
    guidance("pending", b"Check your capture assessment status", f"/unified/{active}".encode())
    assert process(db, LEARNER)["outcomes"] == {"correct": 1}
    restored = plan()
    assert restored["items"][0]["source_key"] == options[0][0]["source_key"]

    # A new review leaves the evidence usable but invalidates its old assessment binding.
    review_evidence(db, options[0][1]["source"]["evidence_id"], decision="accept", actor="fixture")
    certify(db, LEARNER, root)
    guidance("stale", b"The latest assessment could not be checked", b"/plan/captures")
    attempt(positions[0], "correct", "guidance-refreshed")
    assert plan()["items"][0]["source_key"] == options[0][0]["source_key"]

    def form(query):
        response = client.get("/plan?" + query, base_url="https://coach.invalid", headers=headers)
        assert response.status_code == 200
        parsed = Forms()
        parsed.feed(response.get_data(as_text=True))
        return next(
            item
            for item in parsed.forms
            if item.get("training") == "1"
            and item.get("source_type") == "own-game"
            and item.get("window_offer")
        )

    timed_form, untimed_form = form("goal=capture&minutes=1"), form("goal=capture")
    count = db.connection.execute("SELECT count(*) FROM unified_sessions").fetchone()[0]
    trend = trend_location(db, root)
    assert trend is not None and trend.exists() and trend.read_text() != "{}"
    trend.write_text("{}")
    with pytest.raises(ValueError, match="capture practice changed"):
        plan(cursor=tied["window_cursor"])
    refreshed = plan(cursor=tied["window_cursor"], renew=True)
    assert refreshed["window"]["source_refreshed"]
    assert refreshed["items"][0]["source_key"] == options[0][0]["source_key"]
    for old_form in (timed_form, untimed_form):
        response = client.post(
            "/unified/start",
            data=old_form,
            base_url="https://coach.invalid",
            headers=headers | {"Origin": "https://coach.invalid"},
        )
        assert response.status_code == 400
    assert db.connection.execute("SELECT count(*) FROM unified_sessions").fetchone()[0] == count
    assert (
        db.connection.execute("SELECT count(*) FROM unified_training_enrollments").fetchone()[0]
        == 0
    )

    tied = plan()
    old_offer = tied["items"][0]["window_offer"]
    old_cursor = tied["window_cursor"]
    attempt(positions[1], "incorrect", 3)
    with pytest.raises(ValueError, match="capture practice changed"):
        plan(cursor=old_cursor)
    refreshed = plan(cursor=old_cursor, renew=True)
    assert refreshed["window"]["source_refreshed"]
    assert refreshed["items"][0]["source_key"] == options[1][0]["source_key"]
    with pytest.raises(ValueError, match="capture practice offer changed"):
        start(
            db,
            attempt_id="stale-priority",
            subject=LEARNER,
            source_type="own-game",
            version=TARGET_VERSION,
            key=options[0][0]["source_key"],
            training=True,
            window_offer=old_offer,
            project_root=root,
        )
    chosen = plan()
    assert chosen["items"][0]["source_key"] == options[1][0]["source_key"]
    assert "Comparable verified practice selected" in chosen["items"][0]["reason"]
    output = io.StringIO()
    with monkeypatch.context() as patch, redirect_stdout(output):
        patch.setattr("chess_coach.material_opportunity_current.verified_witness", forbidden)
        patch.setattr("chess_coach.objective_capture_snapshot.judge", forbidden)
        patch.setattr(
            sys,
            "argv",
            [
                "chess-coach",
                "--db",
                str(path),
                "daily-plan",
                "priority",
                "--subject",
                LEARNER,
                "--limit",
                "1",
                "--goal",
                "capture",
                "--project-root",
                str(root),
            ],
        )
        cli.main()
    assert (
        json.loads(output.getvalue())["items"][0]["source_key"] == chosen["items"][0]["source_key"]
    )
    with monkeypatch.context() as guard:
        guard.setattr("chess_coach.material_opportunity_current.verified_witness", forbidden)
        guard.setattr("chess_coach.objective_capture_snapshot.judge", forbidden)
        page = client.get(
            "/plan?goal=capture",
            base_url="https://coach.invalid",
            headers=headers,
        )
    assert page.status_code == 200
    assert f'name="key" value="{chosen["items"][0]["source_key"]}"'.encode() in page.data
    assert b"Comparable verified practice selected" in page.data
    selected_form = form("goal=capture&minutes=1")

    # A missing certificate refuses an already signed launch without creating learning.
    from chess_coach.capture_certificate_buckets import publish as publish_certificates
    from chess_coach.capture_certificate_refresh import entries as certificate_entries

    chosen_id = int(chosen["items"][0]["source_key"])
    retained, _ = certificate_entries(db, root, LEARNER, chosen_id)
    retained.pop(str(chosen_id))
    before_missing = tuple(
        db.connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
        for table in ("unified_sessions", "unified_training_enrollments")
    )
    publish_certificates(db, root, LEARNER, chosen_id, retained)
    missing = client.post(
        "/unified/start",
        data=selected_form,
        base_url="https://coach.invalid",
        headers=headers | {"Origin": "https://coach.invalid"},
    )
    assert missing.status_code == 400
    assert before_missing == tuple(
        db.connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
        for table in ("unified_sessions", "unified_training_enrollments")
    )
    certify(db, LEARNER, root)
    chosen = plan()
    assert chosen["items"][0]["source_key"] == options[1][0]["source_key"]
    selected_form = form("goal=capture&minutes=1")

    # A different observed bucket can change after enrollment but before commit.
    other_id = int(options[0][0]["source_key"])
    other_records, _ = certificate_entries(db, root, LEARNER, other_id)
    other_records.pop(str(other_id))
    finish = unified_sessions._window_time

    def replace_before_commit(value, transaction_db, budget):
        publish_certificates(transaction_db, root, LEARNER, other_id, other_records)
        return finish(value, transaction_db, budget)

    before_finish = tuple(
        db.connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
        for table in ("unified_sessions", "unified_training_enrollments", "training_items")
    )
    with monkeypatch.context() as interrupted:
        interrupted.setattr(unified_sessions, "_window_time", replace_before_commit)
        refused = client.post(
            "/unified/start",
            data=selected_form,
            base_url="https://coach.invalid",
            headers=headers | {"Origin": "https://coach.invalid"},
        )
    assert refused.status_code == 400
    assert before_finish == tuple(
        db.connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
        for table in ("unified_sessions", "unified_training_enrollments", "training_items")
    )
    certify(db, LEARNER, root)
    chosen = plan()
    selected_form = form("goal=capture&minutes=1")
    from chess_coach.curriculum_capture_offer import POLICY as NEW_OFFER_POLICY
    from chess_coach.curriculum_cursor import revision
    from chess_coach.curriculum_prerequisite_token import _decode
    from chess_coach.curriculum_window_scope import POLICY as OLD_OFFER_POLICY

    assert _decode(db, selected_form["window_offer"])[0] == NEW_OFFER_POLICY
    assert NEW_OFFER_POLICY != OLD_OFFER_POLICY
    other_game = db.connection.execute(
        "SELECT game_id FROM positions WHERE id=?", (positions[0],)
    ).fetchone()[0]
    old_generation = db.connection.execute(
        "SELECT generation FROM pipeline_stages WHERE game_id=? AND stage='analysis'",
        (other_game,),
    ).fetchone()[0]
    previous_revision = revision(db)
    db.connection.execute(
        "UPDATE pipeline_stages SET generation=generation+1 WHERE game_id=? AND stage='analysis'",
        (other_game,),
    )
    db.connection.commit()
    assert revision(db) == previous_revision
    with pytest.raises(ValueError, match="capture sources changed"):
        plan(cursor=chosen["window_cursor"])
    prior_sessions = db.connection.execute("SELECT count(*) FROM unified_sessions").fetchone()[0]
    refused = client.post(
        "/unified/start",
        data=selected_form,
        base_url="https://coach.invalid",
        headers=headers | {"Origin": "https://coach.invalid"},
    )
    assert refused.status_code == 400
    assert (
        db.connection.execute("SELECT count(*) FROM unified_sessions").fetchone()[0]
        == prior_sessions
    )
    assert (
        db.connection.execute("SELECT count(*) FROM unified_training_enrollments").fetchone()[0]
        == 0
    )
    db.connection.execute(
        "UPDATE pipeline_stages SET generation=? WHERE game_id=? AND stage='analysis'",
        (old_generation, other_game),
    )
    db.connection.commit()
    selected_form = form("goal=capture&minutes=1")
    with monkeypatch.context() as guard:
        guard.setattr("chess_coach.material_opportunity_current.verified_witness", forbidden)
        guard.setattr("chess_coach.objective_capture_snapshot.judge", forbidden)
        response = client.post(
            "/unified/start",
            data=selected_form,
            base_url="https://coach.invalid",
            headers=headers | {"Origin": "https://coach.invalid"},
        )
        assert response.status_code == 303
        redirected = client.get(
            response.headers["Location"], base_url="https://coach.invalid", headers=headers
        )
        assert redirected.status_code == 200
    assert (
        db.connection.execute("SELECT count(*) FROM unified_training_enrollments").fetchone()[0]
        == 1
    )
    resumed = plan(cursor=chosen["window_cursor"], renew=True)
    assert resumed["window"]["source_refreshed"]
    assert resumed["items"][0]["kind"] == "due"
    assert resumed["items"][0]["source_key"] == chosen["items"][0]["source_key"]

    from chess_coach.curriculum_window_cursor import decode as decode_window
    from chess_coach.training import create_training_item

    for file in ("a", "b", "c"):
        create_training_item(
            db,
            source_type="puzzle",
            source_ref=json.dumps(["priority", "priority-fixture-" + file]),
            skill="mate_in_one",
            operation="execute",
        )
    historical = base + timedelta(minutes=1)
    scanned = daily_plan(
        db,
        subject=LEARNER,
        corpus_version="priority",
        limit=1,
        scan_limit=1,
        goal="capture",
        as_of=historical,
        project_root=root,
    )
    positions_seen, matches_seen = [], []
    for _ in range(6):
        state = decode_window(db, scanned["window_cursor"])["state"]
        if state["capture_pending"] is not None:
            positions_seen.append(state["scheduled_after"])
            matches_seen.append(state["priority"]["capture_matches"])
        if scanned["next_cursor"] is None:
            break
        scanned = daily_plan(
            db,
            subject=LEARNER,
            corpus_version="priority",
            limit=1,
            scan_limit=1,
            goal="capture",
            as_of=historical,
            cursor=scanned["next_cursor"],
            project_root=root,
        )
    assert positions_seen == sorted(set(positions_seen)) and len(positions_seen) >= 3
    assert any(mask & 2 for mask in matches_seen)
    assert scanned["items"][0]["source_key"] == options[0][0]["source_key"]
    assert "unknown or tied" in scanned["items"][0]["reason"]

    for index in range(101):
        start(
            db,
            attempt_id=f"unrelated-{index:03d}",
            subject=LEARNER,
            source_type="corpus",
            version="priority",
            key="priority-fixture-a",
        )
    from chess_coach.curriculum_capture_practice_binding import practice

    assert practice(db, LEARNER, lambda: None)[0] is True
    due = daily_plan(
        db,
        subject=LEARNER,
        corpus_version="priority",
        limit=2,
        goal="fork",
        project_root=root,
    )
    assert due["items"] and due["items"][0]["kind"] == "due"
    unknown = daily_plan(
        db,
        subject=LEARNER,
        corpus_version="priority",
        limit=1,
        goal="capture",
        as_of=historical,
        project_root=root,
    )
    assert unknown["items"][0]["source_key"] == options[0][0]["source_key"]
    assert "unknown or tied" in unknown["items"][0]["reason"]

    planning = root / ".runtime" / "planning"
    for index in range(101):
        (planning / f"tactical-study-{index:064x}-intent.json").write_text("{}")
    from chess_coach.tactical_exposure_check import check as exposure_check

    assert exposure_check(db, LEARNER, options[0][0]["prompt_key"]) == "coverage_unavailable"
    due = daily_plan(
        db,
        subject=LEARNER,
        corpus_version="priority",
        limit=2,
        goal="fork",
        project_root=root,
    )
    assert due["items"] and due["items"][0]["kind"] == "due"
    unknown = daily_plan(
        db,
        subject=LEARNER,
        corpus_version="priority",
        limit=1,
        goal="capture",
        as_of=historical,
        project_root=root,
    )
    assert unknown["items"][0]["source_key"] == options[0][0]["source_key"]
    assert "unknown or tied" in unknown["items"][0]["reason"]
    monkeypatch.setattr(unified_sessions, "now", original_start_clock)
    monkeypatch.setattr(unified_session_apply, "now", original_event_clock)
    db.close()


def _retained_capture_workflow(tmp_path, monkeypatch):
    """Backfill real older capture sessions without dropping newer certificates."""
    import io
    import sys
    import time
    from typing import Any

    import chess.pgn

    import chess_coach.capture_certificate_refresh as refresh
    import chess_coach.capture_certificate_worker as worker
    from chess_coach.capture_certificate_buckets import observe
    from chess_coach.capture_certificate_buckets import publish as publish_bucket
    from chess_coach.capture_certificate_progress import checkpoint, save
    from chess_coach.capture_certificate_refresh import entries as bucket_entries
    from chess_coach.capture_certificate_worker import PROOFS, SCAN, run
    from chess_coach.curriculum import daily_plan
    from chess_coach.ingest import ingest_pgn
    from chess_coach.pipeline_config import PipelineConfig
    from chess_coach.pipeline_inputs import engine_identity, game_input
    from chess_coach.pipeline_lock import pipeline_lock
    from chess_coach.pipeline_work import run_analysis
    from chess_coach.unified_source_current import snapshot_hash
    from chess_coach.web import create_app
    from tests.capture_certificate_fixture import cli as fresh_cli

    root, path = capture_project(tmp_path, "retained-capture-project")
    db = make_game(path, monkeypatch)
    old = process_decision(db, 1, LEARNER)["evidence_ids"][0]
    review_evidence(db, old, decision="accept", actor="fixture")
    certify(db, LEARNER, root)
    start(
        db,
        attempt_id="retained-due",
        subject=LEARNER,
        source_type="own-game",
        version=TARGET_VERSION,
        key=str(old),
        training=True,
    )
    assert (
        submit(db, "retained-due", LEARNER, event_id="answer", move="e1f1")["status"]
        == "needs_verification"
    )
    assert process(db, LEARNER)["outcomes"] == {"incorrect": 1}
    learning = show(db, "retained-due", LEARNER)["learning"]
    assert learning["outcome"] == "failure"
    item_id = learning["item_id"]
    db.connection.execute(
        "UPDATE training_items SET due=? WHERE id=?", ("2000-01-01T00:00:00+00:00", item_id)
    )
    db.connection.commit()
    item_before = tuple(
        db.connection.execute("SELECT * FROM training_items WHERE id=?", (item_id,)).fetchone()
    )
    start(
        db,
        attempt_id="retained-active",
        subject=LEARNER,
        source_type="own-game",
        version=TARGET_VERSION,
        key=str(old),
        training=True,
    )
    snapshot_before = db.connection.execute(
        "SELECT snapshot_hash FROM unified_sessions WHERE attempt_id=?", ("retained-active",)
    ).fetchone()[0]
    assert snapshot_before == snapshot_hash(observe(db, root, LEARNER, old)[2]["snapshot"])

    original_pgn = db.connection.execute("SELECT pgn FROM games WHERE id=1").fetchone()[0]
    config = PipelineConfig(learner=LEARNER, engine_path=sys.executable, nodes=100)
    engine = engine_identity(sys.executable)

    def add_source(day):
        game = chess.pgn.read_game(io.StringIO(original_pgn))
        assert game is not None
        game.headers["UTCDate"] = f"2026.01.{day:02d}"
        if day == 2:
            game.headers["Opening"] = "Fixture Opening: line"
        assert ingest_pgn(db, str(game))["games"] == 1
        game_id = db.connection.execute("SELECT max(id) FROM games").fetchone()[0]
        assert (
            run_analysis(db, game_id, game_input(db, game_id), config, engine)["status"]
            == "complete"
        )
        position = db.connection.execute(
            "SELECT id FROM positions WHERE game_id=? ORDER BY ply LIMIT 1", (game_id,)
        ).fetchone()[0]
        return process_decision(db, position, LEARNER)["evidence_ids"][0]

    newer = [add_source(2)]
    certify(db, LEARNER, root)
    start(
        db,
        attempt_id="retained-gain",
        subject=LEARNER,
        source_type="own-game",
        version=GAIN_VERSION,
        key=str(newer[0]),
    )
    assert (
        db.connection.execute(
            "SELECT 1 FROM unified_training_enrollments WHERE attempt_id=?", ("retained-gain",)
        ).fetchone()
        is None
    )
    # Two actual related assessments bind the original annotated source before
    # later evidence pushes it outside the ordinary candidate page.
    from chess_coach.related_capture import preview
    from chess_coach.related_capture_source import source_for_position
    from chess_coach.related_capture_start import start_related

    related_position = db.connection.execute(
        "SELECT position_id FROM evidence_mappings WHERE id=?", (newer[0],)
    ).fetchone()[0]
    original_source = source_for_position(db, LEARNER, related_position)
    assert original_source["opening"] == "Fixture_Opening"
    corpus = db.connection.execute(
        "INSERT INTO puzzle_corpora(version,source,checksum,state) VALUES('capture','fixture','checksum','staging')"
    ).lastrowid
    for file in ("a", "b", "c", "f", "g"):
        board = chess.Board("4k3/8/8/8/3q4/8/8/3RK3 b - - 0 1")
        board.set_piece_at(chess.parse_square(file + "7"), chess.Piece(chess.PAWN, chess.BLACK))
        key = "retained-related-" + file
        db.connection.execute(
            """INSERT INTO puzzles(puzzle_id,corpus_id,fen,source,solution,rating,
            rating_deviation,themes_json,objective)
            VALUES(?,?,?,'fixture',?,1200,80,'["hangingPiece"]','unknown')""",
            (key, corpus, board.fen(), file + "7" + file + "6 d1d4"),
        )
        db.connection.execute(
            "INSERT INTO puzzle_themes VALUES(?,?,'hangingPiece',1200)", (corpus, key)
        )
    db.connection.execute("UPDATE puzzle_corpora SET state='ready' WHERE id=?", (corpus,))
    db.connection.commit()
    from tests.capture_certificate_fixture import prepare_corpus

    prepare_corpus(db, LEARNER, root, "capture", related_position)
    secret = b"retained-related-fixture"

    # The source remains byte-identical while a genuine neighboring certificate
    # changes. Existing unsigned-file-scope references and continuations expire.
    from chess_coach import tactical_exposure_admission
    from chess_coach.related_capture import VERSION as transfer_version
    from chess_coach.related_capture import present as present_transfer
    from chess_coach.related_transfer_select import select as select_transfer

    old_selection = select_transfer(db, LEARNER, original_source, "capture", transfer_version)
    old_preview = present_transfer(old_selection, None, secret=secret)

    # All candidate gain checks stay real; only a proof of this already-certified
    # owned source is forbidden during subsequent capture requests.
    import chess_coach.related_capture_features as related_features

    owned_prompt = original_source["prompt_fen"]
    owned_move = original_source["lines"][0].split()[0]
    actual_gain = related_features.capture_gain
    candidate_checks = []

    def guard_owned_gain(board, move, target, **kwargs):
        if board.fen() == owned_prompt and move.uci() == owned_move:
            raise AssertionError("owned source proof ran during related request")
        candidate_checks.append(True)
        return actual_gain(board, move, target, **kwargs)

    monkeypatch.setattr(related_features, "capture_gain", guard_owned_gain)
    assert old_preview["next_cursor"] is not None
    with pytest.raises(ValueError):
        preview(db, LEARNER, related_position, "capture", old_preview["next_cursor"], secret=secret)
    with pytest.raises(ValueError):
        start_related(
            db,
            attempt_id="unbound-refused",
            subject=LEARNER,
            position=related_position,
            corpus_version="capture",
            reference=old_preview["items"][0]["reference"],
            assessment=True,
            secret=secret,
        )
    assert (
        db.connection.execute(
            "SELECT 1 FROM unified_sessions WHERE attempt_id='unbound-refused'"
        ).fetchone()
        is None
    )

    stale_page = preview(db, LEARNER, related_position, "capture", secret=secret)
    assert stale_page["next_cursor"] is not None
    stale_item = next(item for item in stale_page["items"] if item.get("assessment_available"))
    neighbor_records, _ = bucket_entries(db, root, LEARNER, newer[0])
    selected_entry = neighbor_records[str(newer[0])]
    neighbor_entry = neighbor_records.pop(str(old))
    publish_bucket(db, root, LEARNER, newer[0], neighbor_records)
    assert observe(db, root, LEARNER, newer[0])[2] == selected_entry
    with pytest.raises(ValueError):
        preview(db, LEARNER, related_position, "capture", stale_page["next_cursor"], secret=secret)
    with pytest.raises(ValueError):
        start_related(
            db,
            attempt_id="changed-preview",
            subject=LEARNER,
            position=related_position,
            corpus_version="capture",
            reference=stale_item["reference"],
            assessment=True,
            secret=secret,
        )
    assert (
        db.connection.execute(
            "SELECT 1 FROM unified_sessions WHERE attempt_id='changed-preview'"
        ).fetchone()
        is None
    )
    neighbor_records[str(old)] = neighbor_entry
    publish_bucket(db, root, LEARNER, newer[0], neighbor_records)

    fresh_page = preview(db, LEARNER, related_position, "capture", secret=secret)
    fresh_item = next(item for item in fresh_page["items"] if item.get("assessment_available"))
    tables = (
        "unified_sessions",
        "unified_session_events",
        "objective_requests",
        "objective_results",
        "unified_training_enrollments",
        "training_items",
        "training_attempts",
        "mastery_events",
    )
    before_commit = tuple(
        db.connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0] for table in tables
    )
    real_assessment = tactical_exposure_admission.require_assessment

    def publish_before_commit(database, subject, row, binding):
        real_assessment(database, subject, row, binding)
        records, _ = bucket_entries(database, root, subject, newer[0])
        assert records[str(newer[0])] == selected_entry
        records.pop(str(old))
        publish_bucket(database, root, subject, newer[0], records)

    with monkeypatch.context() as changing:
        changing.setattr(tactical_exposure_admission, "require_assessment", publish_before_commit)
        with pytest.raises(ValueError, match="capture source changed"):
            start_related(
                db,
                attempt_id="changed-before-commit",
                subject=LEARNER,
                position=related_position,
                corpus_version="capture",
                reference=fresh_item["reference"],
                assessment=True,
                secret=secret,
            )
    assert before_commit == tuple(
        db.connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0] for table in tables
    )
    restored, _ = bucket_entries(db, root, LEARNER, newer[0])
    assert restored[str(newer[0])] == selected_entry
    restored[str(old)] = neighbor_entry
    publish_bucket(db, root, LEARNER, newer[0], restored)

    for name in ("related-completed", "related-active"):
        choices = preview(db, LEARNER, related_position, "capture", secret=secret)
        selected = next(item for item in choices["items"] if item.get("assessment_available"))
        start_related(
            db,
            attempt_id=name,
            subject=LEARNER,
            position=related_position,
            corpus_version="capture",
            reference=selected["reference"],
            assessment=True,
            secret=secret,
        )
        if name == "related-completed":
            submit(db, name, LEARNER, event_id="answer", move="d1d4")
            assert process(db, LEARNER)["outcomes"] == {"correct": 1}
    related_rows = {
        name: dict(
            db.connection.execute(
                "SELECT snapshot_hash,provenance_json FROM unified_sessions WHERE attempt_id=?",
                (name,),
            ).fetchone()
        )
        for name in ("related-completed", "related-active")
    }
    for row in related_rows.values():
        binding = json.loads(row["provenance_json"])["related_capture"]
        assert (
            binding["evidence_id"],
            binding["position_id"],
            binding["source_snapshot_hash"],
        ) == (newer[0], related_position, snapshot_hash(original_source))

    # A pre-upgrade checkpoint with only the original global cursor survives.
    from chess_coach.capture_certificate_store import binding
    from chess_coach.short_mate_trend_store import write

    progress_path, prior = checkpoint(db, LEARNER, root)
    write(progress_path, {"binding": binding(db, LEARNER), "before": prior["before"]})
    assert checkpoint(db, LEARNER, root)[1]["before"] == prior["before"]
    newer.extend(add_source(day) for day in range(3, 26))
    for evidence_id in newer[-3:]:
        review_evidence(db, evidence_id, decision="reject", actor="fixture")
    assert SCAN == 20 and PROOFS == 3
    plan_args: dict[str, Any] = dict(
        subject=LEARNER,
        corpus_version="fixture",
        limit=2,
        goal="capture",
        duration_minutes=1,
        project_root=root,
    )
    single_args: dict[str, Any] = {**plan_args, "limit": 1}
    before = daily_plan(db, **plan_args)
    cursor = before["window_cursor"]
    counts = tuple(
        db.connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
        for table in ("unified_sessions", "unified_training_enrollments", "training_attempts")
    )

    def turn():
        visits = proofs = 0
        original_visit, original_prove = worker._visit, refresh.prove

        def visit(*args):
            nonlocal visits
            result = original_visit(*args)
            visits += int(result[0])
            return result

        def prove(*args):
            nonlocal proofs
            proofs += 1
            return original_prove(*args)

        with monkeypatch.context() as budget:
            budget.setattr(worker, "_visit", visit)
            budget.setattr(refresh, "prove", prove)
            with pipeline_lock(db.path):
                run(db, LEARNER, root, time.monotonic() + 5)
        assert visits <= SCAN and proofs <= PROOFS

    turn()
    assert checkpoint(db, LEARNER, root)[1]["before"] == newer[-3]
    with pytest.raises(ValueError, match="capture practice changed"):
        daily_plan(db, cursor=cursor, **plan_args)
    assert counts == tuple(
        db.connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
        for table in ("unified_sessions", "unified_training_enrollments", "training_attempts")
    )

    real_prove = refresh.prove

    def expire_proof(database, subject, evidence_id, check):
        def expired():
            raise TimeoutError("fixture deadline")

        return real_prove(database, subject, evidence_id, expired)

    with monkeypatch.context() as deadline:
        deadline.setattr(refresh, "prove", expire_proof)
        turn()
    timed_out = newer[-4]
    assert checkpoint(db, LEARNER, root)[1]["before"] == timed_out
    assert observe(db, root, LEARNER, timed_out) is None

    # Both direct references predate the unfinished evidence scan. Remove their
    # certificates and keep appending newer sources while the worker resumes.
    for evidence_id in (old, newer[0]):
        records, _ = bucket_entries(db, root, LEARNER, evidence_id)
        records.pop(str(evidence_id))
        publish_bucket(db, root, LEARNER, evidence_id, records)

    with pytest.raises(ValueError, match="practice source unavailable or stale"):
        show(db, "related-active", LEARNER)
    with pytest.raises(ValueError, match="practice source unavailable or stale"):
        show(db, "related-completed", LEARNER)

    # A timed-out direct reference advances only its own visited frontier and
    # is retried after that finite pass, so it cannot starve the other lanes.
    progress_path, current = checkpoint(db, LEARNER, root)
    # Preserve the real session frontier after the newer related attempts.
    marker = []
    while True:
        row, following = worker.session(db, LEARNER, marker)
        assert row is not None
        if row["attempt_id"] == "retained-gain":
            break
        marker = following
    current["lane"], current["session"], current["related"] = 1, marker, following
    save(db, LEARNER, progress_path, current)
    session_key = db.connection.execute(
        "SELECT started_at,attempt_id FROM unified_sessions WHERE attempt_id=?",
        ("retained-gain",),
    ).fetchone()

    def expire_gain(database, subject, evidence_id, check):
        if evidence_id == newer[0]:
            raise TimeoutError("fixture direct deadline")
        return real_prove(database, subject, evidence_id, check)

    with monkeypatch.context() as deadline:
        deadline.setattr(refresh, "prove", expire_gain)
        turn()
    assert checkpoint(db, LEARNER, root)[1]["session"][:2] == list(session_key)
    assert observe(db, root, LEARNER, newer[0]) is None

    for day in range(26, 30):
        add_source(day)
        turn()
        if all(observe(db, root, LEARNER, evidence_id) for evidence_id in (old, newer[0])):
            break
    assert all(observe(db, root, LEARNER, evidence_id) for evidence_id in (old, newer[0]))
    assert checkpoint(db, LEARNER, root)[1]["before"] > newer[0]
    assert show(db, "retained-gain", LEARNER)["objective"] == "bounded_material_gain"

    # Restore the same source specifically from a real related-history reference.
    records, _ = bucket_entries(db, root, LEARNER, newer[0])
    records.pop(str(newer[0]))
    publish_bucket(db, root, LEARNER, newer[0], records)
    progress_path, current = checkpoint(db, LEARNER, root)
    current["lane"], current["related"] = 3, []
    save(db, LEARNER, progress_path, current)
    related_visits = []
    restored_by = []
    original_reference = worker.related_reference
    original_visit = worker._visit

    def record_visit(database, subject, project, state, lane, deadline):
        before = observe(database, project, subject, newer[0])
        result = original_visit(database, subject, project, state, lane, deadline)
        if before is None and observe(database, project, subject, newer[0]):
            restored_by.append(lane)
        return result

    def record_related(row, subject):
        reference = original_reference(row, subject)
        if reference and reference["id"] == newer[0]:
            related_visits.append(reference)
        return reference

    with monkeypatch.context() as references:
        references.setattr(worker, "related_reference", record_related)
        references.setattr(worker, "_visit", record_visit)
        for _ in range(15):
            turn()
            if related_visits and observe(db, root, LEARNER, newer[0]):
                break
    assert related_visits and observe(db, root, LEARNER, newer[0])
    assert restored_by == [3]
    assert checkpoint(db, LEARNER, root)[1]["before"] > newer[0]

    from chess_coach.capture_history_first import report as capture_history
    from chess_coach.capture_plan_history import latest as capture_latest

    def forbid_source_proof(*_args, **_kwargs):
        raise AssertionError("capture source proof ran during related history")

    with monkeypatch.context() as guard:
        guard.setattr(
            "chess_coach.material_opportunity_current.verified_witness", forbid_source_proof
        )
        guard.setattr("chess_coach.objective_capture_snapshot.judge", forbid_source_proof)
        before_read = db.connection.total_changes
        assert source_for_position(db, LEARNER, related_position) == original_source
        assert show(db, "related-active", LEARNER)["status"] == "active"
        assert show(db, "related-completed", LEARNER)["verification"]["status"] == "correct"
        history = capture_history(db, LEARNER, "capture")
        assert {item["attempt_id"] for item in history["items"]} >= {
            "related-active",
            "related-completed",
        }
        assert capture_latest(db, LEARNER, related_position, "capture")["status"] == "incomplete"
        app = create_app(
            db_path=path,
            project_root=root,
            subject=LEARNER,
            actor="fixture",
            corpus="capture",
            login="fixture",
            origin="https://coach.invalid",
        )
        import hashlib
        import sqlite3

        def learning_fingerprint():
            names = (
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
                "tactical_exposure_coverage",
                "tactical_exposures",
            )
            with sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True) as reader:
                rows = tuple(
                    (name, reader.execute(f"SELECT * FROM {name} ORDER BY rowid").fetchall())
                    for name in names
                )
            return hashlib.sha256(repr(rows).encode()).hexdigest()

        before_http = learning_fingerprint()
        client = app.test_client()
        page = client.get(
            "/plan/captures/history",
            base_url="https://coach.invalid",
            headers={"Tailscale-User-Login": "fixture"},
        )
        assert page.status_code == 200
        assert b"related-active" in page.data and b"related-completed" in page.data
        related_page = client.get(
            f"/decisions/{related_position}/related-captures",
            base_url="https://coach.invalid",
            headers={"Tailscale-User-Login": "fixture"},
        )
        assert related_page.status_code == 200 and b"Check my capture choice" in related_page.data
        assert learning_fingerprint() == before_http
        assert db.connection.total_changes == before_read
        assert not candidate_checks
    cli_result = fresh_cli(
        path,
        "related-captures",
        "--subject",
        LEARNER,
        "--position",
        str(related_position),
        "--corpus",
        "capture",
        "--project-root",
        str(root),
        source_guard=(owned_prompt, owned_move),
        proof_free_candidates=True,
    )
    assert json.loads(cli_result.stdout)["status"] == "available"
    for name, row in related_rows.items():
        current_row = db.connection.execute(
            "SELECT snapshot_hash,provenance_json FROM unified_sessions WHERE attempt_id=?", (name,)
        ).fetchone()
        assert dict(current_row) == row

    valid = [old, *newer[:-3]]
    for _ in range(15):
        turn()
        if all(observe(db, root, LEARNER, evidence_id) for evidence_id in valid):
            break
    assert len(valid) > 20 and all(observe(db, root, LEARNER, evidence_id) for evidence_id in valid)

    # The old due source is outside the latest raw page. Its bucket becoming
    # available after the scan must invalidate the saved continuation.
    records, _ = bucket_entries(db, root, LEARNER, old)
    records.pop(str(old))
    import chess_coach.curriculum_page as curriculum_page

    original_due = curriculum_page.due

    def publish_before_due(*args, **kwargs):
        publish_bucket(db, root, LEARNER, old, records)
        return original_due(*args, **kwargs)

    # A fresh due-only page watches files before the first due observation.
    with monkeypatch.context() as changing:
        changing.setattr(curriculum_page, "due", publish_before_due)
        with pytest.raises(ValueError, match="capture practice changed"):
            daily_plan(db, **single_args)
    assert counts == tuple(
        db.connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
        for table in ("unified_sessions", "unified_training_enrollments", "training_attempts")
    )
    assert observe(db, root, LEARNER, old) is None
    unavailable = daily_plan(db, **plan_args)
    assert all(item.get("item_id") != item_id for item in unavailable["items"])
    before_backfill = tuple(
        db.connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
        for table in ("unified_sessions", "unified_training_enrollments", "training_attempts")
    )
    for _ in range(15):
        turn()
        if observe(db, root, LEARNER, old):
            break
    assert observe(db, root, LEARNER, old)
    with pytest.raises(ValueError, match="capture practice changed"):
        daily_plan(db, cursor=unavailable["window_cursor"], **plan_args)
    assert before_backfill == tuple(
        db.connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
        for table in ("unified_sessions", "unified_training_enrollments", "training_attempts")
    )

    def forbidden(*_args, **_kwargs):
        raise AssertionError("capture source proof ran during a request")

    with monkeypatch.context() as guard:
        guard.setattr("chess_coach.material_opportunity_current.verified_witness", forbidden)
        guard.setattr("chess_coach.objective_capture_snapshot.judge", forbidden)
        from chess_coach.objective_capture_source import resolve

        for evidence_id in valid:
            assert (
                resolve(db, TARGET_VERSION, str(evidence_id), LEARNER)["objective"]
                == "capture_named_target"
            )
        due = daily_plan(db, subject=LEARNER, corpus_version="fixture", limit=1, project_root=root)
        assert due["items"][0]["kind"] == "due" and due["items"][0]["item_id"] == item_id
        app = create_app(
            db_path=path,
            project_root=root,
            subject=LEARNER,
            actor="fixture",
            corpus="fixture",
            login="fixture",
            origin="https://coach.invalid",
        )
        response = app.test_client().get(
            "/plan", base_url="https://coach.invalid", headers={"Tailscale-User-Login": "fixture"}
        )
        assert (
            response.status_code == 200
            and f'name="item_id" value="{item_id}"'.encode() in response.data
        )
        assert show(db, "retained-active", LEARNER)["objective"] == "capture_named_target"
        hint(db, "retained-active", LEARNER, event_id="hint")
        response = submit(db, "retained-active", LEARNER, event_id="answer", move="e1f1")
        assert response["status"] == "needs_verification"
        replay_before = tuple(
            db.connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
            for table in (
                "unified_session_events",
                "objective_requests",
                "training_attempts",
                "mastery_events",
            )
        )
        stored_response = db.connection.execute(
            "SELECT response_json FROM unified_session_events WHERE attempt_id=? AND event_id=?",
            ("retained-active", "answer"),
        ).fetchone()[0]
        assert submit(db, "retained-active", LEARNER, event_id="answer", move="e1f1") == response
        assert replay_before == tuple(
            db.connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
            for table in (
                "unified_session_events",
                "objective_requests",
                "training_attempts",
                "mastery_events",
            )
        )
        assert (
            db.connection.execute(
                "SELECT response_json FROM unified_session_events WHERE attempt_id=? AND event_id=?",
                ("retained-active", "answer"),
            ).fetchone()[0]
            == stored_response
        )
    # A due selection rechecks the same file scope inside the start transaction.
    from chess_coach import curriculum_capture_due_scope
    from tests.native_pair_probe import Forms

    client = app.test_client()
    headers = {"Tailscale-User-Login": "fixture"}
    page = client.get(
        "/plan?goal=capture&minutes=1", base_url="https://coach.invalid", headers=headers
    )
    parsed = Forms()
    parsed.feed(page.get_data(as_text=True))
    selected = next(form for form in parsed.forms if form.get("item_id") == str(item_id))
    real_finish = curriculum_capture_due_scope.finish
    records, _ = bucket_entries(db, root, LEARNER, old)
    records.pop(str(old))

    def replace_before_due_commit(database, scope):
        if database.connection.in_transaction and scope is not None:
            publish_bucket(database, root, LEARNER, old, records)
        return real_finish(database, scope)

    before_start = tuple(
        db.connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
        for table in ("unified_sessions", "unified_training_enrollments", "training_attempts")
    )
    with monkeypatch.context() as changing:
        changing.setattr(curriculum_capture_due_scope, "finish", replace_before_due_commit)
        refused = client.post(
            "/unified/start",
            data=selected,
            base_url="https://coach.invalid",
            headers=headers | {"Origin": "https://coach.invalid"},
        )
    assert refused.status_code == 400
    assert before_start == tuple(
        db.connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
        for table in ("unified_sessions", "unified_training_enrollments", "training_attempts")
    )
    for _ in range(15):
        turn()
        if observe(db, root, LEARNER, old):
            break
    assert observe(db, root, LEARNER, old)
    page = client.get(
        "/plan?goal=capture&minutes=1", base_url="https://coach.invalid", headers=headers
    )
    parsed = Forms()
    parsed.feed(page.get_data(as_text=True))
    selected = next(form for form in parsed.forms if form.get("item_id") == str(item_id))
    accepted = client.post(
        "/unified/start",
        data=selected,
        base_url="https://coach.invalid",
        headers=headers | {"Origin": "https://coach.invalid"},
    )
    assert accepted.status_code == 303

    cli_plan = json.loads(
        fresh_cli(
            path,
            "daily-plan",
            "fixture",
            "--subject",
            LEARNER,
            "--limit",
            "1",
            "--project-root",
            str(root),
        ).stdout
    )
    assert cli_plan["items"][0]["kind"] == "due" and cli_plan["items"][0]["item_id"] == item_id
    from chess_coach.curriculum_cursor_codec import decode_cursor

    assert decode_cursor(db, cli_plan["plan_selection_cursor"])["capture_selection"] is True
    with pytest.raises(ValueError, match="for due selection only"):
        daily_plan(
            db,
            subject=LEARNER,
            corpus_version="fixture",
            limit=1,
            cursor=cli_plan["plan_selection_cursor"],
            project_root=root,
        )
    before_wrong_scope = tuple(
        db.connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
        for table in ("unified_sessions", "unified_training_enrollments")
    )
    wrong_scope = fresh_cli(
        path,
        "start-unified",
        "--attempt",
        "wrong-scope",
        "--subject",
        LEARNER,
        "--source",
        "own-game",
        "--version",
        TARGET_VERSION,
        "--key",
        str(old),
        "--training",
        "--training-item-id",
        str(item_id),
        "--project-root",
        str(root),
        f"--plan-cursor={cli_plan['plan_selection_cursor']}",
        "--plan-corpus",
        "other",
        check=False,
    )
    assert wrong_scope.returncode != 0
    assert "capture practice changed; restart the plan" in wrong_scope.stderr
    assert before_wrong_scope == tuple(
        db.connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
        for table in ("unified_sessions", "unified_training_enrollments")
    )
    cli_start = json.loads(
        fresh_cli(
            path,
            "start-unified",
            "--attempt",
            "retained-cli",
            "--subject",
            LEARNER,
            "--source",
            "own-game",
            "--version",
            TARGET_VERSION,
            "--key",
            str(old),
            "--training",
            "--training-item-id",
            str(item_id),
            "--project-root",
            str(root),
            f"--plan-cursor={cli_plan['plan_selection_cursor']}",
            "--plan-corpus",
            "fixture",
        ).stdout
    )
    assert cli_start["objective"] == "capture_named_target"

    # Renewal must bind files before its reoffer scan, even with no priority yet.
    import chess_coach.curriculum_window_renew as renewal

    renewal_page = daily_plan(db, **single_args)
    renewal_history = renewal.history
    records, _ = bucket_entries(db, root, LEARNER, old)
    records.pop(str(old))

    def replace_during_reoffer(*args, **kwargs):
        publish_bucket(db, root, LEARNER, old, records)
        return renewal_history(*args, **kwargs)

    before_renew = tuple(
        db.connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
        for table in ("unified_sessions", "unified_training_enrollments", "training_attempts")
    )
    with monkeypatch.context() as changing:
        changing.setattr(renewal, "history", replace_during_reoffer)
        with pytest.raises(ValueError, match="capture practice changed"):
            daily_plan(db, cursor=renewal_page["window_cursor"], renew=True, **single_args)
    assert before_renew == tuple(
        db.connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
        for table in ("unified_sessions", "unified_training_enrollments", "training_attempts")
    )
    for _ in range(15):
        turn()
        if observe(db, root, LEARNER, old):
            break
    assert observe(db, root, LEARNER, old)

    # Publication after history but before window initialization must not become the baseline.
    import chess_coach.curriculum_window_plan as window_plan

    renewal_page = daily_plan(db, **single_args)
    real_state = window_plan.state
    records, _ = bucket_entries(db, root, LEARNER, old)
    records.pop(str(old))

    def replace_after_renewal(*args, **kwargs):
        value = real_state(*args, **kwargs)
        publish_bucket(db, root, LEARNER, old, records)
        return value

    with monkeypatch.context() as changing:
        changing.setattr(window_plan, "state", replace_after_renewal)
        with pytest.raises(ValueError, match="capture practice changed"):
            daily_plan(db, cursor=renewal_page["window_cursor"], renew=True, **single_args)
    assert before_renew == tuple(
        db.connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
        for table in ("unified_sessions", "unified_training_enrollments", "training_attempts")
    )
    for _ in range(15):
        turn()
        if observe(db, root, LEARNER, old):
            break
    assert observe(db, root, LEARNER, old)

    # A genuinely signed old-shape cursor cannot prove an earlier due observation.
    from chess_coach.curriculum_priority_cursor import CAPTURE_POLICY, LEGACY_CAPTURE_POLICY
    from chess_coach.curriculum_window_cursor import decode as decode_window
    from chess_coach.curriculum_window_cursor import encode as encode_window

    legacy_page = daily_plan(db, **single_args)
    legacy = decode_window(db, legacy_page["window_cursor"])
    assert legacy["state"]["priority"] is None
    legacy["state"]["priority_policy"] = LEGACY_CAPTURE_POLICY
    legacy["state"].pop("capture_files")
    legacy["state"].pop("capture_selection")
    legacy_token = encode_window(db, legacy)
    legacy_args: dict[str, Any] = {**plan_args, "limit": 1, "cursor": legacy_token}
    with pytest.raises(ValueError, match="capture practice changed"):
        daily_plan(db, **legacy_args)
    renewed = daily_plan(db, renew=True, **legacy_args)
    assert decode_window(db, renewed["window_cursor"])["state"]["priority_policy"] == CAPTURE_POLICY
    assert process(db, LEARNER)["outcomes"] == {"incorrect": 1}
    active = show(db, "retained-active", LEARNER)
    assert active["verification"]["status"] == "incorrect"
    assert active["learning"]["assistance"] == "assisted"
    assert (
        db.connection.execute(
            "SELECT snapshot_hash FROM unified_sessions WHERE attempt_id=?", ("retained-active",)
        ).fetchone()[0]
        == snapshot_before
    )
    assert (
        tuple(
            db.connection.execute("SELECT * FROM training_items WHERE id=?", (item_id,)).fetchone()
        )
        == item_before
    )

    # Request-side hint, submit and replay must not re-prove the owned source.
    with monkeypatch.context() as guard:
        guard.setattr(
            "chess_coach.material_opportunity_current.verified_witness", forbid_source_proof
        )
        guard.setattr("chess_coach.objective_capture_snapshot.judge", forbid_source_proof)
        hint(db, "related-active", LEARNER, event_id="hint")
        related_reply = submit(db, "related-active", LEARNER, event_id="answer", move="d1d4")
    # Answer verification is allowed to run its normal separate proof.
    assert process(db, LEARNER)["outcomes"] == {"correct": 1}
    with monkeypatch.context() as guard:
        guard.setattr(
            "chess_coach.material_opportunity_current.verified_witness", forbid_source_proof
        )
        guard.setattr("chess_coach.objective_capture_snapshot.judge", forbid_source_proof)
        assert show(db, "related-active", LEARNER)["verification"]["status"] == "correct"
        assert (
            submit(db, "related-active", LEARNER, event_id="answer", move="d1d4") == related_reply
        )

    # A same-time insertion after the pass began is outside its rowid horizon.
    import chess_coach.unified_sessions as sessions
    from chess_coach.capture_certificate_reference_page import session as session_page

    with monkeypatch.context() as clock:
        clock.setattr(sessions, "now", lambda: "2099-01-01T00:00:00+00:00")
        for attempt in ("frontier-first", "frontier-later"):
            start(
                db,
                attempt_id=attempt,
                subject=LEARNER,
                source_type="own-game",
                version=TARGET_VERSION,
                key=str(old),
            )
            if attempt == "frontier-first":
                first, frontier = session_page(db, LEARNER, [])
                assert first["attempt_id"] == attempt
        following, _ = session_page(db, LEARNER, frontier)
        assert following is None or following["attempt_id"] != "frontier-later"

    # A real revoked direct reference must remain unavailable without blocking
    # another already-admitted due source from being restored.
    revoked = newer[1]
    start(
        db,
        attempt_id="retained-revoked",
        subject=LEARNER,
        source_type="own-game",
        version=TARGET_VERSION,
        key=str(revoked),
    )
    review_evidence(db, revoked, decision="reject", actor="fixture")
    with pytest.raises(ValueError, match="practice source unavailable or stale"):
        show(db, "retained-revoked", LEARNER)
    records, _ = bucket_entries(db, root, LEARNER, old)
    records.pop(str(old))
    publish_bucket(db, root, LEARNER, old, records)
    visited = []
    original_reference = worker.session_reference

    def record_reference(row, subject):
        reference = original_reference(row, subject)
        if row["attempt_id"] == "retained-revoked":
            visited.append(reference)
        return reference

    with monkeypatch.context() as references:
        references.setattr(worker, "session_reference", record_reference)
        for _ in range(8):
            turn()
            if visited and observe(db, root, LEARNER, old):
                break
    assert visited and visited[0]["id"] == revoked
    assert observe(db, root, LEARNER, old)
    assert observe(db, root, LEARNER, revoked) is None
    with pytest.raises(ValueError, match="practice source unavailable or stale"):
        show(db, "retained-revoked", LEARNER)

    # A later valid review creates a new source identity; it does not rewrite
    # the original session or make its old snapshot current again.
    review_evidence(db, revoked, decision="accept", actor="fixture")
    for _ in range(15):
        turn()
        if observe(db, root, LEARNER, revoked):
            break
    assert observe(db, root, LEARNER, revoked)
    start(
        db,
        attempt_id="retained-refreshed",
        subject=LEARNER,
        source_type="own-game",
        version=TARGET_VERSION,
        key=str(revoked),
    )
    with pytest.raises(ValueError, match="practice source unavailable or stale"):
        show(db, "retained-revoked", LEARNER)

    # A genuine scheduled source with no session can only use its schedule lane.
    from chess_coach.training import create_training_item
    from chess_coach.unified_training_item import source_ref
    from chess_coach.unified_training_owned_capture import SOURCE

    schedule_source = newer[2]
    current_snapshot = observe(db, root, LEARNER, schedule_source)[2]["snapshot"]
    schedule_item = create_training_item(
        db,
        source_type=SOURCE,
        source_ref=source_ref(
            LEARNER, TARGET_VERSION, str(schedule_source), snapshot_hash(current_snapshot)
        ),
        skill="hanging_piece",
        operation="execute",
    )
    assert (
        db.connection.execute(
            """SELECT 1 FROM unified_sessions WHERE subject=? AND source_type='own-game'
        AND source_key=?""",
            (LEARNER, str(schedule_source)),
        ).fetchone()
        is None
    )

    from chess_coach.recurrence_cursor import MAX_ID

    records, _ = bucket_entries(db, root, LEARNER, schedule_source)
    records.pop(str(schedule_source))
    publish_bucket(db, root, LEARNER, schedule_source, records)
    progress_path, current = checkpoint(db, LEARNER, root)
    current["before"], current["lane"], current["schedule"] = MAX_ID, 2, []
    save(db, LEARNER, progress_path, current)
    schedules = []
    original_schedule = worker.schedule_reference

    def record_schedule(row, subject):
        reference = original_schedule(row, subject)
        if row["id"] == schedule_item:
            schedules.append(reference)
        return reference

    with monkeypatch.context() as references:
        references.setattr(worker, "schedule_reference", record_schedule)
        for _ in range(8):
            turn()
            if schedules and observe(db, root, LEARNER, schedule_source):
                break
    assert schedules and schedules[0]["id"] == schedule_source
    assert observe(db, root, LEARNER, schedule_source)
    assert checkpoint(db, LEARNER, root)[1]["before"] > schedule_source

    # Over twenty actual nontraining sessions retain distinct source bindings;
    # both start and show must use the worker certificates without proof calls.
    with monkeypatch.context() as guard:
        guard.setattr("chess_coach.material_opportunity_current.verified_witness", forbidden)
        guard.setattr("chess_coach.objective_capture_snapshot.judge", forbidden)
        for evidence_id in valid:
            attempt = f"retained-many-{evidence_id}"
            start(
                db,
                attempt_id=attempt,
                subject=LEARNER,
                source_type="own-game",
                version=TARGET_VERSION,
                key=str(evidence_id),
            )
            stored = db.connection.execute(
                "SELECT snapshot_hash FROM unified_sessions WHERE attempt_id=?", (attempt,)
            ).fetchone()[0]
            assert stored == snapshot_hash(observe(db, root, LEARNER, evidence_id)[2]["snapshot"])
            assert show(db, attempt, LEARNER)["objective"] == "capture_named_target"
    assert len(set(valid)) > 20
    review_evidence(db, newer[0], decision="reject", actor="fixture")
    before_refusal = db.connection.total_changes
    with pytest.raises(ValueError, match="practice source unavailable or stale"):
        show(db, "related-active", LEARNER)
    assert capture_latest(db, LEARNER, related_position, "capture")["status"] == "stale"
    assert db.connection.total_changes == before_refusal
    db.close()

    # An unrelated project database outside the private data directory still plans normally.
    from chess_coach.db import Database

    outside = tmp_path / "outside-capture-project"
    outside.mkdir()
    other = outside / "coach.sqlite"
    other_db = Database(other)
    other_db.initialize()
    other_db.close()
    unrelated = create_app(
        db_path=other,
        project_root=outside,
        subject=LEARNER,
        actor="fixture",
        corpus="fixture",
        login="fixture",
        origin="https://coach.invalid",
    )
    unrelated_page = unrelated.test_client().get(
        "/plan?goal=capture&minutes=1",
        base_url="https://coach.invalid",
        headers={"Tailscale-User-Login": "fixture"},
    )
    assert unrelated_page.status_code == 200
    assert not (outside / ".runtime" / "data").exists()
