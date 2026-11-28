"""Back-rank claims require legal proof and never qualify for mastery."""

import pytest

from chess_coach.back_rank_auto import process_decision
from chess_coach.evidence_review import inspect_evidence, review_evidence
from chess_coach.mastery import update_mastery
from chess_coach.mate_auto import process_decision as process_mate
from tests.test_mate_proof import owned_game

DEFENSE = "r5k1/8/8/8/2N5/8/5PPP/6K1 w - - 0 1"
ATTACK = "6k1/5ppp/8/8/8/8/8/R5K1 w - - 0 1"


def test_automatic_defense_is_provisional_replayable_and_closed(tmp_path, monkeypatch):
    db = owned_game(tmp_path / "back-rank.sqlite", monkeypatch, fen=DEFENSE, move="g3")
    process_mate(db, 1, "fixture_a")
    result = process_decision(db, 1, "fixture_a")
    assert result["observation_status"] == "opportunity"
    assert process_decision(db, 1, "fixture_a")["replayed"]
    row = db.connection.execute(
        "SELECT id,outcome FROM evidence_mappings WHERE skill='back_rank' AND operation='prevent'"
    ).fetchone()
    assert row["outcome"] == "success"
    evidence = inspect_evidence(db, row["id"])
    assert evidence["review_status"] == "unreviewed"
    review_evidence(db, row["id"], decision="accept", actor="reviewer")
    mastery = update_mastery(db, skill="back_rank", operation="prevent", subject="fixture_a")
    assert mastery["status"] == "insufficient"
    assert mastery["exclusions"]["back_rank_family_unvalidated"] == 1
    db.connection.execute("UPDATE pipeline_stages SET status='pending' WHERE stage='analysis'")
    db.connection.commit()
    with pytest.raises(ValueError):
        process_decision(db, 1, "fixture_a")
    db.close()
    _prerequisite_workflow(tmp_path, monkeypatch)


def test_back_rank_practice_ownership_reveal_and_safe_line(tmp_path, monkeypatch):
    _created_backrank_public_workflow(tmp_path, monkeypatch)
    from chess_coach.back_rank_practice import VERSION, list_candidates
    from chess_coach.coaching_practice import choices
    from chess_coach.lesson_mechanisms import describe
    from chess_coach.lesson_source import source
    from chess_coach.objective_defense_source import VERSION as DEFENSE_VERSION
    from chess_coach.unified_session_events import reveal, show, submit
    from chess_coach.unified_sessions import start

    failure_db = owned_game(
        tmp_path / "coaching-defense.sqlite", monkeypatch, fen=DEFENSE, move="Nb6"
    )
    process_mate(failure_db, 1, "fixture_a")
    process_decision(failure_db, 1, "fixture_a")
    evidence = failure_db.connection.execute(
        "SELECT id FROM evidence_mappings WHERE skill='back_rank' AND operation='prevent'"
    ).fetchone()[0]
    inspected = source(failure_db, "fixture_a", {"id": evidence, "position_id": 1})
    assert inspected is not None and inspected["evidence"]["outcome"] == "failure"
    fact = inspected["evidence"]["facts"][0]
    example = describe(inspected)
    lesson = {
        "skill": "back_rank",
        "operation": "prevent",
        "family": inspected["evidence"]["mapping_producer"],
        "source_version": fact["detector_version"],
        "examples": [dict(example, evidence_id=0), example],
    }
    selected = choices(failure_db, "fixture_a", {"groups": [{"lesson": lesson}]})[0]
    assert selected["version"] == DEFENSE_VERSION and selected["key"] == str(evidence)
    assert selected["kind"] == "back_rank_defense"
    state = start(
        failure_db,
        attempt_id="defense",
        subject="fixture_a",
        source_type="own-game",
        version=selected["version"],
        key=selected["key"],
    )
    assert state["objective"] == "avoid_immediate_mate"
    failure_db.connection.execute(
        "UPDATE pipeline_stages SET status='pending' WHERE stage='analysis'"
    )
    failure_db.connection.commit()
    assert choices(failure_db, "fixture_a", {"groups": [{"lesson": lesson}]}) == [None]
    failure_db.close()

    db = owned_game(tmp_path / "practice.sqlite", monkeypatch, fen=DEFENSE, move="g3")
    process_mate(db, 1, "fixture_a")
    process_decision(db, 1, "fixture_a")
    item = list_candidates(db, "fixture_a")["candidates"][0]
    assert item["objective"] == "back_rank_defense"
    with pytest.raises(ValueError):
        start(
            db,
            attempt_id="foreign",
            subject="fixture_b",
            source_type="own-game",
            version=VERSION,
            key=item["key"],
        )
    state = start(
        db,
        attempt_id="own",
        subject="fixture_a",
        source_type="own-game",
        version=VERSION,
        key=item["key"],
    )
    assert "lines" not in state and "source_key" not in state
    assert show(db, "own", "fixture_a")["status"] == "active"
    answer = reveal(db, "own", "fixture_a", event_id="reveal")
    assert answer["hints_used"] == 1
    assert reveal(db, "own", "fixture_a", event_id="reveal") == answer
    move = answer["revealed_line"].split()[0]
    done = submit(db, "own", "fixture_a", event_id="move", move=move)
    assert done["status"] == "line_completed"
    assert db.connection.execute("SELECT COUNT(*) FROM evidence_review_events").fetchone()[0] == 0
    db.connection.execute("UPDATE pipeline_stages SET status='pending' WHERE stage='analysis'")
    db.connection.commit()
    with pytest.raises(ValueError):
        show(db, "own", "fixture_a")

    db.close()
    for black in (False, True):
        for created in (False, True):
            _related_defense_workflow(monkeypatch, black, created)


