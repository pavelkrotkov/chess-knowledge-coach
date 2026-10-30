"""Synthetic source-bound back-rank transfer and safety controls."""

import chess
import chess.engine
import pytest

from chess_coach.back_rank_auto import process_decision
from chess_coach.evidence_review import review_evidence
from chess_coach.mate_auto import process_decision as process_mate
from chess_coach.related_backrank_attack import preview
from chess_coach.related_backrank_features import features
from chess_coach.related_backrank_source import roots, source_for_evidence
from chess_coach.related_backrank_start import start_related
from chess_coach.unified_session_events import show, submit
from tests.related_protection_support import learning_counts
from tests.test_back_rank import ATTACK
from tests.test_mate_proof import owned_game

SUBJECT = "fixture_a"
PRE = "6k1/1p3ppp/8/8/8/8/8/R4K2 b - - 0 1"


def fixture(path, monkeypatch, move="Ra8#", black=False):
    if black:
        import sys

        import chess.pgn

        from chess_coach.db import Database
        from chess_coach.ingest import ingest_pgn
        from chess_coach.pipeline_config import PipelineConfig
        from chess_coach.pipeline_inputs import engine_identity, game_input
        from chess_coach.pipeline_work import run_analysis
        from tests.test_mate_proof import Engine

        board = chess.Board(ATTACK).mirror()
        game = chess.pgn.Game()
        game.setup(board)
        game.headers["White"] = "fixture_b"
        game.headers["Black"] = SUBJECT
        game.headers["Result"] = "*"
        game.add_variation(board.parse_uci("a8a1"))
        db = Database(path)
        db.initialize()
        ingest_pgn(db, str(game))
        monkeypatch.setattr(chess.engine.SimpleEngine, "popen_uci", lambda _: Engine())
        config = PipelineConfig(learner=SUBJECT, engine_path=sys.executable, nodes=100)
        assert (
            run_analysis(db, 1, game_input(db, 1), config, engine_identity(sys.executable))[
                "status"
            ]
            == "complete"
        )
    else:
        db = owned_game(path, monkeypatch, fen=ATTACK, move=move)
    process_mate(db, 1, SUBJECT)
    process_decision(db, 1, SUBJECT)
    evidence = db.connection.execute(
        "SELECT id FROM evidence_mappings WHERE skill='back_rank' AND operation='execute'"
    ).fetchone()["id"]
    db.connection.execute(
        "INSERT INTO puzzle_corpora(version,source,checksum,state) VALUES('test','fixture','checksum','staging')"
    )
    corpus = db.connection.execute("SELECT id FROM puzzle_corpora WHERE version='test'").fetchone()[
        "id"
    ]
    db.connection.execute(
        """INSERT INTO puzzles(puzzle_id,corpus_id,fen,source,solution,rating,rating_deviation,themes_json,objective)
        VALUES('fixture',?,?,'https://example.invalid',?,1200,80,'["mateIn1"]','unknown')""",
        (
            corpus,
            chess.Board(PRE).mirror().fen() if black else PRE,
            "b2b3 a8a1" if black else "b7b6 a1a8",
        ),
    )
    db.connection.execute(
        "INSERT INTO puzzle_themes VALUES(?,?,'mateIn1',1200)", (corpus, "fixture")
    )
    db.connection.execute("UPDATE puzzle_corpora SET state='ready' WHERE id=?", (corpus,))
    db.connection.commit()
    return db, evidence


@pytest.mark.parametrize("black", [False, True])
def test_proved_root_reaches_concealed_playable_transfer(tmp_path, monkeypatch, black):
    db, evidence = fixture(tmp_path / "source.sqlite", monkeypatch, black=black)
    before = learning_counts(db)
    move = "a8a1" if black else "a1a8"
    choices = roots(db, SUBJECT, evidence)[3]
    assert any(root["move"]["uci"] == move and root["distance_plies"] == 1 for root in choices)
    result = preview(db, SUBJECT, evidence, "test", move)
    assert result["status"] == "available" and len(result["items"]) == 1
    assert result["source_outcome"] == "success"
    assert result["backrank_scan"]["lines"] == 1
    item = result["items"][0]
    assert move not in str(item)
    state = start_related(
        db,
        attempt_id="transfer",
        subject=SUBJECT,
        evidence_id=evidence,
        corpus_version="test",
        root_move=move,
        reference=item["reference"],
    )
    assert state["objective"] == "checkmate" and state["status"] == "active"
    assert (
        submit(db, "transfer", SUBJECT, event_id="answer", move=move)["status"]
        == "objective_verified"
    )
    assert learning_counts(db) == before
    db.close()


