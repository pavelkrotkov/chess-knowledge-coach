"""End-to-end source-bound unfamiliar capture practice."""

import json

import pytest

from chess_coach.evidence_review import review_evidence
from chess_coach.material_detector import process_decision
from chess_coach.related_capture import _selection, preview
from chess_coach.related_capture_start import start_related
from chess_coach.unified_session_events import submit
from chess_coach.web import create_app
from tests.fork_concealment_support import assert_collision, assert_concealed
from tests.test_material_pipeline import LEARNER, make_game
from tests.transfer_concealment_support import binding_text, preview_text
from tests.transfer_expected_support import expected_binding


def fixture(tmp_path, monkeypatch):
    db = make_game(tmp_path / "transfer.sqlite", monkeypatch)
    evidence = process_decision(db, 1, LEARNER)["evidence_ids"][0]
    db.connection.execute(
        "INSERT INTO puzzle_corpora(version,source,checksum,state) VALUES('test','fixture','checksum','staging')"
    )
    corpus_id = db.connection.execute(
        "SELECT id FROM puzzle_corpora WHERE version='test'"
    ).fetchone()[0]
    db.connection.execute(
        """INSERT INTO puzzles(puzzle_id,corpus_id,fen,source,solution,rating,rating_deviation,themes_json,objective)
        VALUES('capture',?,'1k6/8/8/8/4q3/8/8/4R1K1 b - - 0 1','https://lichess.org/testgame','b8a8 e1e4',1200,80,'["hangingPiece"]','unknown')""",
        (corpus_id,),
    )
    db.connection.execute(
        "INSERT INTO puzzle_themes VALUES(?,'capture','hangingPiece',1200)", (corpus_id,)
    )
    db.connection.execute("UPDATE puzzle_corpora SET state='ready' WHERE id=?", (corpus_id,))
    db.connection.commit()
    return db, evidence


def test_capture_preview_start_and_review_invalidation(tmp_path, monkeypatch):
    db, evidence = fixture(tmp_path, monkeypatch)
    result = preview(db, LEARNER, 1, "test")
    assert result["status"] == "available" and result["baseline"] is None
    item = result["items"][0]
    assert item["fen"].split()[1] == "w"
    assert "e1e4" not in preview_text(result, _selection(db, LEARNER, 1, "test"))
    assert "key" not in item and result["review_status"] == "unreviewed"
    review_evidence(db, evidence, decision="reject", actor="fixture_reviewer")
    with pytest.raises(ValueError):
        start_related(
            db,
            attempt_id="stale",
            subject=LEARNER,
            position=1,
            corpus_version="test",
            reference=item["reference"],
        )
    assert db.connection.execute("SELECT COUNT(*) FROM unified_sessions").fetchone()[0] == 0
    review_evidence(db, evidence, decision="accept", actor="fixture_reviewer")
    result = preview(db, LEARNER, 1, "test")
    reference = result["items"][0]["reference"]
    with pytest.raises(ValueError):
        start_related(
            db,
            attempt_id="foreign",
            subject="other",
            position=1,
            corpus_version="test",
            reference=reference,
        )
    state = start_related(
        db,
        attempt_id="valid",
        subject=LEARNER,
        position=1,
        corpus_version="test",
        reference=reference,
    )
    assert state["status"] == "active" and "source_key" not in state
    assert submit(db, "valid", LEARNER, event_id="m", move="e1e4")["status"] == "line_completed"
    assert preview(db, LEARNER, 1, "test")["items"] == []
    assert db.connection.execute("SELECT COUNT(*) FROM training_attempts").fetchone()[0] == 0