def _related_defense_workflow(monkeypatch, black, created):
    import contextlib
    import io
    import json
    import re

    import chess
    import chess.pgn

    from chess_coach import web_related_backrank as web
    from chess_coach.cli_parser import build_parser
    from chess_coach.cli_related_commands import COMMANDS
    from chess_coach.evidence_review import inspect_evidence
    from chess_coach.ingest import ingest_pgn
    from chess_coach.lesson_mechanisms import describe
    from chess_coach.lesson_source import source
    from chess_coach.related_backrank_defense import preview, start_related
    from chess_coach.unified_session_events import show, submit
    from chess_coach.unified_sessions import start as start_corpus
    from chess_coach.web import create_app

    with monkeypatch.context() as patch:
        position = "r5k1/8/8/8/N7/8/5PPP/6K1 w - - 0 1" if created else DEFENSE
        fen = chess.Board(position).mirror().fen() if black else position
        subject, bad = ("fixture_b", "Nb3") if black else ("fixture_a", "Nb6")
        db = owned_game(":memory:", patch, fen=fen, move=bad)
        process_mate(db, 1, subject)
        process_decision(db, 1, subject)
        evidence = db.connection.execute(
            "SELECT id FROM evidence_mappings WHERE skill=? AND operation=?",
            ("back_rank", "prevent"),
        ).fetchone()[0]
        assert inspect_evidence(db, evidence)["backrank_defense_transfer"]
        from chess_coach.curriculum_prerequisite_source import context as prerequisite_context

        assert prerequisite_context(db, subject, 20, lambda: None)["state"] == "available"
        assert describe(source(db, subject, {"id": evidence, "position_id": 1}))[
            "backrank_defense_transfer"
        ]
        db.connection.execute(
            "INSERT INTO puzzle_corpora(version,source,checksum,state) VALUES(?,?,?,?)",
            ("test", "fixture", "checksum", "staging"),
        )
        corpus = db.connection.execute("SELECT id FROM puzzle_corpora").fetchone()[0]
        board = chess.Board(position)
        board.turn = chess.BLACK
        board.set_piece_at(chess.H7, chess.Piece(chess.PAWN, chess.BLACK))
        if black:
            board = board.mirror()
        setup, good = ("h2h3", "g7g6") if black else ("h7h6", "g2g3")
        wrong = ("a5b3" if black else "a4b6") if created else ("c5b3" if black else "c4b6")
        candidates = [("good", good, board, setup), ("wrong", wrong, board, setup)]
        exact = chess.Board(position)
        exact.turn = chess.BLACK
        exact.remove_piece_at(chess.A8)
        exact.set_piece_at(chess.A7, chess.Piece(chess.ROOK, chess.BLACK))
        exact.set_piece_at(chess.A8, chess.Piece(chess.KNIGHT, chess.WHITE))
        if black:
            exact = exact.mirror()
        candidates.append(("00-exact", good, exact, "a2a1" if black else "a7a8"))
        for index, file in enumerate("bcde"):
            familiar_board = board.copy()
            square = chess.parse_square(file + ("2" if black else "7"))
            familiar_board.set_piece_at(square, chess.Piece(chess.PAWN, board.turn))
            candidates.append((f"00-seen-{index}", good, familiar_board, setup))
            if index == 0:
                indexed_board = familiar_board
        for key, move, candidate_board, candidate_setup in candidates:
            db.connection.execute(
                """INSERT INTO puzzles(puzzle_id,corpus_id,fen,source,solution,rating,
                rating_deviation,themes_json,objective) VALUES(?,?,?,?,?,?,?,?,?)""",
                (
                    key,
                    corpus,
                    candidate_board.fen(),
                    "https://example.invalid",
                    candidate_setup + " " + move,
                    1200,
                    80,
                    "[]",
                    "unknown",
                ),
            )
            db.connection.execute(
                "INSERT INTO puzzle_themes VALUES(?,?,?,?)", (corpus, key, "defensiveMove", 1200)
            )
        db.connection.execute("UPDATE puzzle_corpora SET state=?", ("ready",))
        db.connection.commit()
        indexed_game = chess.pgn.Game()
        indexed_game.setup(indexed_board)
        indexed_game.headers["White"] = subject if not black else "fixture_opponent"
        indexed_game.headers["Black"] = subject if black else "fixture_opponent"
        indexed_game.add_variation(indexed_board.parse_uci(setup))
        ingest_pgn(db, str(indexed_game))
        for index in range(1, 4):
            start_corpus(
                db,
                attempt_id=f"seen-{index}",
                subject=subject,
                source_type="corpus",
                version="test",
                key=f"00-seen-{index}",
            )
        transfer = preview(db, subject, evidence, "test")
        assert len(transfer["items"]) == 1 and transfer["defense_scan"]["proofs"] == 2
        assert transfer["threat_origin"] == ("newly_allowed" if created else "anchored_preexisting")
        if created:
            assert transfer["source_contrast"]["san"] == bad
            from chess_coach.back_rank_defense import observe
            from chess_coach.related_backrank_defense_proof import _new_mates

            prompt = board.copy()
            prompt.push_uci(setup)
            outcome = observe(prompt, prompt.parse_uci(good), include_candidates=True)
            bad_choice = next(row for row in outcome["alternatives"] if row["move"]["uci"] == wrong)
            assert _new_mates(bad_choice, outcome["pre_move_candidates"])
            assert not _new_mates(bad_choice, [bad_choice["back_rank"][0]["move"]["uci"]])
            mixed = chess.Board("rq4k1/8/8/8/N7/8/5PPP/6K1 w - - 0 1")
            if black:
                mixed = mixed.mirror()
            mixed_result = observe(mixed, mixed.parse_uci(good), include_candidates=True)
            mixed_bad = "a5c4" if black else "a4c5"
            mixed_choice = next(
                row for row in mixed_result["alternatives"] if row["move"]["uci"] == mixed_bad
            )
            mates = {mate["move"]["uci"] for mate in mixed_choice["back_rank"]}
            before = set(mixed_result["pre_move_candidates"])
            assert mates & before and mates - before
            assert not _new_mates(mixed_choice, before)
        assert transfer["defense_scan"]["familiar"] == 4
        assert transfer["defense_scan"]["exact_source"] == 1
        assert not transfer["defense_scan"]["truncated"]
        assert "defense_witness" not in transfer["items"][0]
        with pytest.raises(ValueError):
            start_related(
                db,
                attempt_id="bad",
                subject=subject,
                evidence_id=evidence,
                corpus_version="test",
                reference="tampered",
            )

        patch.setattr(web, "database", lambda: db)
        app = create_app(
            db_path=":memory:",
            subject=subject,
            actor="fixture",
            corpus="test",
            login="fixture",
            origin="https://coach.invalid",
        )
        client = app.test_client()
        headers = {"Tailscale-User-Login": "fixture"}
        url = f"/evidence/{evidence}/related-backrank-defenses"
        assert client.get(url).status_code == 403
        page = client.get(url, base_url="https://coach.invalid", headers=headers)
        assert page.status_code == 200 and b"Practice this defense" in page.data
        if created:
            assert (
                bad.encode() in page.data and b"absent from the bounded pre-move probe" in page.data
            )
        assert not re.search(
            rb"(?<![A-Za-z0-9_-])" + good.encode() + rb"(?![A-Za-z0-9_-])", page.data
        )
        parser = build_parser()
        args = parser.parse_args(
            [
                "related-backrank-defenses",
                "--subject",
                subject,
                "--evidence",
                str(evidence),
                "--corpus",
                "test",
            ]
        )
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            COMMANDS[args.command](db, args)
        listing = json.loads(output.getvalue())
        assert len(listing["items"]) == 1

        if black:
            args = parser.parse_args(
                [
                    "start-related-backrank-defense",
                    "--subject",
                    subject,
                    "--evidence",
                    str(evidence),
                    "--corpus",
                    "test",
                    "--attempt",
                    "cli-defense",
                    "--reference",
                    listing["items"][0]["reference"],
                ]
            )
            with contextlib.redirect_stdout(io.StringIO()):
                COMMANDS[args.command](db, args)
            attempt = "cli-defense"
        else:
            with client.session_transaction(base_url="https://coach.invalid") as session:
                csrf = session["csrf"]
            response = client.post(
                url + "/start",
                base_url="https://coach.invalid",
                headers=headers | {"Origin": "https://coach.invalid"},
                data={"csrf": csrf, "reference": transfer["items"][0]["reference"]},
            )
            assert response.status_code == 303
            attempt = response.location.rsplit("/", 1)[-1]
        state = show(db, attempt, subject)
        assert state["status"] == "active" and "backrank_defense_witness" not in state
        assert state["related_backrank_defense_origin"] == transfer["threat_origin"]
        from chess_coach.related_backrank_contract import CREATED_DEFENSE_VERSION, DEFENSE_VERSION

        row = db.connection.execute(
            "SELECT provenance_json FROM unified_sessions WHERE attempt_id=?", (attempt,)
        ).fetchone()
        binding = json.loads(row[0])["related_backrank_defense"]
        assert binding["rank_version"] == (CREATED_DEFENSE_VERSION if created else DEFENSE_VERSION)
        done = submit(db, attempt, subject, event_id="answer", move=good)
        assert done["status"] == "line_completed" and "backrank_defense_witness" in done
        review_evidence(db, evidence, decision="reject", actor="fixture")
        with pytest.raises(ValueError):
            show(db, attempt, subject)
        args = parser.parse_args(
            [
                "related-backrank-defenses",
                "--subject",
                subject,
                "--evidence",
                str(evidence),
                "--corpus",
                "test",
            ]
        )
        with pytest.raises(SystemExit, match="unavailable or stale"):
            COMMANDS[args.command](db, args)
        db.close()


