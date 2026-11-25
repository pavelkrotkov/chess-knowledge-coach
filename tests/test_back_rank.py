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
    assert state["v"] == 6 and len(state["prerequisite_scope"]) == 64
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