@pytest.mark.parametrize("collision", ["none", "reference", "csrf"])
def test_browser_preview_and_safe_start(tmp_path, monkeypatch, collision):
    db, _ = fixture(tmp_path, monkeypatch)
    if collision == "reference":
        monkeypatch.setattr("chess_coach.related_capture.digest", lambda value: "e1e4" + "a" * 60)
        monkeypatch.setattr(
            "chess_coach.related_transfer_admission.digest", lambda value: "e1e4" + "a" * 60
        )
    expected = preview(db, LEARNER, 1, "test")["items"][0]["reference"]
    db.close()
    csrf_value = ("e1e4" + "A" * 39) if collision == "csrf" else "A" * 43
    monkeypatch.setattr(
        "chess_coach.web_security.secrets.token_urlsafe",
        lambda n: csrf_value if n == 32 else "B" * 32,
    )
    app = create_app(
        db_path=tmp_path / "transfer.sqlite",
        subject=LEARNER,
        actor="operator",
        corpus="test",
        login="fixture",
        origin="https://coach.invalid",
    )
    client = app.test_client()
    headers = {"Tailscale-User-Login": "fixture"}
    decision = client.get("/decisions/1", base_url="https://coach.invalid", headers=headers)
    assert decision.status_code == 200 and b"/decisions/1/related-captures" in decision.data
    page = client.get(
        "/decisions/1/related-captures", base_url="https://coach.invalid", headers=headers
    )
    assert b"provisional" in page.data
    with client.session_transaction(base_url="https://coach.invalid") as session:
        session_csrf = session["csrf"]
    assert_collision(page, collision, answer=b"e1e4")
    assert_concealed(page, session_csrf, expected, answer=b"e1e4")
    data = {"csrf": session_csrf, "reference": expected}
    assert (
        client.post(
            "/decisions/1/related-captures/start",
            base_url="https://coach.invalid",
            headers=headers,
            data=data,
        ).status_code
        == 403
    )
    response = client.post(
        "/decisions/1/related-captures/start",
        base_url="https://coach.invalid",
        headers=headers | {"Origin": "https://coach.invalid"},
        data=data,
    )
    assert response.status_code == 303
    practice = client.get(
        response.headers["Location"], base_url="https://coach.invalid", headers=headers
    )
    assert_concealed(practice, session_csrf, answer=b"e1e4")


def test_public_prompts_cursor_and_diversity_follow_review_and_familiarity(tmp_path, monkeypatch):
    db, evidence = fixture(tmp_path, monkeypatch)
    db.connection.execute("""INSERT INTO public_collections(version,source_url,source_revision,source_sha256,
        content_sha256,content_format,license,attribution,license_notice,accepted,excluded,state)
        VALUES('public-v1','https://example.invalid','v1','a','b','fen_csv','CC0-1.0','fixture','notice',7,0,'staging')""")
    collection = db.connection.execute(
        "SELECT id FROM public_collections WHERE version='public-v1'"
    ).fetchone()[0]
    for index, file in enumerate("bcdefgh"):
        import chess

        board = chess.Board("k7/8/8/8/4q3/8/8/4R1K1 w - - 0 1")
        board.set_piece_at(chess.parse_square(file + "7"), chess.Piece(chess.PAWN, chess.BLACK))
        db.connection.execute(
            "INSERT INTO public_tasks VALUES(?,?,?,?,?)",
            (
                collection,
                "answer-e1e4-" + str(index),
                board.fen(),
                "legal_line",
                json.dumps(["e1e4"]),
            ),
        )
    db.connection.execute("UPDATE public_collections SET state='ready' WHERE id=?", (collection,))
    db.connection.commit()
    first = preview(db, LEARNER, 1, "test")
    assert len(first["items"]) == 4 and first["next_cursor"]
    assert "e1e4" not in preview_text(first, _selection(db, LEARNER, 1, "test"))
    second = preview(db, LEARNER, 1, "test", first["next_cursor"])
    assert second["items"] and not (
        {i["fen"] for i in first["items"]} & {i["fen"] for i in second["items"]}
    )
    assert preview(db, LEARNER, 1, "test", first["next_cursor"]) == second
    review_evidence(db, evidence, decision="accept", actor="fixture_reviewer")
    with pytest.raises(ValueError, match="cursor"):
        preview(db, LEARNER, 1, "test", first["next_cursor"])
    with pytest.raises(ValueError):
        start_related(
            db,
            attempt_id="stale-review",
            subject=LEARNER,
            position=1,
            corpus_version="test",
            reference=first["items"][0]["reference"],
        )


