"""Owned pin certificates retrieve only legal, independently certified examples."""

import json

import chess
import pytest

from chess_coach.evidence_review import review_evidence
from chess_coach.related_pin import preview, selection
from chess_coach.related_pin_budget import create
from chess_coach.related_pin_line import candidate_line
from chess_coach.related_pin_source import source_for_evidence
from chess_coach.related_pin_start import start_related
from chess_coach.unified_session_events import hint, reveal, show, submit
from tests.test_objective_pin import SUBJECT, owned_pin
from tests.transfer_concealment_support import preview_text


def _candidate(source):
    line = source["lines"][0].split()
    for file in "abcdefgh":
        board = chess.Board(source["prompt_fen"])
        board.turn = not board.turn
        rank, destination = ("2", "3") if board.turn else ("7", "6")
        origin = chess.parse_square(file + rank)
        if board.piece_at(origin):
            continue
        board.set_piece_at(origin, chess.Piece(chess.PAWN, board.turn))
        setup = file + rank + file + destination
        move = chess.Move.from_uci(setup)
        if not board.is_valid() or move not in board.legal_moves:
            continue
        after = board.copy(stack=True)
        after.push(move)
        if candidate_line(after, line, source["features"], create()):
            return board.fen(), setup + " " + " ".join(line)
    for file in "abcdefgh":
        for extra_file in "abcdefgh":
            board = chess.Board(source["prompt_fen"])
            opponent = not board.turn
            target_rank, origin_rank = ("3", "2") if opponent else ("6", "7")
            target = chess.parse_square(file + target_rank)
            origin = chess.parse_square(file + origin_rank)
            extra = chess.parse_square(extra_file + ("2" if board.turn else "7"))
            if board.piece_at(target) != chess.Piece(chess.PAWN, opponent):
                continue
            if board.piece_at(origin) or board.piece_at(extra):
                continue
            board.remove_piece_at(target)
            board.set_piece_at(origin, chess.Piece(chess.PAWN, opponent))
            board.set_piece_at(extra, chess.Piece(chess.PAWN, board.turn))
            board.turn = opponent
            setup = file + origin_rank + file + target_rank
            move = chess.Move.from_uci(setup)
            if not board.is_valid() or move not in board.legal_moves:
                continue
            after = board.copy(stack=True)
            after.push(move)
            if candidate_line(after, line, source["features"], create()):
                return board.fen(), setup + " " + " ".join(line)
    raise AssertionError("no synthetic candidate")


def fixture(path, monkeypatch, *, black=False, relative=False, public_only=False):
    db, evidence = owned_pin(path, monkeypatch, black=black, relative=relative)
    source = source_for_evidence(db, SUBJECT, evidence)
    fen, line = _candidate(source)
    db.connection.execute(
        "INSERT INTO puzzle_corpora(version,source,checksum,state) VALUES('test','fixture','checksum','staging')"
    )
    corpus = db.connection.execute("SELECT id FROM puzzle_corpora WHERE version='test'").fetchone()[
        0
    ]
    if not public_only:
        db.connection.execute(
            """INSERT INTO puzzles(puzzle_id,corpus_id,fen,source,solution,rating,rating_deviation,themes_json,objective)
            VALUES('fixture-pin',?,?,'https://example.invalid',?,1200,80,'[]','unknown')""",
            (corpus, fen, line),
        )
        db.connection.execute(
            "INSERT INTO puzzle_themes VALUES(?,?,'pin',1200)", (corpus, "fixture-pin")
        )
    db.connection.execute("UPDATE puzzle_corpora SET state='ready' WHERE id=?", (corpus,))
    db.connection.commit()
    return db, evidence, fen, line


