"""Current mate observations retrieve only legal source-bound mating witnesses."""

import json

import chess
import pytest

from chess_coach.evidence_review import review_evidence
from chess_coach.mate_auto import process_decision
from chess_coach.mate_contract import MAPPER
from chess_coach.related_mate import preview, selection
from chess_coach.related_mate_features import corpus_features, mate_features
from chess_coach.related_mate_source import source_for_evidence
from chess_coach.related_mate_start import start_related
from chess_coach.unified_session_events import show, submit
from tests.test_mate_proof import FEN, owned_game
from tests.transfer_concealment_support import preview_text

SHORT = "7k/5Q2/6K1/8/8/8/8/8 w - - 0 1"


def fixture(path, monkeypatch, black, short, *, duplicate=False):
    fen = SHORT if short else FEN
    if black:
        fen = chess.Board(fen).mirror().fen()
    move = ("Qa2" if black else "Qa7") if short else ("Qg2#" if black else "Qg7#")
    subject = "fixture_b" if black else "fixture_a"
    db = owned_game(path, monkeypatch, fen=fen, move=move)
    process_decision(db, 1, subject)
    evidence = db.connection.execute(
        "SELECT e.id FROM evidence_mappings e JOIN mapping_runs r ON r.id=e.mapping_run_id WHERE r.producer=?",
        (MAPPER,),
    ).fetchone()[0]
    source = source_for_evidence(db, subject, evidence)
    db.connection.execute(
        "INSERT INTO puzzle_corpora(version,source,checksum,state) VALUES('test','fixture','checksum','staging')"
    )
    corpus = db.connection.execute("SELECT id FROM puzzle_corpora WHERE version='test'").fetchone()[
        0
    ]
    pre, setup = _candidate(source)
    line = setup + " " + source["lines"][0]
    theme = "mateIn2" if short else "mateIn1"
    db.connection.execute(
        """INSERT INTO puzzles(puzzle_id,corpus_id,fen,source,solution,rating,rating_deviation,themes_json,objective)
        VALUES('fixture-puzzle',?,?,'https://example.invalid',?,1200,80,'[]','unknown')""",
        (corpus, pre, line),
    )
    db.connection.execute(
        "INSERT INTO puzzle_themes VALUES(?,?,?,1200)", (corpus, "fixture-puzzle", theme)
    )
    if duplicate:
        db.connection.execute(
            """INSERT INTO puzzles(puzzle_id,corpus_id,fen,source,solution,rating,rating_deviation,themes_json,objective)
            SELECT 'duplicate',corpus_id,fen,source,solution,rating,rating_deviation,themes_json,objective
            FROM puzzles WHERE puzzle_id='fixture-puzzle'"""
        )
        db.connection.execute(
            "INSERT INTO puzzle_themes SELECT corpus_id,'duplicate',theme,rating FROM puzzle_themes WHERE puzzle_id='fixture-puzzle'"
        )
    db.connection.execute("UPDATE puzzle_corpora SET state='ready' WHERE id=?", (corpus,))
    db.connection.commit()
    return db, evidence, subject


def _candidate(source):
    source_shape = mate_features(source["prompt_fen"], source["lines"][0].split())
    for file in "abcdefgh":
        board = chess.Board(source["prompt_fen"])
        board.turn = not board.turn
        rank = "2" if board.turn else "7"
        destination = "3" if board.turn else "6"
        origin = chess.parse_square(file + rank)
        if board.piece_at(origin):
            continue
        board.set_piece_at(origin, chess.Piece(chess.PAWN, board.turn))
        setup = file + rank + file + destination
        if not board.is_valid() or chess.Move.from_uci(setup) not in board.legal_moves:
            continue
        prompt, shape = corpus_features(board.fen(), setup + " " + source["lines"][0])
        if (
            prompt
            and shape
            and all(shape[k] == source_shape[k] for k in ("mover", "target", "timing", "geometry"))
        ):
            return board.fen(), setup
    raise AssertionError("no synthetic candidate")


