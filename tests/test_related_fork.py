"""Fork transfer uses the selected owned fact and legal supplied-line mechanism."""

import json

import chess
import pytest

from chess_coach.evidence_review import review_evidence
from chess_coach.fork_detector import process_decision
from chess_coach.related_fork import preview, selection
from chess_coach.related_fork_features import corpus_fork_features, fork_features
from chess_coach.related_fork_start import start_related
from chess_coach.unified_session_events import show, submit
from chess_coach.web import create_app
from tests.fork_concealment_support import assert_collision, assert_concealed
from tests.test_fork_pipeline import LEARNER, make_game
from tests.transfer_concealment_support import binding_text, preview_text
from tests.transfer_expected_support import expected_binding

PRE = "r2k4/6pp/8/1N6/8/8/6P1/7K b - - 0 1"
LINE = "d8e8 b5c7 e8f8 c7a8"


def fixture(tmp_path, monkeypatch, played="h1g1"):
    db, _ = make_game(tmp_path / "fork-transfer.sqlite", monkeypatch, played=played)
    evidence = process_decision(db, 1, LEARNER)["evidence_ids"][0]
    db.connection.execute(
        "INSERT INTO puzzle_corpora(version,source,checksum,state) VALUES('test','fixture','checksum','staging')"
    )
    corpus = db.connection.execute("SELECT id FROM puzzle_corpora WHERE version='test'").fetchone()[
        0
    ]
    rows = [("fork-good", PRE, LINE), ("fork-bad", PRE, "d8e8 h1g1 e8f8 g2g3")]
    for key, fen, line in rows:
        db.connection.execute(
            """INSERT INTO puzzles(puzzle_id,corpus_id,fen,source,solution,rating,rating_deviation,themes_json,objective)
            VALUES(?,?,?,'https://example.invalid',?,1200,80,'["fork"]','unknown')""",
            (key, corpus, fen, line),
        )
        db.connection.execute("INSERT INTO puzzle_themes VALUES(?,?,'fork',1200)", (corpus, key))
    db.connection.execute("UPDATE puzzle_corpora SET state='ready' WHERE id=?", (corpus,))
    db.connection.commit()
    return db, evidence


def test_source_bound_fork_transfer_and_review_invalidation(tmp_path, monkeypatch):
    db, evidence = fixture(tmp_path, monkeypatch)
    result = preview(db, LEARNER, evidence, "test")
    assert result["status"] == "available" and result["source_outcome"] == "failure"
    assert len(result["items"]) == 1 and result["scanned"] == 2
    assert "b5c7" not in preview_text(result, selection(db, LEARNER, evidence, "test"))
    assert "fork-good" not in json.dumps(result)
    reference = result["items"][0]["reference"]
    with pytest.raises(ValueError):
        start_related(
            db,
            attempt_id="foreign",
            subject="fixture_other",
            evidence_id=evidence,
            corpus_version="test",
            reference=reference,
        )
    review_evidence(db, evidence, decision="accept", actor="fixture_reviewer")
    with pytest.raises(ValueError):
        start_related(
            db,
            attempt_id="stale",
            subject=LEARNER,
            evidence_id=evidence,
            corpus_version="test",
            reference=reference,
        )
    chosen = preview(db, LEARNER, evidence, "test")["items"][0]
    selected = selection(db, LEARNER, evidence, "test")
    state = start_related(
        db,
        attempt_id="fork",
        subject=LEARNER,
        evidence_id=evidence,
        corpus_version="test",
        reference=chosen["reference"],
    )
    assert state["status"] == "active" and "source_key" not in state
    record = db.connection.execute(
        "SELECT provenance_json FROM unified_sessions WHERE attempt_id='fork'"
    ).fetchone()
    binding = json.loads(record["provenance_json"])["related_fork"]
    assert (binding["motif"], binding["operation"], binding["pattern_cued"]) == (
        "fork",
        "execute",
        True,
    )
    assert binding["evidence_id"] == evidence
    expected = expected_binding(db, selected, chosen["reference"], LEARNER, fork=True)
    assert "b5c7" not in binding_text(binding, expected)
    review_evidence(db, evidence, decision="revoke", actor="fixture_reviewer")
    with pytest.raises(ValueError, match="stale"):
        show(db, "fork", LEARNER)
    with pytest.raises(ValueError, match="stale"):
        submit(db, "fork", LEARNER, event_id="m", move="b5c7")
    assert db.connection.execute("SELECT COUNT(*) FROM unified_session_events").fetchone()[0] == 0