@pytest.mark.parametrize("black", [False, True])
@pytest.mark.parametrize("relative", [False, True])
def test_owned_pin_transfer_playable_concealed_and_review_bound(
    tmp_path, monkeypatch, black, relative
):
    db, evidence, _, _ = fixture(
        tmp_path / "pin.sqlite", monkeypatch, black=black, relative=relative
    )
    result = preview(db, SUBJECT, evidence, "test")
    assert result["status"] == "available" and len(result["items"]) == 1
    chosen = selection(db, SUBJECT, evidence, "test")
    source = source_for_evidence(db, SUBJECT, evidence)
    assert source["lines"][0].split()[0] not in preview_text(result, chosen)
    assert "candidate_certificates" not in json.dumps(result)
    reference = result["items"][0]["reference"]
    state = start_related(
        db,
        attempt_id="pin-transfer",
        subject=SUBJECT,
        evidence_id=evidence,
        corpus_version="test",
        reference=reference,
    )
    assert state["status"] == "active" and state["objective"] == "legal_line"
    assert "source_key" not in state
    row = db.connection.execute(
        "SELECT lines_json,provenance_json FROM unified_sessions WHERE attempt_id='pin-transfer'"
    ).fetchone()
    lines = json.loads(row["lines_json"])
    binding = json.loads(row["provenance_json"])["related_pin"]
    assert binding["operation"] == "execute" and binding["pattern_cued"]
    assert binding["candidate_certificates"][0]["proof"]["type"] == (
        "relative_pin" if relative else "absolute_pin"
    )
    assert len(lines[0]) == 3
    first = submit(db, "pin-transfer", SUBJECT, event_id="first", move=lines[0][0])
    assert first["status"] == "active" and first["opponent_move"] == lines[0][1]
    last = submit(db, "pin-transfer", SUBJECT, event_id="last", move=lines[0][2])
    assert last["status"] == "line_completed"
    assert db.connection.execute("SELECT COUNT(*) FROM objective_requests").fetchone()[0] == 0
    assert db.connection.execute("SELECT COUNT(*) FROM training_attempts").fetchone()[0] == 0
    review_evidence(db, evidence, decision="reject", actor="fixture_reviewer")
    with pytest.raises(ValueError, match="stale"):
        show(db, "pin-transfer", SUBJECT)


def test_unlisted_moves_and_reveal_are_not_claimed_as_solved(tmp_path, monkeypatch):
    db, evidence, _, _ = fixture(tmp_path / "unlisted.sqlite", monkeypatch)
    item = preview(db, SUBJECT, evidence, "test")["items"][0]
    state = start_related(
        db,
        attempt_id="unknown",
        subject=SUBJECT,
        evidence_id=evidence,
        corpus_version="test",
        reference=item["reference"],
    )
    saved = json.loads(
        db.connection.execute(
            "SELECT lines_json FROM unified_sessions WHERE attempt_id='unknown'"
        ).fetchone()[0]
    )
    board = chess.Board(state["fen"])
    alternative = next(move.uci() for move in board.legal_moves if move.uci() != saved[0][0])
    assert (
        submit(db, "unknown", SUBJECT, event_id="other", move=alternative)["feedback"]
        == "needs_verification"
    )
    assert db.connection.execute("SELECT COUNT(*) FROM objective_requests").fetchone()[0] == 0
    db2, ev2, _, _ = fixture(tmp_path / "reveal.sqlite", monkeypatch)
    ref = preview(db2, SUBJECT, ev2, "test")["items"][0]["reference"]
    start_related(
        db2,
        attempt_id="hint",
        subject=SUBJECT,
        evidence_id=ev2,
        corpus_version="test",
        reference=ref,
    )
    assert hint(db2, "hint", SUBJECT, event_id="hint")["assistance_kind"] == "hinted"
    assert reveal(db2, "hint", SUBJECT, event_id="reveal")["assistance_kind"] == "revealed"


def test_line_budget_and_missing_history_do_not_run_proof(tmp_path, monkeypatch):
    from chess_coach import related_pin_certificate
    from chess_coach.related_pin_line import candidate_line

    db, evidence, fen, full = fixture(tmp_path / "budget.sqlite", monkeypatch)
    source = source_for_evidence(db, SUBJECT, evidence)
    board = chess.Board(fen)
    words = full.split()
    board.push_uci(words[0])
    budget = create()
    budget["root_proof_limit"] = 0
    monkeypatch.setattr(
        related_pin_certificate, "proven", lambda *_: pytest.fail("unreserved proof")
    )
    assert candidate_line(board, words[1:], source["features"], budget) is None
    assert budget["truncated"] and budget["root_proofs"] == 0

    board = chess.Board(board.fen())
    board.halfmove_clock = 1
    budget = create()
    assert candidate_line(board, words[1:], source["features"], budget) is None
    assert budget["unknown"] == 1 and budget["root_proofs"] == 0