def _prerequisite_workflow(tmp_path, monkeypatch):
    import json
    import os
    from datetime import UTC, datetime, timedelta

    import chess

    from chess_coach.curriculum import daily_plan
    from chess_coach.curriculum_cursor_codec import decode_cursor
    from chess_coach.deep_selection_source import learner_key
    from chess_coach.fact_fingerprint import digest
    from chess_coach.tactical_study_exposure import VERSION as EXPOSURE_VERSION
    from chess_coach.unified_session_events import submit
    from chess_coach.unified_sessions import start
    from chess_coach.web import create_app
    from tests.test_unified_sessions import token

    root = tmp_path / "diagnostic-project"
    data = root / ".runtime" / "data"
    planning = root / ".runtime" / "planning"
    data.mkdir(parents=True, mode=0o700)
    planning.mkdir(mode=0o700)
    path = data / "synthetic.sqlite"
    db = owned_game(path, monkeypatch, fen=DEFENSE, move="Nb6")
    process_mate(db, 1, "fixture_a")
    process_decision(db, 1, "fixture_a")
    evidence = db.connection.execute(
        "SELECT id FROM evidence_mappings WHERE skill='back_rank' AND operation='prevent'"
    ).fetchone()[0]
    corpus = db.connection.execute(
        "INSERT INTO puzzle_corpora(version,source,checksum,state) "
        "VALUES('diagnostic','fixture','checksum','staging')"
    ).lastrowid
    for name in ("a-nonmate", "b-nonmate"):
        db.connection.execute(
            """INSERT INTO puzzles(puzzle_id,corpus_id,fen,source,solution,rating,
            rating_deviation,themes_json,objective)
            VALUES(?,?,?,'fixture','e2e4 e7e5',1100,80,'[]','unknown')""",
            (name, corpus, chess.STARTING_FEN),
        )
    base = chess.Board("7k/1p6/6K1/2Q5/8/8/8/8 b - - 17 14")
    for index, name in enumerate(("diag", "z0", "z1", "z2")):
        board = base.copy()
        if index:
            board.set_piece_at(
                chess.parse_square(f"{chr(96 + index)}2"), chess.Piece(chess.PAWN, chess.WHITE)
            )
        db.connection.execute(
            """INSERT INTO puzzles(puzzle_id,corpus_id,fen,source,solution,rating,
            rating_deviation,themes_json,objective)
            VALUES(?,?,?,'fixture','b7b6 c5f8',1200,80,'[]','unknown')""",
            (name, corpus, board.fen()),
        )
    db.connection.execute("UPDATE puzzle_corpora SET state='ready' WHERE id=?", (corpus,))
    db.connection.commit()
    now = datetime.now(UTC)
    while now.date().toordinal() % 3 != 2:
        now -= timedelta(days=1)
    first = daily_plan(
        db, subject="fixture_a", corpus_version="diagnostic", scan_limit=1, as_of=now
    )
    assert first["prerequisite"]["state"] == "available"
    assert first["prerequisite"]["review"] == "unreviewed"
    assert first["prerequisite"]["mate_evidence"] == "unknown"
    state = decode_cursor(db, first["next_cursor"])
    assert state["v"] == 8 and len(state["prerequisite_scope"]) == 64
    assert "fixture_a" not in first["next_cursor"]
    from chess_coach import curriculum_prerequisite_source as prerequisite_source

    with monkeypatch.context() as patch:
        edges = tuple(
            edge
            for edge in prerequisite_source.EDGES
            if edge != ("mate_in_one", "back_rank_mate", "requires")
        )
        patch.setattr(prerequisite_source, "EDGES", edges)
        with pytest.raises(ValueError, match="prerequisite relation"):
            daily_plan(db, subject="fixture_a", corpus_version="diagnostic")
    foreign = daily_plan(db, subject="fixture_b", corpus_version="diagnostic")
    assert foreign["prerequisite"]["state"] != "available"

    review_evidence(db, evidence, decision="accept", actor="fixture")
    with pytest.raises(ValueError, match="sources changed"):
        daily_plan(
            db,
            subject="fixture_a",
            corpus_version="diagnostic",
            scan_limit=1,
            as_of=now,
            cursor=first["next_cursor"],
        )
    accepted = daily_plan(db, subject="fixture_a", corpus_version="diagnostic")
    assert accepted["prerequisite"]["review"] == "accepted"
    diagnostic = next(item for item in accepted["items"] if item.get("prerequisite_token"))
    assert diagnostic["puzzle_id"] == "diag" and diagnostic["unified_training"]
    assert "not" in diagnostic["reason"] and "mastery" in diagnostic["reason"]

    app = create_app(
        db_path=path,
        subject="fixture_a",
        actor="fixture",
        corpus="diagnostic",
        login="fixture-login",
        origin="https://coach.invalid",
    )
    client = app.test_client()
    headers = {"Tailscale-User-Login": "fixture-login"}
    page = client.get("/plan", base_url="https://coach.invalid", headers=headers)
    assert page.status_code == 200 and b"Optional mate-in-one recognition practice" in page.data
    form = {
        "csrf": token(page, "csrf"),
        "source_type": "corpus",
        "version": "diagnostic",
        "key": "diag",
        "goal": "mate_in_one",
        "training": "1",
        "prerequisite_token": diagnostic["prerequisite_token"],
    }

    # A possible Study send is file-backed, so a DB revision alone cannot
    # establish that this previously offered diagnostic is still unexposed.
    artifact = "a" * 64
    intent = {
        "course_sha256": artifact,
        "chapters": ["pending"],
        "tactical_delivery": {
            "version": EXPOSURE_VERSION,
            "owner": learner_key("fixture_a"),
            "chapters": {
                "0": {
                    "positions": [digest(diagnostic["prompt_key"])],
                    "pending_at": datetime.now(UTC).isoformat(),
                    "verified_at": None,
                }
            },
        },
    }
    intent_path = planning / f"tactical-study-{artifact}-intent.json"
    fd = os.open(intent_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as stream:
        json.dump(intent, stream)
    stale_exposure = client.post(
        "/unified/start",
        base_url="https://coach.invalid",
        headers=headers | {"Origin": "https://coach.invalid"},
        data=form,
    )
    assert stale_exposure.status_code == 400
    assert db.connection.execute("SELECT count(*) FROM unified_sessions").fetchone()[0] == 0
    revised = daily_plan(db, subject="fixture_a", corpus_version="diagnostic")
    replacement = next(item for item in revised["items"] if item.get("prerequisite_token"))
    assert replacement["puzzle_id"] != "diag"
    form.update(key=replacement["puzzle_id"], prerequisite_token=replacement["prerequisite_token"])
    review_evidence(db, evidence, decision="reject", actor="fixture")
    revoked = client.post(
        "/unified/start",
        base_url="https://coach.invalid",
        headers=headers | {"Origin": "https://coach.invalid"},
        data=form,
    )
    assert revoked.status_code == 400
    assert db.connection.execute("SELECT count(*) FROM unified_sessions").fetchone()[0] == 0
    review_evidence(db, evidence, decision="accept", actor="fixture")
    current = daily_plan(db, subject="fixture_a", corpus_version="diagnostic")
    replacement = next(item for item in current["items"] if item.get("prerequisite_token"))
    form.update(key=replacement["puzzle_id"], prerequisite_token=replacement["prerequisite_token"])
    db.connection.execute("UPDATE pipeline_stages SET status='pending' WHERE stage='analysis'")
    db.connection.commit()
    stale_source = client.post(
        "/unified/start",
        base_url="https://coach.invalid",
        headers=headers | {"Origin": "https://coach.invalid"},
        data=form,
    )
    assert stale_source.status_code == 400
    assert db.connection.execute("SELECT count(*) FROM unified_sessions").fetchone()[0] == 0
    db.connection.execute("UPDATE pipeline_stages SET status='complete' WHERE stage='analysis'")
    db.connection.commit()
    current = daily_plan(db, subject="fixture_a", corpus_version="diagnostic")
    replacement = next(item for item in current["items"] if item.get("prerequisite_token"))
    form.update(key=replacement["puzzle_id"], prerequisite_token=replacement["prerequisite_token"])
    posted = client.post(
        "/unified/start",
        base_url="https://coach.invalid",
        headers=headers | {"Origin": "https://coach.invalid"},
        data=form,
    )
    assert posted.status_code == 303
    attempt = posted.location.rstrip("/").rsplit("/", 1)[-1]
    result = submit(db, attempt, "fixture_a", event_id="answer", move="c5f8")["learning"]
    assert result["outcome"] == "success" and result["rating"] == "good"
    assert (
        db.connection.execute(
            "SELECT human_validated FROM evidence_mappings WHERE id=?", (result["evidence_id"],)
        ).fetchone()[0]
        == 0
    )
    due = daily_plan(
        db,
        subject="fixture_a",
        corpus_version="diagnostic",
        as_of=datetime.now(UTC) + timedelta(days=2),
    )
    assert due["items"][0]["kind"] == "due"
    assert any(item.get("item_id") == result["item_id"] for item in due["items"])
    review_evidence(db, result["evidence_id"], decision="accept", actor="fixture")
    partial = daily_plan(db, subject="fixture_a", corpus_version="diagnostic")
    assert partial["prerequisite"]["mate_evidence"] == "insufficient"
    for index, name in enumerate(("z1", "z2")):
        start(
            db,
            attempt_id=f"accepted-{index}",
            subject="fixture_a",
            source_type="corpus",
            version="diagnostic",
            key=name,
            goal="mate_in_one",
            training=True,
        )
        learned = submit(db, f"accepted-{index}", "fixture_a", event_id="answer", move="c5f8")[
            "learning"
        ]
        review_evidence(db, learned["evidence_id"], decision="accept", actor="fixture")
    sufficient = daily_plan(db, subject="fixture_a", corpus_version="diagnostic")
    assert sufficient["prerequisite"]["mate_evidence"] == "reviewed_sufficient"
    assert sufficient["prerequisite"]["review"] == "accepted"
    import chess_coach.curriculum_window_scope as window_scope
    from tests.test_objective_fork import _window_legacy_workflow

    with monkeypatch.context() as window_test:
        wall = [datetime.now(UTC)]
        window_test.setattr(window_scope, "clock", lambda: wall[0])
        _window_legacy_workflow(db, tmp_path, window_test, wall, "fixture_a")
    db.close()


def _created_backrank_public_workflow(tmp_path, monkeypatch):
    """Exercise created public back-rank defense on two original indexed histories."""
    import base64
    import contextlib
    import hashlib
    import io
    import json
    import random
    import subprocess
    import sys

    import chess
    import chess.engine
    import chess.pgn
    import httpx

    import chess_coach.mastery as mastery
    import chess_coach.objective_worker as objective_worker
    import chess_coach.opening_public_created_backrank_example as created_example
    import chess_coach.opening_public_created_backrank_scan as created_scan
    import chess_coach.ops_opening_profile as profile_cli
    from chess_coach.db import Database
    from chess_coach.fact_fingerprint import canonical, digest
    from chess_coach.ingest import ingest_pgn
    from chess_coach.objective_short_history import history_hash
    from chess_coach.opening_classification import classify_game
    from chess_coach.opening_full_history_build import build as build_history
    from chess_coach.opening_recent_acquire import acquire
    from chess_coach.opening_recent_index import build as build_recent
    from chess_coach.opening_recent_source import PREFIX_BYTES, PREFIX_NAME
    from chess_coach.opening_snapshot import SOURCE, VERSION, import_snapshot
    from chess_coach.web import create_app

    tail = (
        "d4 Bg4 dxe5 Bxf3 Qxf3 dxe5 Bc4 Nf6 Qb3 Qe7 Nc3 c6 "
        "Bg5 b5 Nxb5 cxb5 Bxb5+ Nbd7 O-O-O Rd8 Rxd7 Rxd7 Rd1 "
        "Qe6 Bxd7+ Nxd7 a3 Nb8 Rd8#"
    )
    lines = (f"e4 e5 Nf3 d6 {tail}", f"e4 d6 Nf3 e5 {tail}")
    games = []
    for index, line in enumerate(lines):
        board = chess.Board()
        for san in line.split():
            board.push_san(san)
        assert len(board.move_stack) == 33 and board.is_checkmate()
        game = chess.pgn.Game.from_board(board)
        game.headers.update(
            Event="Rated Blitz game",
            White=f"Peer {index}-{1100 + index}",
            Black=f"Reference {index}-{1200 + index}",
            Result="1-0",
            Date="2026.10.01",
            TimeControl="600+0",
            WhiteElo="1650",
            BlackElo="1700",
        )
        games.append((game, [move.uci() for move in board.move_stack]))
    root = tmp_path / "public-created-backrank"
    planning, data = root / ".runtime" / "planning", root / ".runtime" / "data"
    planning.mkdir(parents=True, mode=0o700)
    data.mkdir(mode=0o700)
    db_path = data / "synthetic.sqlite"
    with monkeypatch.context() as patch:
        patch.delenv("CHESS_SCHEMA_COMPAT", raising=False)
        db = Database(db_path)
        db.initialize()
        import_snapshot(db)
        owned = games[0][0]
        owned.headers.update(
            White="synthetic peer", Black="learner", UTCDate="2026.01.02", UTCTime="12:06:00"
        )
        ingest_pgn(db, str(owned))
        game_id = db.connection.execute("SELECT max(id) FROM games").fetchone()[0]
        position_id = db.connection.execute(
            "SELECT id FROM positions WHERE game_id=? AND ply=2", (game_id,)
        ).fetchone()[0]
        classify_game(db, game_id, version=VERSION, source_url=SOURCE)
        db.close()
        before = hashlib.sha256(db_path.read_bytes()).hexdigest()
        owned.headers.update(White="Peer 0-1100", Black="Reference 0-1200")
        text = "\n\n".join(str(game) for game, _ in games)
        noise = base64.b64encode(random.Random(801).randbytes(1_400_000)).decode()
        compressed = subprocess.run(
            ["/usr/bin/zstd", "-q", "-c"],
            input=(text + "\n\n{" + noise).encode(),
            stdout=subprocess.PIPE,
            check=True,
        ).stdout
        assert len(compressed) > PREFIX_BYTES
        prefix = compressed[:PREFIX_BYTES]

        def response(request):
            return httpx.Response(
                206,
                headers={
                    "Content-Range": f"bytes 0-{PREFIX_BYTES - 1}/{PREFIX_BYTES * 2}",
                    "Content-Length": str(PREFIX_BYTES),
                    "ETag": '"synthetic-created-backrank"',
                },
                content=prefix,
                request=request,
            )

        with httpx.Client(transport=httpx.MockTransport(response)) as client:
            acquire(root, "learner", client=client)
        assert build_recent(root, "learner")["accepted"] == 2
        assert build_history(root, "learner")["accepted"] == 2
        patch.setenv("CHESS_DB", str(db_path))
        patch.setenv("CHESS_SUBJECT", "learner")
        args = [
            "opening-profile",
            "--project-root",
            str(root),
            "--game-id",
            str(game_id),
            "--position-id",
            str(position_id),
            "--alternative",
            "d7d6",
            "--reference",
            "recent",
        ]
        for window in ("continuation", "initial"):
            patch.setattr(
                sys,
                "argv",
                [
                    *args,
                    "--prepare-public",
                    "--proof-kind",
                    "created_backrank",
                    "--fork-window",
                    window,
                ],
            )
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                profile_cli.main()
            prepared = json.loads(output.getvalue())
            policy = prepared["created_backrank_policy"]
            assert policy["origin"] == "newly_allowed" and policy["operation"] == "prevent"
            assert (policy["observer_node_limit"], policy["observer_reply_limit"]) == (6000, 100)
            assert (policy["judge_node_limit"], policy["judge_reply_limit"]) == (100, 100)
            if window == "continuation":
                assert all(
                    not b["examples"] and b["preparation_incomplete"]
                    for b in prepared["branches"].values()
                )
                continue
            for label, (_, moves) in zip(("played", "alternative"), games, strict=True):
                branch = prepared["branches"][label]
                assert branch["eligible"] == branch["selected"] == branch["supported"] == 1
                assert branch["nominated"] == 16 and branch["unknown_observations"] == 15
                example = branch["examples"][0]
                board = chess.Board()
                for uci in moves[:31]:
                    board.push_uci(uci)
                assert example["ply"] == 32 and example["side_to_move"] == "black"
                assert example["fen"] == board.fen(en_passant="fen", promoted=True)
                assert example["history_hash"] == history_hash(board)
                assert example["full_history_sha256"] == digest(canonical(moves))
                assert (
                    example["source_identity"]
                    and example["history_sha256"]
                    and example["record_hash"]
                )
                observer = example["observer"]
                assert observer["status"] == "opportunity" and observer["origin"] == "newly_allowed"
                assert observer["outcome"] == "allows" and observer["pre_move_candidates"] == []
                assert len(observer["alternatives"]) == len(list(board.legal_moves))
                assert example["recorded_uci"] == "d7b8" and example["recorded_san"] == "Nb8"
                assert example["recorded_verdict"]["mate_reply"]["uci"] == "d1d8"
                assert example["recorded_verdict"]["mate_reply"]["san"] == "Rd8#"
                h6 = next(item for item in example["alternatives"] if item["move"] == "h7h6")
                assert h6["status"] == "correct" and h6["reason"] == "no_immediate_checkmate_reply"
                for verdict in [example["recorded_verdict"], *example["alternatives"]]:
                    if "legal_replies" not in verdict:
                        continue
                    position = board.copy(stack=True)
                    position.push_uci(verdict["move"])
                    assert verdict["history_hash"] == history_hash(board)
                    assert set(verdict["legal_replies"]) == {m.uci() for m in position.legal_moves}
                    assert verdict["replies_scanned"] == len(verdict["legal_replies"])
                assert len(example["recorded_verdict"]["legal_replies"]) == 46
                assert len(h6["legal_replies"]) == 45

        _created_backrank_interruption(root, db_path, game_id, position_id, patch)

        def forbidden(*_args, **_kwargs):
            pytest.fail("proof, engine, provider, or learning on private read")

        with patch.context() as read:
            read.setattr(created_scan, "observe", forbidden)
            read.setattr(created_example, "judge", forbidden)
            read.setattr(chess.engine.SimpleEngine, "popen_uci", forbidden)
            read.setattr(httpx.Client, "send", forbidden)
            read.setattr(mastery, "update_mastery", forbidden)
            read.setattr(objective_worker, "process", forbidden)
            read.setattr(sys, "argv", [*args, "--proof-kind", "created_backrank"])
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                profile_cli.main()
            shown = json.loads(output.getvalue())["public_preparation"]
            assert shown["created_backrank_status"] == "prepared"
            assert all(b["supported"] == 1 for b in shown["branches"].values())
            app = create_app(
                db_path=db_path,
                project_root=root,
                subject="learner",
                actor="fixture",
                corpus="test",
                login="fixture",
                origin="https://coach.invalid",
            )
            route = f"/repertoire/games/{game_id}/openings/{position_id}/profile"
            client = app.test_client()
            assert client.get(route, base_url="https://coach.invalid").status_code == 403
            query = {"reference": "recent", "alternative": "d7d6", "proof_kind": "created_backrank"}
            page = client.get(
                route,
                query_string=query,
                base_url="https://coach.invalid",
                headers={"Tailscale-User-Login": "fixture"},
            )
            assert page.status_code == 200
            assert page.data.count(b"Public newly allowed back-rank example") == 2
            assert b"Black played Nb8, newly allowing Rd8#" in page.data
            assert b"h6" in page.data and b"no immediate mating reply" in page.data
            prefix_path = planning / PREFIX_NAME
            original_prefix = prefix_path.read_bytes()
            artifacts = {
                p: hashlib.sha256(p.read_bytes()).hexdigest()
                for p in planning.glob("opening-public-proof-*.json")
            }
            prefix_path.chmod(0o600)
            try:
                with prefix_path.open("r+b") as stream:
                    stream.write(bytes([original_prefix[0] ^ 1]))
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    profile_cli.main()
                assert json.loads(output.getvalue())["public_preparation"] is None
                stale = client.get(
                    route,
                    query_string=query,
                    base_url="https://coach.invalid",
                    headers={"Tailscale-User-Login": "fixture"},
                )
                assert stale.status_code == 200
                assert b"No current newly allowed back-rank preparation" in stale.data
            finally:
                with prefix_path.open("r+b") as stream:
                    stream.write(original_prefix[:1])
                prefix_path.chmod(0o400)
            assert prefix_path.read_bytes() == original_prefix
            assert {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in artifacts} == artifacts
        assert hashlib.sha256(db_path.read_bytes()).hexdigest() == before


def _created_backrank_interruption(root, db_path, game_id, position_id, patch):
    """Keep actual earlier verified answers when later independent judging stops."""
    import sqlite3
    import time

    import chess_coach.opening_public_created_backrank_example as created_example
    from chess_coach.opening_profile_cli_db import private_database
    from chess_coach.opening_public_created_backrank import branch
    from chess_coach.opening_public_created_backrank_policy import policy
    from chess_coach.opening_public_fork_later import bound
    from chess_coach.opening_public_proof_source import binding
    from chess_coach.style_schedule_budget import history_budget

    deadline = time.monotonic() + 20
    with private_database(root, "learner", database=db_path) as read_db:
        with history_budget(deadline=deadline):
            base, _ = binding(read_db, root, "learner", game_id, position_id, "d7d6", deadline)
        full = bound(root, "learner", deadline)
    selected = policy(base, full[1], "initial")
    selected = {**selected, "index_sha256": full[1]}
    original = created_example._judge
    returned = []

    def interrupted(board, move, start, end):
        if len(returned) == 2:
            raise TimeoutError("fixture later independent judgment")
        result = original(board, move, start, end)
        returned.append(result)
        return result

    with patch.context() as bounded:
        bounded.setattr(created_example, "_judge", interrupted)
        with sqlite3.connect(full[0][0].as_uri() + "?mode=ro&immutable=1", uri=True) as indexed:
            start = time.monotonic()
            partial = branch(indexed, selected, base["source"]["played"], start + 20, start=start)
    assert partial["status"] == "incomplete" and partial["interrupted"]
    assert partial["unfinished_games"] and partial["examples"]
    value = partial["examples"][0]
    assert value["interrupted"] and value["recorded_verdict"] == returned[0]
    assert value["alternatives"] == [returned[1]] and returned[1]["status"] == "correct"
    assert returned[0]["legal_replies"] and returned[1]["legal_replies"]