def test_success_source_keeps_outcome_distinct(tmp_path, monkeypatch):
    db, evidence = fixture(tmp_path, monkeypatch, played="b5c7")
    assert preview(db, LEARNER, evidence, "test")["source_outcome"] == "success"


def test_setup_colors_and_full_line_legality():
    prompt, shape = corpus_fork_features(PRE, LINE)
    assert prompt.split()[1] == "w" and shape is not None
    board = chess.Board(prompt).mirror()
    source = [chess.Move.from_uci(move) for move in LINE.split()[1:]]
    mirrored = [
        chess.Move(
            chess.square_mirror(m.from_square), chess.square_mirror(m.to_square), m.promotion
        ).uci()
        for m in source
    ]
    black = fork_features(board.fen(), mirrored)
    assert black is not None and (shape["mover"], shape["target"], shape["geometry"]) == (
        black["mover"],
        black["target"],
        black["geometry"],
    )
    assert corpus_fork_features(PRE, "d8e8 b5c7 e8f8 c7a8 a2a4 h7h5") == (None, None)
    assert fork_features(prompt, ["h1g1", "e8f8", "b5c7"]) is None


@pytest.mark.parametrize("collision", ["none", "reference", "csrf"])
def test_browser_entry_from_evidence_and_protected_start(tmp_path, monkeypatch, collision):
    db, evidence = fixture(tmp_path, monkeypatch)
    if collision == "reference":
        monkeypatch.setattr("chess_coach.related_capture.digest", lambda value: "b5c7" + "a" * 60)
        monkeypatch.setattr(
            "chess_coach.related_transfer_admission.digest", lambda value: "b5c7" + "a" * 60
        )
    expected = preview(db, LEARNER, evidence, "test")["items"][0]["reference"]
    db.close()
    csrf_value = ("b5c7" + "A" * 39) if collision == "csrf" else "A" * 43
    monkeypatch.setattr(
        "chess_coach.web_security.secrets.token_urlsafe",
        lambda n: csrf_value if n == 32 else "B" * 32,
    )
    app = create_app(
        db_path=tmp_path / "fork-transfer.sqlite",
        subject=LEARNER,
        actor="operator",
        corpus="test",
        login="fixture",
        origin="https://coach.invalid",
    )
    client = app.test_client()
    headers = {"Tailscale-User-Login": "fixture"}
    source = client.get(f"/evidence/{evidence}", base_url="https://coach.invalid", headers=headers)
    assert source.status_code == 200 and b"Find related fork practice" in source.data
    page = client.get(
        f"/evidence/{evidence}/related-forks", base_url="https://coach.invalid", headers=headers
    )
    assert b"missed fork" in page.data
    with client.session_transaction(base_url="https://coach.invalid") as session:
        session_csrf = session["csrf"]
    assert_collision(page, collision)
    assert_concealed(page, session_csrf, expected)
    data = {"csrf": session_csrf, "reference": expected}
    url = f"/evidence/{evidence}/related-forks/start"
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
    practice = client.get(
        response.headers["Location"], base_url="https://coach.invalid", headers=headers
    )
    assert_concealed(practice, session_csrf)


def add_public(db, evidence):
    from chess_coach.related_fork_source import source_for_evidence

    db.connection.execute("""INSERT INTO public_collections(version,source_url,source_revision,source_sha256,
        content_sha256,content_format,license,attribution,license_notice,accepted,excluded,state)
        VALUES('public-v1','https://example.invalid','v1','a','b','fen_csv','CC0-1.0','fixture','notice',9,0,'staging')""")
    collection = db.connection.execute(
        "SELECT id FROM public_collections WHERE version='public-v1'"
    ).fetchone()[0]
    base, _ = corpus_fork_features(PRE, LINE)
    for index, file in enumerate("abcdefh"):
        board = chess.Board(base)
        board.set_piece_at(chess.parse_square(file + "2"), chess.Piece(chess.PAWN, chess.WHITE))
        db.connection.execute(
            "INSERT INTO public_tasks VALUES(?,?,?,?,?)",
            (
                collection,
                "answer-b5c7-" + str(index),
                board.fen(),
                "legal_line",
                json.dumps(["b5c7 e8f8 c7a8"]),
            ),
        )
    source = source_for_evidence(db, LEARNER, evidence)
    db.connection.execute(
        "INSERT INTO public_tasks VALUES(?,?,?,?,?)",
        (collection, "exact", source["prompt_fen"], "legal_line", json.dumps(source["lines"])),
    )
    board = chess.Board(base)
    board.set_piece_at(chess.A2, chess.Piece(chess.PAWN, chess.WHITE))
    db.connection.execute(
        "INSERT INTO public_tasks VALUES(?,?,?,?,?)",
        (collection, "duplicate", board.fen(), "legal_line", json.dumps(["b5c7 e8f8 c7a8"])),
    )
    db.connection.execute("UPDATE public_collections SET state='ready' WHERE id=?", (collection,))
    db.connection.commit()