def test_full_line_and_certificate_branch_must_match(tmp_path, monkeypatch):
    from chess_coach.pin_proof import proven

    db, evidence, fen, full = fixture(tmp_path / "line.sqlite", monkeypatch)
    source = source_for_evidence(db, SUBJECT, evidence)
    board = chess.Board(fen)
    words = full.split()
    board.push_uci(words[0])
    line = words[1:]
    good = candidate_line(board, line, source["features"], create())
    assert good is not None
    assert candidate_line(board, [*line, "a1a8"], source["features"], create()) is None
    creation = board.parse_uci(line[0])
    certificates = proven(board, creation)
    after = board.copy(stack=True)
    after.push(creation)
    recorded = {
        (branch["reply"], branch["capture"])
        for proof in certificates
        for branch in proof["branches"]
    }
    unrelated = None
    for defense in after.legal_moves:
        reply = after.copy(stack=True)
        reply.push(defense)
        for capture in reply.legal_moves:
            if reply.is_capture(capture) and (defense.uci(), capture.uci()) not in recorded:
                unrelated = [creation.uci(), defense.uci(), capture.uci()]
                break
        if unrelated:
            break
    assert unrelated is not None
    assert candidate_line(board, unrelated, source["features"], create()) is None


def test_source_review_and_reference_invalidation(tmp_path, monkeypatch):
    db, evidence, _, _ = fixture(tmp_path / "stale.sqlite", monkeypatch)
    reference = preview(db, SUBJECT, evidence, "test")["items"][0]["reference"]
    with pytest.raises(ValueError):
        preview(db, "fixture_other", evidence, "test")
    review_evidence(db, evidence, decision="accept", actor="fixture_reviewer")
    with pytest.raises(ValueError):
        start_related(
            db,
            attempt_id="old",
            subject=SUBJECT,
            evidence_id=evidence,
            corpus_version="test",
            reference=reference,
        )


def test_corpus_line_change_invalidates_active_session(tmp_path, monkeypatch):
    db, evidence, _, _ = fixture(tmp_path / "source.sqlite", monkeypatch)
    reference = preview(db, SUBJECT, evidence, "test")["items"][0]["reference"]
    start_related(
        db,
        attempt_id="changed",
        subject=SUBJECT,
        evidence_id=evidence,
        corpus_version="test",
        reference=reference,
    )
    from chess_coach import related_pin_current

    resolve = related_pin_current.resolve_source

    def changed(*args, **kwargs):
        candidate = resolve(*args, **kwargs)
        candidate["lines"] = [candidate["lines"][0] + " a1a1"]
        return candidate

    monkeypatch.setattr(related_pin_current, "resolve_source", changed)
    with pytest.raises(ValueError, match="stale"):
        show(db, "changed", SUBJECT)


def test_source_reserves_two_rechecks_without_duplicate_observation(tmp_path, monkeypatch):
    from chess_coach import objective_pin_snapshot, pin_observation

    db, evidence, _, _ = fixture(tmp_path / "source-count.sqlite", monkeypatch)
    calls = []
    observer = pin_observation.proven
    snapshot = objective_pin_snapshot.proven

    def observe(*args):
        calls.append("observe")
        return observer(*args)

    def certify(*args):
        calls.append("certificate")
        return snapshot(*args)

    monkeypatch.setattr(pin_observation, "proven", observe)
    monkeypatch.setattr(objective_pin_snapshot, "proven", certify)
    source = source_for_evidence(db, SUBJECT, evidence)
    assert calls == ["observe", "certificate"]
    assert source["source_work_reservation"] == {"root_proofs": 2, "pin_geometry_limit": 8}


def test_public_lines_filter_wrong_operation_and_keep_only_certified_branch(tmp_path, monkeypatch):
    from chess_coach.related_pin_match import scorer

    db, evidence, fen, full = fixture(tmp_path / "public.sqlite", monkeypatch, public_only=True)
    source = source_for_evidence(db, SUBJECT, evidence)
    board = chess.Board(fen)
    words = full.split()
    board.push_uci(words[0])
    good = " ".join(words[1:])
    creation = board.parse_uci(words[1])
    board.push(creation)
    defense = board.parse_uci(words[2])
    board.push(defense)
    alternate = next(move.uci() for move in board.legal_moves if move.uci() != words[3])
    bad = " ".join((words[1], words[2], alternate))
    prompt = chess.Board(fen)
    prompt.push_uci(words[0])
    wrong = {"type": "public", "objective": "promotion", "fen": prompt.fen(), "lines": [good]}
    assert scorer(create())(wrong, source["features"], set(), None) is None
    db.connection.execute("""INSERT INTO public_collections(version,source_url,source_revision,source_sha256,
        content_sha256,content_format,license,attribution,license_notice,accepted,excluded,state)
        VALUES('public-v1','https://example.invalid','v1','a','b','fen_csv','CC0-1.0','fixture','notice',1,0,'staging')""")
    collection = db.connection.execute(
        "SELECT id FROM public_collections WHERE version='public-v1'"
    ).fetchone()[0]
    db.connection.execute(
        "INSERT INTO public_tasks VALUES(?,?,?,?,?)",
        (collection, "public-pin", prompt.fen(), "legal_line", json.dumps([bad, good])),
    )
    db.connection.execute("UPDATE public_collections SET state='ready' WHERE id=?", (collection,))
    db.connection.commit()
    result = preview(db, SUBJECT, evidence, "test")
    assert len(result["items"]) == 1 and result["items"][0]["type"] == "public"
    state = start_related(
        db,
        attempt_id="public",
        subject=SUBJECT,
        evidence_id=evidence,
        corpus_version="test",
        reference=result["items"][0]["reference"],
    )
    assert state["objective"] == "legal_line"
    saved = json.loads(
        db.connection.execute(
            "SELECT lines_json FROM unified_sessions WHERE attempt_id='public'"
        ).fetchone()[0]
    )
    assert saved == [good.split()]