@pytest.mark.parametrize("black", [False, True])
@pytest.mark.parametrize("short", [False, True])
def test_transfer_is_source_bound_playable_and_revoked(tmp_path, monkeypatch, black, short):
    db, evidence, subject = fixture(tmp_path / "mate.sqlite", monkeypatch, black, short)
    result = preview(db, subject, evidence, "test")
    assert result["status"] == "available" and len(result["items"]) == 1
    assert result["scanned"] == 1
    assert result["mate_timing"] == ("mate_within_two" if short else "mate_in_one")
    assert "fixture-puzzle" not in json.dumps(result)
    source = source_for_evidence(db, subject, evidence)
    assert source["lines"][0].split()[0] not in preview_text(
        result, selection(db, subject, evidence, "test")
    )
    reference = result["items"][0]["reference"]
    with pytest.raises(ValueError):
        preview(db, "fixture_other", evidence, "test")
    state = start_related(
        db,
        attempt_id="fixture",
        subject=subject,
        evidence_id=evidence,
        corpus_version="test",
        reference=reference,
    )
    assert state["status"] == "active" and state["objective"] == "checkmate"
    familiar = preview(db, subject, evidence, "test")
    assert familiar["items"] == [] and familiar["excluded"]["familiar"] == 1
    assert "insufficient" in familiar["status"]
    record = db.connection.execute(
        "SELECT lines_json,provenance_json FROM unified_sessions WHERE attempt_id='fixture'"
    ).fetchone()
    line = json.loads(record["lines_json"])[0]
    binding = json.loads(record["provenance_json"])["related_mate"]
    assert binding["operation"] == "execute" and binding["pattern_cued"]
    assert binding["mate_timing"] == result["mate_timing"]
    result = submit(db, "fixture", subject, event_id="first", move=line[0])
    if short:
        assert result["status"] == "active"
        result = submit(db, "fixture", subject, event_id="last", move=line[-1])
    assert result["status"] == "objective_verified" and chess.Board(result["fen"]).is_checkmate()
    assert db.connection.execute("SELECT COUNT(*) FROM training_attempts").fetchone()[0] == 0
    review_evidence(db, evidence, decision="reject", actor="fixture_reviewer")
    with pytest.raises(ValueError, match="stale"):
        show(db, "fixture", subject)


def test_unlisted_legal_move_is_unresolved(tmp_path, monkeypatch):
    db, evidence, subject = fixture(tmp_path / "unlisted.sqlite", monkeypatch, False, False)
    reference = preview(db, subject, evidence, "test")["items"][0]["reference"]
    other = start_related(
        db,
        attempt_id="unlisted",
        subject=subject,
        evidence_id=evidence,
        corpus_version="test",
        reference=reference,
    )
    stored = db.connection.execute(
        "SELECT lines_json FROM unified_sessions WHERE attempt_id='unlisted'"
    ).fetchone()
    expected = json.loads(stored[0])[0][0]
    alternative = next(
        move.uci() for move in chess.Board(other["fen"]).legal_moves if move.uci() != expected
    )
    unknown = submit(db, "unlisted", subject, event_id="other", move=alternative)
    assert unknown["feedback"] == "needs_verification"
    assert db.connection.execute("SELECT COUNT(*) FROM objective_requests").fetchone()[0] == 0


def test_terminal_witness_timing_and_setup_are_not_tags():
    setup = "7k/p7/5KQ1/8/8/8/8/8 b - - 0 1"
    prompt, feature = corpus_features(setup, "a7a6 g6g7")
    assert feature and feature["timing"] == 1 and chess.Board(prompt).turn == chess.WHITE
    assert corpus_features(setup, "a7a6 g6g1") == (prompt, None)
    assert corpus_features(setup, "a7a6 g6g7 a6a5") == (None, None)
    board = chess.Board(prompt).mirror()
    mirrored = chess.Move(chess.square_mirror(chess.G6), chess.square_mirror(chess.G7)).uci()
    assert mate_features(board.fen(), [mirrored])["geometry"] == feature["geometry"]


@pytest.mark.parametrize("black", [False, True])
def test_promoted_checker_and_discovered_double_mate_roles(black):
    from chess_coach.related_mate_score import match

    def features(fen, uci):
        board = chess.Board(fen)
        move = chess.Move.from_uci(uci)
        if black:
            board = board.mirror()
            move = chess.Move(
                chess.square_mirror(move.from_square),
                chess.square_mirror(move.to_square),
                promotion=move.promotion,
            )
        result = mate_features(board.fen(), [move.uci()])
        board.push(move)
        assert board.is_checkmate()
        return result, board

    fen = "k7/6P1/1K6/8/8/8/8/8 w - - 0 1"
    queen, queen_board = features(fen, "g7g8q")
    rook, _ = features(fen, "g7g8r")
    assert queen["mover"] == rook["mover"] == chess.PAWN
    assert queen["target"] == (chess.QUEEN,)
    assert rook["target"] == (chess.ROOK,)
    assert queen["geometry"] != rook["geometry"]
    candidate = {"type": "public", "version": "fixture", "key": "mate"}
    prompt = queen_board.fen()
    assert match(candidate, queen, set(), None, prompt, rook) is None
    assert match(candidate, queen, set(), None, prompt, queen) is not None

    fen = "7k/5K2/7B/8/8/8/8/7R w - - 0 1"
    discovered, board = features(fen, "h6f8")
    double, double_board = features(fen, "h6g7")
    assert discovered["mover"] == double["mover"] == chess.BISHOP
    assert discovered["target"] == (chess.ROOK,)
    assert double["target"] == (chess.BISHOP, chess.ROOK)
    assert len(board.checkers()) == 1 and len(double_board.checkers()) == 2
    assert discovered["geometry"] != double["geometry"]
    assert match(candidate, discovered, set(), None, prompt, double) is None


