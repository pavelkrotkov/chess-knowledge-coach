"""Source-bound back-rank transfers preserve witness and mover roles."""

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
from tests.test_back_rank import ATTACK
from tests.test_mate_proof import owned_game

SUBJECT = "fixture_a"
PRE = "6k1/1p3ppp/8/8/8/8/8/R4K2 b - - 0 1"


def learning_counts(db):
    tables = (
        "evidence_review_events",
        "evidence_mappings",
        "evidence_fact_links",
        "training_items",
        "training_attempts",
        "training_completions",
        "mastery_states",
        "mastery_events",
    )
    return tuple(
        db.connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] for table in tables
    )


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
    review_evidence(db, evidence, decision="reject", actor="fixture_reviewer")
    with pytest.raises(ValueError):
        show(db, "transfer", SUBJECT)
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


@pytest.mark.parametrize("black", [False, True])
def test_direct_and_discovered_mates_have_distinct_opening_attacker_roles(black, monkeypatch):
    from chess_coach import related_backrank_score
    from chess_coach.related_backrank_contract import LINE_LIMIT
    from chess_coach.related_backrank_public import candidate_public

    direct = chess.Board("6k1/2B2ppp/8/8/8/8/8/R4K2 w - - 0 1")
    discovered = chess.Board("RB4k1/5ppp/8/8/8/8/8/5K2 w - - 0 1")
    direct_move, discovered_move = "a1a8", "b8c7"
    if black:
        direct, discovered = direct.mirror(), discovered.mirror()
        direct_move, discovered_move = "a8a1", "b1c2"
    assert direct.is_valid() and direct.is_legal(chess.Move.from_uci(direct_move))
    assert discovered.is_valid() and discovered.is_legal(chess.Move.from_uci(discovered_move))
    direct_end, discovered_end = direct.copy(), discovered.copy()
    direct_end.push_uci(direct_move)
    discovered_end.push_uci(discovered_move)
    assert direct_end.board_fen() == discovered_end.board_fen()
    source = features(direct.fen(), [direct_move])
    other = features(discovered.fen(), [discovered_move])
    assert source and other
    assert source["backrank"]["opening_piece_backrank_checks"]
    assert not other["backrank"]["opening_piece_backrank_checks"]
    assert source["backrank"]["escapes"] == other["backrank"]["escapes"]
    assert ((-1, -1), True, False) in source["backrank"]["escapes"]
    assert ((-1, 0), False, True) in source["backrank"]["escapes"]
    source["opening"] = None
    other["opening"] = None
    budget = {"lines": 0, "line_limit": LINE_LIMIT, "truncated": False}

    def item(board, move):
        return {
            "type": "public",
            "version": "fixture",
            "key": "candidate",
            "objective": "legal_line",
            "fen": board.fen(),
            "lines": [move],
        }

    assert candidate_public(item(direct, direct_move), source, set(), None, budget) is not None
    assert candidate_public(item(discovered, discovered_move), source, set(), None, budget) is None
    assert (
        candidate_public(item(discovered, discovered_move), other, set(), None, budget) is not None
    )
    assert budget["lines"] == 3
    # Isolate the new structural guard even if generic mover-type data were equal.
    monkeypatch.setattr(
        related_backrank_score, "mate_match", lambda *_: pytest.fail("role mismatch")
    )
    assert related_backrank_score.match({}, source, set(), None, direct.fen(), other) is None
