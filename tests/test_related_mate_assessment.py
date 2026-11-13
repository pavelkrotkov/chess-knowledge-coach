"""Bounded unfamiliar short-mate assessment keeps provenance and assistance."""

import json

import chess
import pytest

from chess_coach.evidence_review import review_evidence
from chess_coach.mate_assessment_history import report as assessment_history
from chess_coach.mate_auto import process_decision
from chess_coach.related_mate import preview
from chess_coach.related_mate_source import source_for_evidence
from chess_coach.related_mate_start import start_related
from chess_coach.unified_session_events import hint, reveal, show, submit
from chess_coach.web import create_app
from tests.test_mate_proof import owned_game

SUBJECT = "fixture_a"


@pytest.mark.parametrize("mode", ["unassisted", "assisted", "ungraded", "incorrect"])
def test_related_short_mate_assessment_workflow(tmp_path, monkeypatch, mode):
    fen = "6k1/5ppp/8/1p5Q/8/5R2/7r/KQ3R2 w - - 0 1"
    db = owned_game(tmp_path / "short.sqlite", monkeypatch, fen=fen, move="Qa2")
    monkeypatch.setattr("chess_coach.mate_auto.short_candidate", lambda *_: True)
    process_decision(db, 1, SUBJECT)
    evidence = db.connection.execute(
        "SELECT id FROM evidence_mappings WHERE skill='calculation' AND operation='execute'"
    ).fetchone()[0]
    initial = chess.Board("6k1/1p3ppp/8/7Q/8/5R2/7r/KQ3R2 b - - 0 1")
    source = source_for_evidence(db, SUBJECT, evidence)
    moves = "b7b6 " + source["lines"][0]
    db.connection.execute(
        "INSERT INTO puzzle_corpora(version,source,checksum,state) VALUES('short','fixture','checksum','staging')"
    )
    corpus = db.connection.execute("SELECT id FROM puzzle_corpora").fetchone()[0]
    db.connection.execute(
        """INSERT INTO puzzles(puzzle_id,corpus_id,fen,source,solution,rating,rating_deviation,themes_json,objective)
        VALUES('short',?,?,'https://example.invalid',?,1200,80,'["mateIn2"]','unknown')""",
        (corpus, initial.fen(), moves),
    )
    db.connection.execute("INSERT INTO puzzle_themes VALUES(?,?,'mateIn2',1200)", (corpus, "short"))
    db.connection.execute("UPDATE puzzle_corpora SET state='ready' WHERE id=?", (corpus,))
    db.connection.commit()
    if mode == "unassisted":
        from chess_coach.recurrence_snapshot import read_snapshot
        from chess_coach.tactical_course_related import unfamiliar

        with read_snapshot(db):
            course_chapter = unfamiliar(
                db, SUBJECT, "short", {"kind": "short_mate", "evidence_id": evidence}
            )
        assert course_chapter["mode"] == "conceal"
        assert "Pattern-cued unfamiliar worked example" in course_chapter["pgn"]
        assert "Worked example, ungraded" in course_chapter["pgn"]
        from chess_coach.tactical_course_budget import Budget
        from chess_coach.tactical_course_resolve import related

        matched, reason = related(
            db, SUBJECT, "short", {"kind": "short_mate", "evidence_id": evidence}, Budget(db)
        )
        assert reason is None and matched["mode"] == "conceal"
    selected = preview(db, SUBJECT, evidence, "short")
    assert selected["mate_timing"] == "mate_within_two"
    assert len(selected["items"]) == 1 and selected["items"][0]["assessment_available"]
    ref = selected["items"][0]["reference"]
    before = db.connection.execute("SELECT COUNT(*) FROM training_attempts").fetchone()[0]
    if mode == "ungraded":
        monkeypatch.setattr("chess_coach.related_mate_assessment_context.capture", lambda *_: None)
    state = start_related(
        db,
        attempt_id="assessment",
        subject=SUBJECT,
        evidence_id=evidence,
        corpus_version="short",
        reference=ref,
        assessment=True,
    )
    assert state["short_mate_assessment"] and state["objective"] == "mate_within_two"
    row = db.connection.execute(
        "SELECT * FROM unified_sessions WHERE attempt_id='assessment'"
    ).fetchone()
    data = json.loads(row["provenance_json"])["related_mate"]["assessment"]
    assert data["history_mode"] == "zeroing_setup" and data["roots"]
    if mode == "ungraded":
        assert data["context"] is None
    else:
        assert data["context"]["content_rating"] == 1200
        assert data["context"]["content_deviation"] == 80
    assert len(data["roots"]) >= 2
    initial_history = assessment_history(db, SUBJECT, "short")
    assert initial_history["items"][0]["outcome"] == "incomplete"
    first_move = data["roots"][1 if mode == "unassisted" else 0]["move"]["uci"]
    if mode == "unassisted":
        assert first_move != moves.split()[1]
    if mode == "ungraded":
        board = chess.Board(state["fen"])
        proved = {root["move"]["uci"] for root in data["roots"]}
        unknown = next(move for move in board.legal_moves if move.uci() not in proved)
        result = submit(db, "assessment", SUBJECT, event_id="first", move=unknown.uci())
        assert result["status"] == "needs_verification" and "source_key" not in result
        assert db.connection.execute("SELECT COUNT(*) FROM objective_requests").fetchone()[0] == 0
    else:
        first = submit(db, "assessment", SUBJECT, event_id="first", move=first_move)
        assert first["status"] == "active" and first["opponent_move"]
        if mode == "assisted":
            hint(db, "assessment", SUBJECT, event_id="hint")
            reveal(db, "assessment", SUBJECT, event_id="reveal")
        board = chess.Board(show(db, "assessment", SUBJECT)["fen"])
        move = next(
            move for move in board.legal_moves if _mate(board, move) != (mode == "incorrect")
        )
        result = submit(db, "assessment", SUBJECT, event_id="mate", move=move.uci())
        assert result["status"] == (
            "line_completed" if mode == "incorrect" else "objective_verified"
        )
        assert result["hints_used"] == (2 if mode == "assisted" else 0)
    history = assessment_history(db, SUBJECT, "short")
    assert len(history["items"]) == 1
    entry = history["items"][0]
    assert (
        entry["outcome"]
        == {
            "unassisted": "verified",
            "assisted": "verified",
            "ungraded": "unresolved",
            "incorrect": "incorrect",
        }[mode]
    )
    assert entry["current"]
    assert entry["hints"] == (2 if mode == "assisted" else 0)
    assert entry["reveals"] == (1 if mode == "assisted" else 0)
    assert (entry["scope"] is None) == (mode == "ungraded")
    if mode == "unassisted":
        import copy

        from chess_coach.mate_assessment_groups import groups
        from chess_coach.mate_assessment_scope import scope

        binding = json.loads(row["provenance_json"])["related_mate"]
        first = copy.deepcopy(data)
        first["context"]["ranking_baseline"] = 1601
        second = copy.deepcopy(first)
        second["context"]["ranking_baseline"] = 1602
        assert scope(row, binding, first)["key"] == scope(row, binding, second)["key"]
        second["context"]["material_distance"] += 1
        assert scope(row, binding, first)["key"] != scope(row, binding, second)["key"]
        examples = [
            {**entry, "started_at": f"2026-01-01T00:00:{i:02}+00:00", "hints": i % 2, "reveals": 0}
            for i in range(20)
        ]
        compared = groups(examples, False)[0]
        assert compared["comparable"] and compared["earlier"]["unassisted"]["verified"] == 5
        assert compared["later"]["assisted"]["verified"] == 5
        examples[0]["hints"] = 1
        assert not groups(examples, False)[0]["comparable"]
        examples[0]["hints"] = 0
        examples[-1]["outcome"] = "unresolved"
        assert not groups(examples, False)[0]["comparable"]
        assert not groups(examples, True)[0]["comparable"]
        import sqlite3

        with pytest.raises(sqlite3.IntegrityError, match="ready corpus is immutable"):
            db.connection.execute("UPDATE puzzles SET rating=2399 WHERE puzzle_id='short'")
        db.connection.rollback()
        assert assessment_history(db, SUBJECT, "short")["items"][0]["scope"]["rating_start"] == 1200
    assert db.connection.execute("SELECT COUNT(*) FROM training_attempts").fetchone()[0] == before
    app = create_app(
        db_path=tmp_path / "short.sqlite",
        subject=SUBJECT,
        actor="fixture",
        corpus="short",
        login="fixture",
        origin="https://coach.invalid",
    )
    page = app.test_client().get(
        "/unified/assessment",
        base_url="https://coach.invalid",
        headers={"Tailscale-User-Login": "fixture"},
    )
    assert page.status_code == 200
    expected = {
        "unassisted": b"No hint or reveal was used",
        "assisted": b"This attempt was assisted",
        "ungraded": b"remains ungraded",
        "incorrect": b"Incorrect: this final move did not give checkmate",
    }
    assert expected[mode] in page.data
    client = app.test_client()
    assert client.get("/assessment-history", base_url="https://coach.invalid").status_code == 403
    history_page = client.get(
        "/assessment-history",
        base_url="https://coach.invalid",
        headers={"Tailscale-User-Login": "fixture"},
    )
    assert history_page.status_code == 200
    assert b"Recorded first encounters" in history_page.data
    assert b"fixture_a" not in history_page.data
    if mode == "unassisted":
        from datetime import UTC, datetime, timedelta

        for index in range(201):
            copy_row = dict(row)
            copy_row.update(
                attempt_id=f"prior-{index}",
                subject="fixture_other",
                objective="legal_line",
                started_at=(datetime(2025, 1, 1, tzinfo=UTC) + timedelta(days=index)).isoformat(),
            )
            columns = ",".join(copy_row)
            marks = ",".join("?" for _ in copy_row)
            db.connection.execute(
                f"INSERT INTO unified_sessions({columns}) VALUES({marks})", tuple(copy_row.values())
            )
        db.connection.commit()
        app.config["SUBJECT"] = "fixture_other"
        limited_page = client.get(
            "/assessment-history",
            base_url="https://coach.invalid",
            headers={"Tailscale-User-Login": "fixture"},
        )
        assert (
            b"No short-mate assessments were found in the inspected sessions" in limited_page.data
        )
        assert b"No short-mate assessments have been recorded yet" not in limited_page.data
        app.config["SUBJECT"] = SUBJECT
    review_evidence(db, evidence, decision="reject", actor="fixture_reviewer")
    historical = assessment_history(db, SUBJECT, "short")["items"][0]
    assert not historical["current"] and historical["outcome"] == entry["outcome"]
    with pytest.raises(ValueError):
        show(db, "assessment", SUBJECT)
    db.close()

    if mode == "unassisted":
        # An unfamiliar immediate-mate source may have more than one mating move.
        mate_path = tmp_path / "immediate.sqlite"
        mate_db = owned_game(
            mate_path, monkeypatch, fen="7k/8/6K1/8/8/Q7/8/8 w - - 0 1", move="Qa8"
        )
        monkeypatch.setattr("chess_coach.mate_auto.short_candidate", lambda *_: False)
        process_decision(mate_db, 1, SUBJECT)
        mate_evidence = mate_db.connection.execute(
            "SELECT id FROM evidence_mappings WHERE skill='mate_in_one' AND operation='execute'"
        ).fetchone()[0]
        mate_source = source_for_evidence(mate_db, SUBJECT, mate_evidence)
        supplied = mate_source["lines"][0].split()[0]
        board = chess.Board("7k/1p6/6K1/8/8/Q7/8/8 b - - 0 1")
        mate_db.connection.execute(
            "INSERT INTO puzzle_corpora(version,source,checksum,state) VALUES('mate-one','fixture','checksum','staging')"
        )
        corpus_id = mate_db.connection.execute("SELECT id FROM puzzle_corpora").fetchone()[0]
        mate_db.connection.execute(
            """INSERT INTO puzzles(puzzle_id,corpus_id,fen,source,solution,rating,rating_deviation,themes_json,objective)
            VALUES('mate',?,?,'https://example.invalid',?,1200,80,'["mateIn1"]','unknown')""",
            (corpus_id, board.fen(), "b7b6 " + supplied),
        )
        mate_db.connection.execute(
            "INSERT INTO puzzle_themes VALUES(?, 'mate', 'mateIn1', 1200)", (corpus_id,)
        )
        mate_db.connection.execute(
            "UPDATE puzzle_corpora SET state='ready' WHERE id=?", (corpus_id,)
        )
        mate_db.connection.commit()
        choice = preview(mate_db, SUBJECT, mate_evidence, "mate-one")
        assert choice["mate_timing"] == "mate_in_one" and len(choice["items"]) == 1
        reference = choice["items"][0]["reference"]
        start_related(
            mate_db,
            attempt_id="alternative",
            subject=SUBJECT,
            evidence_id=mate_evidence,
            corpus_version="mate-one",
            reference=reference,
        )
        prompt = chess.Board(show(mate_db, "alternative", SUBJECT)["fen"])
        alternative = next(
            move for move in prompt.legal_moves if move.uci() != supplied and _mate(prompt, move)
        )
        result = submit(mate_db, "alternative", SUBJECT, event_id="answer", move=alternative.uci())
        assert result["status"] == result["feedback"] == "objective_verified"
        assert (
            submit(mate_db, "alternative", SUBJECT, event_id="answer", move=alternative.uci())
            == result
        )
        nonmate = next(move for move in prompt.legal_moves if not _mate(prompt, move))
        from chess_coach.unified_session_unmatched import unmatched

        row = mate_db.connection.execute(
            "SELECT * FROM unified_sessions WHERE attempt_id='alternative'"
        ).fetchone()
        prompt.push(nonmate)
        assert unmatched(row, prompt, 0, [])["status"] == "needs_verification"
        assert (
            mate_db.connection.execute("SELECT COUNT(*) FROM objective_requests").fetchone()[0] == 0
        )
        mate_app = create_app(
            db_path=mate_path,
            subject=SUBJECT,
            actor="fixture",
            corpus="mate-one",
            login="fixture",
            origin="https://coach.invalid",
        )
        mate_page = mate_app.test_client().get(
            "/unified/alternative",
            base_url="https://coach.invalid",
            headers={"Tailscale-User-Login": "fixture"},
        )
        assert b"The stated checkmate objective was verified" in mate_page.data
        review_evidence(mate_db, mate_evidence, decision="reject", actor="fixture_reviewer")
        with pytest.raises(ValueError):
            show(mate_db, "alternative", SUBJECT)
        mate_db.close()