def test_partial_budget_is_disclosed_and_no_fallback_is_invented(tmp_path, monkeypatch):
    from chess_coach import related_pin_budget

    db, evidence, _, _ = fixture(tmp_path / "partial.sqlite", monkeypatch)
    monkeypatch.setattr(related_pin_budget, "LINE_LIMIT", 0)
    result = preview(db, SUBJECT, evidence, "test")
    assert result["pin_scan"]["truncated"] and result["items"] == []
    assert result["status"] == "partial: candidate proof budget exhausted"


def test_setup_preserves_castling_and_unsupported_en_passant_is_unknown():
    from chess_coach.related_pin_candidates import prompt

    fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR b KQkq - 0 1"
    item = {"type": "corpus", "fen": fen, "solution": "e7e6 d2d3 a7a6 g2g3"}
    board, lines = prompt(item)
    assert board.has_kingside_castling_rights(chess.WHITE)
    assert board.has_queenside_castling_rights(chess.BLACK)
    assert lines == ["d2d3 a7a6 g2g3"]
    board, lines = prompt({**item, "solution": "e7e5 d2d3 a7a6 g2g3"})
    assert board.ep_square == chess.E6
    budget = create()
    assert candidate_line(board, lines[0].split(), {}, budget) is None
    assert budget["unknown"] == 1 and budget["root_proofs"] == 0


def test_candidate_is_not_accepted_without_its_own_proof(tmp_path, monkeypatch):
    from chess_coach import related_pin_certificate

    db, evidence, _, _ = fixture(tmp_path / "separate.sqlite", monkeypatch)
    monkeypatch.setattr(related_pin_certificate, "proven", lambda *_: [])
    result = preview(db, SUBJECT, evidence, "test")
    assert result["items"] == [] and result["pin_scan"]["unknown"] == 1


def test_public_checkmate_line_is_only_a_legal_line_session(tmp_path, monkeypatch):
    db, evidence, fen, full = fixture(
        tmp_path / "public-mate.sqlite", monkeypatch, public_only=True
    )
    words = full.split()
    board = chess.Board(fen)
    board.push_uci(words[0])
    prompt = board.fen()
    for move in words[1:]:
        board.push_uci(move)
    assert board.is_checkmate()
    db.connection.execute("""INSERT INTO public_collections(version,source_url,source_revision,source_sha256,
        content_sha256,content_format,license,attribution,license_notice,accepted,excluded,state)
        VALUES('public-mate','https://example.invalid','v1','a','b','fen_csv','CC0-1.0','fixture','notice',1,0,'staging')""")
    collection = db.connection.execute(
        "SELECT id FROM public_collections WHERE version='public-mate'"
    ).fetchone()[0]
    db.connection.execute(
        "INSERT INTO public_tasks VALUES(?,?,?,?,?)",
        (collection, "fixture", prompt, "checkmate", json.dumps([" ".join(words[1:])])),
    )
    db.connection.execute("UPDATE public_collections SET state='ready' WHERE id=?", (collection,))
    db.connection.commit()
    result = preview(db, SUBJECT, evidence, "test")
    state = start_related(
        db,
        attempt_id="public-mate",
        subject=SUBJECT,
        evidence_id=evidence,
        corpus_version="test",
        reference=result["items"][0]["reference"],
    )
    assert state["source_type"] == "public" and state["objective"] == "legal_line"
    first = submit(db, "public-mate", SUBJECT, event_id="first", move=words[1])
    assert first["status"] == "active"
    last = submit(db, "public-mate", SUBJECT, event_id="last", move=words[3])
    assert last["status"] == "line_completed"
    assert db.connection.execute("SELECT COUNT(*) FROM objective_requests").fetchone()[0] == 0