def test_public_candidates_duplicate_exclusion_and_cursor_scope(tmp_path, monkeypatch):
    db, evidence = fixture(tmp_path, monkeypatch)
    add_public(db, evidence)
    first = preview(db, LEARNER, evidence, "test")
    assert len(first["items"]) == 4 and first["next_cursor"]
    assert first["excluded"]["exact_source"] == 1 and first["excluded"]["duplicate"] >= 1
    assert any(item["type"] == "public" for item in first["items"])
    assert "b5c7" not in preview_text(first, selection(db, LEARNER, evidence, "test"))
    second = preview(db, LEARNER, evidence, "test", first["next_cursor"])
    assert second == preview(db, LEARNER, evidence, "test", first["next_cursor"])
    assert not (
        {item["fen"] for item in first["items"]} & {item["fen"] for item in second["items"]}
    )
    review_evidence(db, evidence, decision="accept", actor="fixture_reviewer")
    with pytest.raises(ValueError, match="cursor"):
        preview(db, LEARNER, evidence, "test", first["next_cursor"])
    with pytest.raises(ValueError):
        start_related(
            db,
            attempt_id="stale",
            subject=LEARNER,
            evidence_id=evidence,
            corpus_version="test",
            reference=first["items"][0]["reference"],
        )


def test_prompt_rights_retained_and_unsupported_en_passant():
    fen = "r3k2r/7p/8/1N6/8/8/6P1/7K b kq - 0 1"
    prompt, shape = corpus_fork_features(fen, "h7h6 b5c7 e8f8 c7a8")
    assert shape and prompt.split()[2] == "kq"
    ep = "r3k3/6p1/8/1N1Pp3/8/8/6P1/7K w - e6 0 2"
    assert fork_features(ep, ["b5c7", "e8f8", "c7a8"]) is None


def test_matching_geometry_outranks_same_roles_with_other_geometry(tmp_path, monkeypatch):
    from chess_coach.related_capture_rank import rank
    from chess_coach.related_fork_match import candidate
    from chess_coach.related_fork_source import source_for_evidence

    db, evidence = fixture(tmp_path, monkeypatch)
    source = source_for_evidence(db, LEARNER, evidence)
    same_prompt, _ = corpus_fork_features(PRE, LINE)
    different_prompt = "8/7p/4k3/8/4r3/1N6/6P1/7K w - - 0 1"
    candidates = [
        {
            "type": "public",
            "version": "v",
            "key": "a",
            "fen": different_prompt,
            "line": "b3c5 e6f6 c5e4",
        },
        {
            "type": "public",
            "version": "v",
            "key": "z",
            "fen": same_prompt,
            "line": "b5c7 e8f8 c7a8",
        },
    ]
    result = rank(source, candidates, set(), None, feature=fork_features, score=candidate)
    assert [item["key"] for item in result] == ["z", "a"]


def test_cli_preview_and_guarded_start(tmp_path, monkeypatch, capsys):
    from argparse import Namespace

    from chess_coach.cli_related_fork import begin, listing

    db, evidence = fixture(tmp_path, monkeypatch)
    listing(db, Namespace(subject=LEARNER, evidence=evidence, corpus="test", cursor=None))
    data = json.loads(capsys.readouterr().out)
    assert "b5c7" not in preview_text(data, selection(db, LEARNER, evidence, "test"))
    begin(
        db,
        Namespace(
            subject=LEARNER,
            evidence=evidence,
            corpus="test",
            attempt="cli",
            reference=data["items"][0]["reference"],
        ),
    )
    state = json.loads(capsys.readouterr().out)
    assert state["status"] == "active" and "source_key" not in state


def test_cursor_invalidates_ranking_version_and_public_versions(tmp_path, monkeypatch):
    from chess_coach import related_fork

    db, evidence = fixture(tmp_path, monkeypatch)
    add_public(db, evidence)
    cursor = preview(db, LEARNER, evidence, "test")["next_cursor"]
    monkeypatch.setattr(related_fork, "VERSION", "fork-execute-transfer-v-next")
    with pytest.raises(ValueError, match="cursor"):
        preview(db, LEARNER, evidence, "test", cursor)
    monkeypatch.setattr(related_fork, "VERSION", "fork-execute-transfer-v1")
    db.connection.execute("""INSERT INTO public_collections(version,source_url,source_revision,source_sha256,
        content_sha256,content_format,license,attribution,license_notice,accepted,excluded,state)
        VALUES('public-v2','https://example.invalid','v2','a','b','fen_csv','CC0-1.0','fixture','notice',0,0,'ready')""")
    db.connection.commit()
    with pytest.raises(ValueError, match="cursor"):
        preview(db, LEARNER, evidence, "test", cursor)