def test_pattern_cue_is_durable_and_revocation_blocks_resumed_session(tmp_path, monkeypatch):
    from chess_coach.unified_session_events import show

    db, evidence = fixture(tmp_path, monkeypatch)
    review_evidence(db, evidence, decision="accept", actor="fixture_reviewer")
    choice = preview(db, LEARNER, 1, "test")["items"][0]
    selected = _selection(db, LEARNER, 1, "test")
    start_related(
        db,
        attempt_id="cued",
        subject=LEARNER,
        position=1,
        corpus_version="test",
        reference=choice["reference"],
    )
    row = db.connection.execute(
        "SELECT provenance_json FROM unified_sessions WHERE attempt_id='cued'"
    ).fetchone()
    binding = json.loads(row["provenance_json"])["related_capture"]
    assert binding["pattern_cued"] is True and binding["motif"] == "material_capture"
    assert binding["operation"] == "execute" and binding["rank_version"] == "capture-transfer-v1"
    assert binding["evidence_id"] == evidence
    expected = expected_binding(db, selected, choice["reference"], LEARNER, fork=False)
    assert "e1e4" not in binding_text(binding, expected)
    review_evidence(db, evidence, decision="revoke", actor="fixture_reviewer")
    with pytest.raises(ValueError, match="stale"):
        show(db, "cued", LEARNER)
    with pytest.raises(ValueError, match="stale"):
        submit(db, "cued", LEARNER, event_id="move", move="e1e4")
    assert db.connection.execute("SELECT COUNT(*) FROM unified_session_events").fetchone()[0] == 0


def test_indexed_familiarity_respects_color_castling_en_passant_and_owner(tmp_path):
    from chess_coach.db import Database
    from chess_coach.related_capture_familiar import familiarity
    from chess_coach.related_capture_position import prompt_key

    db = Database(tmp_path / "familiarity.sqlite")
    db.initialize()
    pgn = '[White "fixture_learner"]\n[Black "fixture_opponent"]\n[Result "*"]\n\n*'
    db.connection.execute(
        "INSERT INTO games(pgn,white,black,result) VALUES(?,?,?,'*')",
        (pgn, LEARNER, "fixture_opponent"),
    )
    cases = ["r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 17 23", "4k3/8/8/3pP3/8/8/8/4K3 w - d6 0 2"]
    db.connection.executemany(
        "INSERT INTO positions(game_id,ply,fen,san,uci) VALUES(1,?,?, 'x','a1a2')",
        [(i, fen) for i, fen in enumerate(cases, 1)],
    )
    db.connection.commit()
    _, _, known = familiarity(db, LEARNER)
    assert all(known(prompt_key(fen)) for fen in cases)
    assert not known(prompt_key("r3k2r/8/8/8/8/8/8/R3K2R w - - 17 23"))
    assert not known(prompt_key("r3k2r/8/8/8/8/8/8/R3K2R b KQkq - 17 23"))
    assert not known(prompt_key("4k3/8/8/3pP3/8/8/8/4K3 w - - 0 2"))
    _, _, other = familiarity(db, "fixture_other")
    assert not other(prompt_key(cases[0]))
    plan = db.connection.execute(
        """EXPLAIN QUERY PLAN SELECT 1 FROM positions p INDEXED BY idx_positions_fen_game
        JOIN games g ON g.id=p.game_id WHERE p.fen>=? AND p.fen<?
        AND (lower(g.white)=? OR lower(g.black)=?) LIMIT 1""",
        ("a", "b", LEARNER, LEARNER),
    ).fetchall()
    assert any("idx_positions_fen_game" in row[3] for row in plan)