def test_wrong_origin_foreign_and_review_revocation_fail_closed(tmp_path, monkeypatch):
    db, evidence = fixture(tmp_path / "stale.sqlite", monkeypatch)
    with pytest.raises(ValueError):
        source_for_evidence(db, "foreign", evidence, "a1a8")
    with pytest.raises(ValueError):
        source_for_evidence(db, SUBJECT, evidence, "a1a7")
    item = preview(db, SUBJECT, evidence, "test", "a1a8")["items"][0]
    with pytest.raises(ValueError):
        start_related(
            db,
            attempt_id="wrong-root",
            subject=SUBJECT,
            evidence_id=evidence,
            corpus_version="test",
            root_move="a1a7",
            reference=item["reference"],
        )
    start_related(
        db,
        attempt_id="stale",
        subject=SUBJECT,
        evidence_id=evidence,
        corpus_version="test",
        root_move="a1a8",
        reference=item["reference"],
    )
    review_evidence(db, evidence, decision="reject", actor="fixture_reviewer")
    with pytest.raises(ValueError):
        show(db, "stale", SUBJECT)
    with pytest.raises(ValueError):
        preview(db, SUBJECT, evidence, "test", "a1a8")
    db.close()


def test_only_actual_home_rank_rook_or_queen_checker_matches():
    valid = chess.Board(ATTACK)
    assert features(valid.fen(), ["a1a8"]) is not None
    mirrored = valid.mirror()
    assert features(mirrored.fen(), ["a8a1"]) is not None
    ordinary = chess.Board("7k/5Q2/6K1/8/8/8/8/8 w - - 0 1")
    assert features(ordinary.fen(), ["f7g7"]) is None
    assert features(valid.fen(), ["a1a7"]) is None
    assert features(valid.fen(), ["a1a8", "g8h7"]) is None


def test_shared_line_work_limit_stops_before_excess_candidates(monkeypatch):
    from chess_coach import related_backrank_match as match
    from chess_coach.related_backrank_contract import LINE_LIMIT

    budget = {"lines": 0, "line_limit": LINE_LIMIT, "truncated": False}
    checked = []
    monkeypatch.setattr(match, "features", lambda *_: checked.append(1))
    score = match.scorer(budget)
    item = {"type": "corpus", "fen": PRE, "solution": "b7b6 a1a8"}
    for _ in range(LINE_LIMIT + 1):
        score(item, {}, set(), None)
    assert budget["lines"] == LINE_LIMIT and budget["truncated"]
    assert len(checked) == LINE_LIMIT


def test_ambiguous_source_is_supported_alternative_not_missed_mistake(tmp_path, monkeypatch):
    db, evidence = fixture(tmp_path / "ambiguous.sqlite", monkeypatch, move="Ra2")
    result = preview(db, SUBJECT, evidence, "test", "a1a8")
    assert result["source_outcome"] == "ambiguous"
    assert result["status"] == "available"
    db.close()


def test_filter_version_change_invalidates_active_session(tmp_path, monkeypatch):
    from chess_coach import related_backrank_contract as contract

    db, evidence = fixture(tmp_path / "filter.sqlite", monkeypatch)
    item = preview(db, SUBJECT, evidence, "test", "a1a8")["items"][0]
    start_related(
        db,
        attempt_id="filter",
        subject=SUBJECT,
        evidence_id=evidence,
        corpus_version="test",
        root_move="a1a8",
        reference=item["reference"],
    )
    monkeypatch.setattr(contract, "FILTER_VERSION", "changed-fixture-filter")
    with pytest.raises(ValueError, match="stale"):
        show(db, "filter", SUBJECT)
    db.close()