def test_insufficient_corpus_has_no_unrelated_fallback(tmp_path, monkeypatch):
    db, evidence = fixture(tmp_path, monkeypatch)
    db.connection.execute(
        "INSERT INTO puzzle_corpora(version,source,checksum,state) VALUES('empty','fixture','empty','ready')"
    )
    db.connection.commit()
    result = preview(db, LEARNER, evidence, "empty")
    assert result["items"] == [] and "insufficient" in result["status"]
    assert result["next_cursor"] is None


def test_material_protection_lesson_does_not_offer_capture_transfer(tmp_path):
    from flask import render_template

    app = create_app(
        db_path=tmp_path / "unused.sqlite",
        subject="fixture_learner",
        actor="operator",
        corpus="test",
        login="fixture",
        origin="https://coach.invalid",
    )
    lesson = {
        "family": "material-opportunity-mapper",
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
                "operation": "prevent",
                "facts": [],
                "lines": [],
            }
        ],
    }
    with app.test_request_context():
        page = render_template("lesson_body.html", lesson=lesson)
    assert "Related protection practice is not yet available" in page
    assert "related-captures" not in page


def test_public_matching_uses_any_validated_alternative(tmp_path, monkeypatch):
    db, evidence = fixture(tmp_path, monkeypatch)
    prompt, _ = corpus_fork_features(PRE, LINE)
    board = chess.Board(prompt)
    board.set_piece_at(chess.A2, chess.Piece(chess.PAWN, chess.WHITE))
    db.connection.execute("""INSERT INTO public_collections(version,source_url,source_revision,source_sha256,
        content_sha256,content_format,license,attribution,license_notice,accepted,excluded,state)
        VALUES('multi','https://example.invalid','v1','a','b','fen_csv','CC0-1.0','fixture','notice',1,0,'staging')""")
    collection = db.connection.execute(
        "SELECT id FROM public_collections WHERE version='multi'"
    ).fetchone()[0]
    db.connection.execute(
        "INSERT INTO public_tasks VALUES(?,?,?,?,?)",
        (
            collection,
            "fixture",
            board.fen(),
            "legal_line",
            json.dumps(["h1g1 e8f8 g2g3", "b5c7 e8f8 c7a8"]),
        ),
    )
    db.connection.execute("UPDATE public_collections SET state='ready' WHERE id=?", (collection,))
    db.connection.commit()
    result = preview(db, LEARNER, evidence, "test")
    public = next(item for item in result["items"] if item["type"] == "public")
    selected = selection(db, LEARNER, evidence, "test")
    assert "b5c7" not in preview_text(result, selected)
    start_related(
        db,
        attempt_id="public",
        subject=LEARNER,
        evidence_id=evidence,
        corpus_version="test",
        reference=public["reference"],
    )
    from chess_coach.unified_session_events import hint

    row = db.connection.execute(
        "SELECT provenance_json FROM unified_sessions WHERE attempt_id='public'"
    ).fetchone()
    binding = json.loads(row["provenance_json"])["related_fork"]
    assert binding["selected_line_indices"] == [1]
    assert binding["line_filter_version"] == "fork-execute-lines-v1"
    expected = expected_binding(db, selected, public["reference"], LEARNER, fork=True)
    assert "b5c7" not in binding_text(binding, expected)
    assert hint(db, "public", LEARNER, event_id="hint")["hint"] == "b5"

    from chess_coach import related_fork_current

    original = related_fork_current.resolve_source

    def changed(*args, **kwargs):
        snapshot = original(*args, **kwargs)
        snapshot["lines"].reverse()
        return snapshot

    with monkeypatch.context() as patch:
        patch.setattr(related_fork_current, "resolve_source", changed)
        with pytest.raises(ValueError, match="stale"):
            show(db, "public", LEARNER)
    from chess_coach import related_fork_lines

    with monkeypatch.context() as patch:
        patch.setattr(related_fork_lines, "FILTER_VERSION", "future-filter")
        with pytest.raises(ValueError, match="stale"):
            show(db, "public", LEARNER)
    result = submit(db, "public", LEARNER, event_id="unlisted", move="h1g1")
    assert result["status"] == "needs_verification"