def _mate(board, move):
    board.push(move)
    result = board.is_checkmate()
    board.pop()
    return result


def test_empty_batches_continue_and_later_assessment_is_admitted(tmp_path, monkeypatch):
    import copy
    import html
    import re
    from urllib.parse import parse_qs, urlsplit

    import chess_coach.related_mate_search_page as search_page
    from chess_coach.recurrence_snapshot import read_snapshot
    from chess_coach.related_mate_search_select import select as search_select
    from chess_coach.related_mate_search_token import decode, encode

    original_select = search_page.select

    def checked_snapshot(database, *args):
        assert not database.connection.in_transaction
        return original_select(database, *args)

    monkeypatch.setattr(search_page, "select", checked_snapshot)
    subject = "fixture_a"
    fen = "6k1/5ppp/8/1p5Q/8/5R2/7r/KQ3R2 w - - 0 1"
    path = tmp_path / "search.sqlite"
    db = owned_game(path, monkeypatch, fen=fen, move="Qa2")
    monkeypatch.setattr("chess_coach.mate_auto.short_candidate", lambda *_: True)
    process_decision(db, 1, subject)
    evidence = db.connection.execute(
        "SELECT id FROM evidence_mappings WHERE skill='calculation' AND operation='execute'"
    ).fetchone()[0]
    source = source_for_evidence(db, subject, evidence)
    initial = chess.Board("6k1/1p3ppp/8/7Q/8/5R2/7r/KQ3R2 b - - 0 1")
    moves = "b7b6 " + source["lines"][0]
    other = chess.Board("6k1/1p3ppp/8/7Q/8/P4R2/7r/KQ3R2 b - - 0 1")
    other_moves = "b7b6 " + source["lines"][0]
    same_game = chess.Board("6k1/1p3ppp/8/7Q/P7/5R2/7r/KQ3R2 b - - 0 1")
    from chess_coach.related_mate_features import corpus_features, mate_features

    _, same_game_features = corpus_features(same_game.fen(), moves)
    source_features = mate_features(source["prompt_fen"], source["lines"][0].split())
    for key in ("mover", "target", "timing", "geometry"):
        assert same_game_features[key] == source_features[key]
    db.connection.execute(
        "INSERT INTO puzzle_corpora(version,source,checksum,state) VALUES('short','fixture','checksum','staging')"
    )
    corpus = db.connection.execute("SELECT id FROM puzzle_corpora").fetchone()[0]
    sql = """INSERT INTO puzzles(puzzle_id,corpus_id,fen,source,solution,rating,rating_deviation,themes_json,objective)
    VALUES(?,?,?,?,?,1200,80,'["mateIn2"]','unknown')"""
    for index in range(200):
        key = f"d{index:03}"
        db.connection.execute(sql, (key, corpus, initial.fen(), "https://example.invalid", "b7b6"))
        db.connection.execute("INSERT INTO puzzle_themes VALUES(?,?,'mateIn2',1200)", (corpus, key))
    variants = []
    for index, square in enumerate((chess.B3, chess.C3, chess.B4, chess.E3), start=1):
        board = initial.copy()
        board.set_piece_at(square, chess.Piece(chess.PAWN, chess.WHITE))
        variants.append((f"short{index}", board, "https://example.invalid", moves))
    for key, board, source_url, line in (
        ("a-seen", initial, "https://lichess.org/abcd1234/white", moves),
        ("short", other, "https://example.invalid", other_moves),
        ("z-duplicate", initial, "https://lichess.org/abcd1234/black", moves),
        ("z-same-game", same_game, "https://lichess.org/abcd1234/black", moves),
        *variants,
    ):
        db.connection.execute(sql, (key, corpus, board.fen(), source_url, line))
        db.connection.execute("INSERT INTO puzzle_themes VALUES(?,?,'mateIn2',1200)", (corpus, key))
    db.connection.execute("UPDATE puzzle_corpora SET state='ready' WHERE id=?", (corpus,))
    db.connection.commit()
    app = create_app(
        db_path=path,
        subject=subject,
        actor="fixture",
        corpus="short",
        login="fixture",
        origin="https://coach.invalid",
    )
    client = app.test_client()
    base = "https://coach.invalid"
    headers = {"Tailscale-User-Login": "fixture"}
    route = f"/evidence/{evidence}/related-mates"
    normal = client.get(route, base_url=base, headers=headers)
    assert normal.status_code == 200 and b"Search more short-mate examples" in normal.data
    assert normal.data.count(b"Try verified short-mate assessment") == 1
    empty = client.get(route + "?search=begin", base_url=base, headers=headers)
    assert empty.status_code == 200 and b"No matching examples in this batch" in empty.data
    match = re.search(r'href="([^"]+)">Search the next batch</a>', empty.text)
    assert match
    link = html.unescape(match.group(1))
    next_token = parse_qs(urlsplit(link).query)["search"][0]
    next_state = decode(app.secret_key, next_token)
    assert all(
        key is None or (type(key[0]) is int and len(key[1]) == 64) for key in next_state["keys"]
    )
    bad_state = copy.deepcopy(next_state)
    anchor = next(key for key in bad_state["keys"] if key is not None)
    anchor[0] += 1
    bad_token = encode(app.secret_key, bad_state)
    assert (
        client.get(
            route, query_string={"search": bad_token}, base_url=base, headers=headers
        ).status_code
        == 400
    )
    assert client.get(link + "x", base_url=base, headers=headers).status_code == 400
    app.config["SUBJECT"] = "fixture_other"
    assert client.get(link, base_url=base, headers=headers).status_code == 400
    app.config["SUBJECT"] = subject
    app.config["CORPUS"] = "missing"
    assert client.get(link, base_url=base, headers=headers).status_code == 400
    app.config["CORPUS"] = "short"
    later = client.get(link, base_url=base, headers=headers)
    assert later.status_code == 200 and later.data.count(b"Try verified short-mate assessment") == 4
    more = re.search(r'href="([^"]+)">More matches in this batch</a>', later.text)
    assert more
    later = client.get(html.unescape(more.group(1)), base_url=base, headers=headers)
    assert later.status_code == 200 and later.data.count(b"Try verified short-mate assessment") == 1
    reference_match = re.search(r'name="reference" value="([^"]+)"', later.text)
    search_match = re.search(r'name="search" value="([^"]+)"', later.text)
    assert reference_match and search_match
    reference = reference_match.group(1)
    search = search_match.group(1)
    form_state = decode(app.secret_key, search)
    with read_snapshot(db):
        chosen, _ = search_select(db, subject, evidence, "short", app.secret_key, form_state)
    assert form_state["scope"] != chosen[4]
    assert "short" not in json.dumps(form_state)
    with client.session_transaction(base_url=base) as session:
        csrf = session["csrf"]
    form = {"csrf": csrf, "reference": reference, "search": search, "assessment": "1"}
    headers["Origin"] = base
    started = client.post(route + "/start", data=form, base_url=base, headers=headers)
    assert started.status_code == 303
    with client.session_transaction(base_url=base) as session:
        attempt = session["unified_attempt"]
    row = db.connection.execute(
        "SELECT provenance_json FROM unified_sessions WHERE attempt_id=?", (attempt,)
    ).fetchone()
    binding = json.loads(row[0])["related_mate"]
    assert binding["rank_version"] == "mate-search-v1" and binding["assessment"]["roots"]
    assert client.get(started.location, base_url=base, headers=headers).status_code == 200
    stale = client.post(route + "/start", data=form, base_url=base, headers=headers)
    assert stale.status_code == 400
    db.close()