def test_short_root_is_replayed_separately_from_immediate_roots(tmp_path, monkeypatch):
    fen = "6k1/5ppp/8/7Q/8/5R2/7r/K4R2 w - - 0 1"
    db = owned_game(tmp_path / "short.sqlite", monkeypatch, fen=fen, move="Qxf7+")
    # The synthetic cheap engine supplies no mate score; nominate the genuine proof explicitly.
    monkeypatch.setattr("chess_coach.mate_auto.short_candidate", lambda *_: True)
    process_mate(db, 1, SUBJECT)
    process_decision(db, 1, SUBJECT)
    row = db.connection.execute(
        "SELECT id FROM evidence_mappings WHERE skill='back_rank' AND operation='execute'"
    ).fetchone()
    source = source_for_evidence(db, SUBJECT, row["id"], "h5f7")
    assert source["objective"] == "mate_within_two"
    assert all(line.split()[0] == "h5f7" and len(line.split()) == 3 for line in source["lines"])
    initial = chess.Board("6k1/1p3ppp/8/7Q/8/5R2/7r/K4R2 b - - 0 1")
    moves = ["b7b6", *source["lines"][0].split()]
    board = initial.copy()
    for text in moves:
        board.push_uci(text)
    assert board.is_checkmate()
    db.connection.execute(
        "INSERT INTO puzzle_corpora(version,source,checksum,state) VALUES('short','fixture','checksum','staging')"
    )
    corpus = db.connection.execute(
        "SELECT id FROM puzzle_corpora WHERE version='short'"
    ).fetchone()["id"]
    db.connection.execute(
        """INSERT INTO puzzles(puzzle_id,corpus_id,fen,source,solution,rating,rating_deviation,themes_json,objective)
        VALUES('short',?,?,'https://example.invalid',?,1200,80,'["mateIn2"]','unknown')""",
        (corpus, initial.fen(), " ".join(moves)),
    )
    db.connection.execute("INSERT INTO puzzle_themes VALUES(?,?,'mateIn2',1200)", (corpus, "short"))
    db.connection.execute("UPDATE puzzle_corpora SET state='ready' WHERE id=?", (corpus,))
    db.connection.commit()
    selected = preview(db, SUBJECT, row["id"], "short", "h5f7")
    assert selected["mate_timing"] == "mate_within_two"
    assert len(selected["items"]) == 1
    state = start_related(
        db,
        attempt_id="short",
        subject=SUBJECT,
        evidence_id=row["id"],
        corpus_version="short",
        root_move="h5f7",
        reference=selected["items"][0]["reference"],
    )
    assert state["status"] == "active"
    first = submit(db, "short", SUBJECT, event_id="first", move=moves[1])
    assert first["status"] == "active" and first["opponent_move"] == moves[2]
    final = submit(db, "short", SUBJECT, event_id="mate", move=moves[3])
    assert final["status"] == "objective_verified"
    db.close()


def test_cli_and_private_browser_follow_explicit_root(tmp_path, monkeypatch, capsys):
    import json
    import sys

    from chess_coach.cli import main
    from chess_coach.web import create_app

    path = tmp_path / "clients.sqlite"
    db, evidence = fixture(path, monkeypatch)
    db.close()
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "coach",
            "--db",
            str(path),
            "related-backrank-attacks",
            "--subject",
            SUBJECT,
            "--evidence",
            str(evidence),
            "--corpus",
            "test",
            "--root",
            "a1a8",
        ],
    )
    main()
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "available"
    reference = result["items"][0]["reference"]
    monkeypatch.setattr(
        "chess_coach.web_security.secrets.token_urlsafe",
        lambda size: "A" * (43 if size == 32 else 32),
    )
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
    evidence_page = client.get(
        f"/evidence/{evidence}", base_url="https://coach.invalid", headers=headers
    )
    assert b"Find related back-rank attack practice" in evidence_page.data
    url = f"/evidence/{evidence}/related-backrank-attacks"
    page = client.get(url, base_url="https://coach.invalid", headers=headers)
    assert page.status_code == 200 and b"1 ply" in page.data
    page = client.get(url + "?root=a1a8", base_url="https://coach.invalid", headers=headers)
    assert page.status_code == 200 and b"Transfer example" in page.data
    assert b"b7b6 a1a8" not in page.data
    with client.session_transaction(base_url="https://coach.invalid") as session:
        csrf = session["csrf"]
    data = {"csrf": csrf, "root": "a1a8", "reference": reference}
    assert (
        client.post(
            url + "/start", base_url="https://coach.invalid", headers=headers, data=data
        ).status_code
        == 403
    )
    started = client.post(
        url + "/start",
        base_url="https://coach.invalid",
        headers=headers | {"Origin": "https://coach.invalid"},
        data=data,
    )
    assert started.status_code == 303
    page = client.get(
        started.headers["Location"], base_url="https://coach.invalid", headers=headers
    )
    assert page.status_code == 200 and b"Find checkmate" in page.data