def test_cursor_scope_changes_with_review(tmp_path, monkeypatch):
    db, evidence, subject = fixture(tmp_path / "review.sqlite", monkeypatch, False, False)
    result = preview(db, subject, evidence, "test")
    reference = result["items"][0]["reference"]
    review_evidence(db, evidence, decision="accept", actor="fixture_reviewer")
    assert selection(db, subject, evidence, "test")[4] != result["scope"]
    with pytest.raises(ValueError):
        start_related(
            db,
            attempt_id="stale",
            subject=subject,
            evidence_id=evidence,
            corpus_version="test",
            reference=reference,
        )


def test_setup_preserves_en_passant_and_castling_rights():
    ep = "7k/3p4/5KQ1/4P3/8/8/8/8 b - - 0 1"
    prompt, feature = corpus_features(ep, "d7d5 g6g7")
    assert feature and chess.Board(prompt).ep_square == chess.D6
    castle = "4k2r/p7/3K4/8/7Q/8/8/8 b k - 0 1"
    prompt, feature = corpus_features(castle, "a7a6 h4e7")
    assert feature and chess.Board(prompt).has_kingside_castling_rights(chess.BLACK)


def test_wrong_operation_and_stale_source_are_unavailable(tmp_path, monkeypatch):
    db, evidence, subject = fixture(tmp_path / "stale.sqlite", monkeypatch, False, False)
    db.connection.execute(
        "UPDATE mapping_runs SET operation='prevent' WHERE id=(SELECT mapping_run_id FROM evidence_mappings WHERE id=?)",
        (evidence,),
    )
    db.connection.commit()
    with pytest.raises(ValueError):
        preview(db, subject, evidence, "test")


def test_evidence_browser_entry_csrf_and_playable_session(tmp_path, monkeypatch):
    from chess_coach.web import create_app

    path = tmp_path / "browser.sqlite"
    db, evidence, subject = fixture(path, monkeypatch, False, False)
    reference = preview(db, subject, evidence, "test")["items"][0]["reference"]
    db.close()
    app = create_app(
        db_path=path,
        subject=subject,
        actor="fixture",
        corpus="test",
        login="fixture",
        origin="https://coach.invalid",
    )
    client = app.test_client()
    headers = {"Tailscale-User-Login": "fixture"}
    source = client.get(f"/evidence/{evidence}", base_url="https://coach.invalid", headers=headers)
    assert source.status_code == 200 and b"Find related mate practice" in source.data
    page = client.get(
        f"/evidence/{evidence}/related-mates", base_url="https://coach.invalid", headers=headers
    )
    assert (
        page.status_code == 200 and b"does not prove the result against every defense" in page.data
    )
    with client.session_transaction(base_url="https://coach.invalid") as session:
        csrf = session["csrf"]
    url = f"/evidence/{evidence}/related-mates/start"
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


def test_supplied_short_mate_line_is_a_witness_not_all_defenses():
    board = chess.Board()
    for san in ("e4", "e5", "Bc4", "Nc6"):
        board.push_san(san)
    line = ["d1h5", "g8f6", "h5f7"]
    assert mate_features(board.fen(), line)["timing"] == 3
    board.push_uci(line[0])
    alternative = chess.Move.from_uci("g7g6")
    assert alternative in board.legal_moves
    board.push(alternative)
    assert chess.Move.from_uci(line[-1]) not in board.legal_moves