def test_cli_and_private_browser_preview_csrf_and_start(tmp_path, monkeypatch, capsys):
    import sys

    from chess_coach.cli import main
    from chess_coach.web import create_app

    path = tmp_path / "clients.sqlite"
    db, evidence, _, _ = fixture(path, monkeypatch)
    chosen = preview(db, SUBJECT, evidence, "test")
    reference = chosen["items"][0]["reference"]
    db.close()
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "chess-coach",
            "--db",
            str(path),
            "related-pins",
            "--subject",
            SUBJECT,
            "--evidence",
            str(evidence),
            "--corpus",
            "test",
        ],
    )
    main()
    assert json.loads(capsys.readouterr().out)["items"][0]["reference"] == reference
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "chess-coach",
            "--db",
            str(path),
            "start-related-pin",
            "--subject",
            SUBJECT,
            "--evidence",
            str(evidence),
            "--corpus",
            "test",
            "--attempt",
            "cli",
            "--reference",
            reference,
        ],
    )
    main()
    assert json.loads(capsys.readouterr().out)["objective"] == "legal_line"
    path = tmp_path / "browser.sqlite"
    db, evidence, _, _ = fixture(path, monkeypatch)
    reference = preview(db, SUBJECT, evidence, "test")["items"][0]["reference"]
    db.close()
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
    source = client.get(f"/evidence/{evidence}", base_url="https://coach.invalid", headers=headers)
    assert source.status_code == 200 and b"Find related pin practice" in source.data
    page = client.get(
        f"/evidence/{evidence}/related-pins", base_url="https://coach.invalid", headers=headers
    )
    assert page.status_code == 200 and b"Practice this pin pattern" in page.data
    with client.session_transaction(base_url="https://coach.invalid") as session:
        csrf = session["csrf"]
    url = f"/evidence/{evidence}/related-pins/start"
    data = {"csrf": csrf, "reference": reference}
    assert (
        client.post(url, base_url="https://coach.invalid", headers=headers, data=data).status_code
        == 403
    )
    response = client.post(
        url,
        base_url="https://coach.invalid",
        headers=headers | {"Origin": "https://coach.invalid"},
        data=data,
    )
    assert response.status_code == 303
    assert (
        client.get(
            response.headers["Location"], base_url="https://coach.invalid", headers=headers
        ).status_code
        == 200
    )


def test_grounded_pin_lesson_offers_transfer(tmp_path):
    from flask import render_template

    from chess_coach.web import create_app

    app = create_app(
        db_path=tmp_path / "unused.sqlite",
        subject="fixture",
        actor="fixture",
        corpus="test",
        login="fixture",
        origin="https://coach.invalid",
    )
    lesson = {
        "family": "pin-execute-mapper",
        "qualification": "bounded",
        "possible": "possible",
        "question": "question",
        "habit": "habit",
        "practice": "practice",
        "examples": [
            {
                "evidence_id": 1,
                "position_id": 1,
                "game_id": 1,
                "ply": 1,
                "review": "unreviewed",
                "played": "move",
                "operation": "execute",
                "facts": [],
                "lines": [],
            }
        ],
    }
    with app.test_request_context():
        page = render_template("lesson_body.html", lesson=lesson, csrf="fixture")
    assert "Find related pin practice" in page and "related-pins" in page


def test_owned_source_rechecks_review_after_snapshot(tmp_path, monkeypatch):
    from chess_coach import objective_pin_source
    from chess_coach.objective_pin_contract import VERSION

    db, evidence, _, _ = fixture(tmp_path / "snapshot-race.sqlite", monkeypatch)
    original = objective_pin_source.snapshot

    def changing_snapshot(*args):
        result = original(*args)
        review_evidence(db, evidence, decision="reject", actor="fixture_reviewer")
        return result

    monkeypatch.setattr(objective_pin_source, "snapshot", changing_snapshot)
    with pytest.raises(ValueError, match="changed"):
        objective_pin_source.resolve(db, VERSION, str(evidence), SUBJECT)


def test_exhausted_budget_stops_candidate_processing(monkeypatch):
    from chess_coach import related_pin_match

    budget = create()
    budget["truncated"] = True

    def unexpected(*_args):
        raise AssertionError("candidate work after budget exhaustion")

    monkeypatch.setattr(related_pin_match, "_candidate", unexpected)
    assert related_pin_match.scorer(budget)({}, {}, set(), None) is None