def test_prevention_source_and_changed_game_are_not_transfer_sources(tmp_path, monkeypatch):
    from tests.test_back_rank import DEFENSE

    db = owned_game(tmp_path / "defense.sqlite", monkeypatch, fen=DEFENSE, move="g3")
    process_mate(db, 1, SUBJECT)
    process_decision(db, 1, SUBJECT)
    row = db.connection.execute(
        "SELECT id FROM evidence_mappings WHERE skill='back_rank' AND operation='prevent'"
    ).fetchone()
    with pytest.raises(ValueError):
        roots(db, SUBJECT, row["id"])
    db.close()

    db, evidence = fixture(tmp_path / "changed.sqlite", monkeypatch)
    item = preview(db, SUBJECT, evidence, "test", "a1a8")["items"][0]
    start_related(
        db,
        attempt_id="changed",
        subject=SUBJECT,
        evidence_id=evidence,
        corpus_version="test",
        root_move="a1a8",
        reference=item["reference"],
    )
    db.connection.execute("UPDATE games SET pgn=pgn || '\n{synthetic change}' WHERE id=1")
    db.connection.commit()
    with pytest.raises(ValueError, match="stale"):
        show(db, "changed", SUBJECT)
    db.close()


def test_lesson_exposes_attack_entry(tmp_path):
    from flask import render_template

    from chess_coach.web import create_app

    app = create_app(
        db_path=tmp_path / "unused.sqlite",
        subject=SUBJECT,
        actor="fixture",
        corpus="test",
        login="fixture",
        origin="https://coach.invalid",
    )
    example = {
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
    lesson = {
        "family": "back-rank-observation-mapper",
        "qualification": "bounded",
        "possible": "possible",
        "question": "question",
        "habit": "habit",
        "practice": "practice",
        "examples": [example],
    }
    with app.test_request_context():
        page = render_template("lesson_body.html", lesson=lesson, csrf="fixture")
    assert "Find related back-rank attack practice" in page


def test_public_supplied_lines_are_filtered_and_share_work_budget(tmp_path, monkeypatch):
    import json

    db, evidence = fixture(tmp_path / "public.sqlite", monkeypatch)
    db.connection.execute(
        """INSERT INTO public_collections(version,source_url,source_revision,source_sha256,
        content_sha256,content_format,license,attribution,license_notice,accepted,excluded,state)
        VALUES('public-v1','https://example.invalid','v1','a','b','fen_csv','CC0-1.0','fixture','notice',1,0,'staging')"""
    )
    collection = db.connection.execute(
        "SELECT id FROM public_collections WHERE version='public-v1'"
    ).fetchone()[0]
    prompt = "6k1/5ppp/1p6/8/8/8/1P6/R4K2 w - - 0 2"
    db.connection.execute(
        "INSERT INTO public_tasks VALUES(?,?,?,?,?)",
        (collection, "public-mate", prompt, "legal_line", json.dumps(["a1a2", "a1a8"])),
    )
    db.connection.execute("UPDATE public_collections SET state='ready' WHERE id=?", (collection,))
    db.connection.commit()
    result = preview(db, SUBJECT, evidence, "test", "a1a8")
    assert result["backrank_scan"]["lines"] == 3
    item = next(item for item in result["items"] if item["type"] == "public")
    start_related(
        db,
        attempt_id="public",
        subject=SUBJECT,
        evidence_id=evidence,
        corpus_version="test",
        root_move="a1a8",
        reference=item["reference"],
    )
    stored = db.connection.execute(
        "SELECT lines_json FROM unified_sessions WHERE attempt_id='public'"
    ).fetchone()[0]
    assert json.loads(stored) == [["a1a8"]]
    assert (
        submit(db, "public", SUBJECT, event_id="answer", move="a1a8")["status"]
        == "objective_verified"
    )
    db.close()