def test_cli_preview_and_start(tmp_path, monkeypatch, capsys):
    import sys

    from chess_coach.cli import main

    path = tmp_path / "cli.sqlite"
    db, evidence, subject = fixture(path, monkeypatch, False, False)
    db.close()
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "chess-coach",
            "--db",
            str(path),
            "related-mates",
            "--subject",
            subject,
            "--evidence",
            str(evidence),
            "--corpus",
            "test",
        ],
    )
    main()
    reference = json.loads(capsys.readouterr().out)["items"][0]["reference"]
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "chess-coach",
            "--db",
            str(path),
            "start-related-mate",
            "--subject",
            subject,
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
    state = json.loads(capsys.readouterr().out)
    assert state["status"] == "active" and "source_key" not in state


def test_public_lines_are_filtered_and_wrong_operation_is_excluded(tmp_path, monkeypatch):
    from chess_coach.related_mate_match import candidate

    db, evidence, subject = fixture(tmp_path / "public.sqlite", monkeypatch, False, False)
    source = source_for_evidence(db, subject, evidence)
    pre, setup = _candidate(source)
    prompt, _ = corpus_features(pre, setup + " " + source["lines"][0])
    board = chess.Board(prompt)
    board.set_piece_at(chess.B2, chess.Piece(chess.PAWN, chess.WHITE))
    good = source["lines"][0]
    bad = next(
        move.uci() for move in board.legal_moves if mate_features(board.fen(), [move.uci()]) is None
    )
    shape = mate_features(source["prompt_fen"], source["lines"][0].split())
    wrong = {"type": "public", "objective": "promotion", "fen": board.fen(), "lines": [good]}
    assert candidate(wrong, shape, set(), None) is None
    db.connection.execute("""INSERT INTO public_collections(version,source_url,source_revision,source_sha256,
        content_sha256,content_format,license,attribution,license_notice,accepted,excluded,state)
        VALUES('public-v1','https://example.invalid','v1','a','b','fen_csv','CC0-1.0','fixture','notice',1,0,'staging')""")
    collection = db.connection.execute(
        "SELECT id FROM public_collections WHERE version='public-v1'"
    ).fetchone()[0]
    db.connection.execute(
        "INSERT INTO public_tasks VALUES(?,?,?,?,?)",
        (collection, "public-mate", board.fen(), "legal_line", json.dumps([bad, good])),
    )
    db.connection.execute("UPDATE public_collections SET state='ready' WHERE id=?", (collection,))
    db.connection.commit()
    result = preview(db, subject, evidence, "test")
    chosen = next(item for item in result["items"] if item["type"] == "public")
    state = start_related(
        db,
        attempt_id="public",
        subject=subject,
        evidence_id=evidence,
        corpus_version="test",
        reference=chosen["reference"],
    )
    assert state["objective"] == "checkmate"
    row = db.connection.execute(
        "SELECT lines_json FROM unified_sessions WHERE attempt_id='public'"
    ).fetchone()
    assert json.loads(row[0]) == [[good]]
    assert (
        submit(db, "public", subject, event_id="mate", move=good)["status"] == "objective_verified"
    )


def test_synthetic_yield_and_indexed_bounded_scan(tmp_path, monkeypatch):
    import time

    db, evidence, subject = fixture(tmp_path / "scan.sqlite", monkeypatch, False, False)
    started = time.perf_counter()
    result = preview(db, subject, evidence, "test")
    elapsed = time.perf_counter() - started
    assert (result["scanned"], len(result["items"])) == (1, 1)
    plan = db.connection.execute(
        """EXPLAIN QUERY PLAN SELECT p.* FROM puzzle_themes t
        JOIN puzzles p ON p.corpus_id=t.corpus_id AND p.puzzle_id=t.puzzle_id
        WHERE t.corpus_id=? AND t.theme=? AND t.rating BETWEEN ? AND ?
        ORDER BY t.rating,t.puzzle_id LIMIT 100""",
        (1, "mateIn1", 600, 2200),
    ).fetchall()
    assert any("idx_puzzle_themes_search" in row["detail"] for row in plan)
    print(
        f"synthetic match yield 1/1; bounded preview {elapsed * 1000:.1f} ms; indexed theme query"
    )


def test_duplicate_prompts_are_not_repeated(tmp_path, monkeypatch):
    db, evidence, subject = fixture(
        tmp_path / "duplicate.sqlite", monkeypatch, False, False, duplicate=True
    )
    result = preview(db, subject, evidence, "test")
    assert result["scanned"] == 2 and len(result["items"]) == 1
    assert result["excluded"]["duplicate"] == 1


def test_grounded_mate_lesson_offers_source_bound_entry(tmp_path):
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
        "family": "bounded-mate-observation-mapper",
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
        page = render_template("lesson_body.html", lesson=lesson)
    assert "Find related mate practice" in page and "related-mates" in page
