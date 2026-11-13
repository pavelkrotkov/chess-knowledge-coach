"""Certified pin transfer workflows preserve source and admission boundaries."""

import json

import chess
import pytest

from chess_coach.evidence_review import review_evidence
from chess_coach.related_pin import preview
from chess_coach.related_pin_budget import create
from chess_coach.related_pin_line import candidate_line
from chess_coach.related_pin_source import source_for_evidence
from chess_coach.related_pin_start import start_related
from chess_coach.unified_session_events import show, submit
from tests.test_objective_pin import SUBJECT, owned_pin


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


def _prevention_transfer(monkeypatch, black):
    import sys
    from copy import deepcopy

    import chess.engine
    import chess.pgn

    from chess_coach import related_pin_prevent_line as prevent_line
    from chess_coach.db import Database
    from chess_coach.evidence_review import inspect_evidence
    from chess_coach.ingest import ingest_pgn
    from chess_coach.pin_pipeline import process_decision
    from chess_coach.pipeline_config import PipelineConfig
    from chess_coach.pipeline_inputs import engine_identity, game_input
    from chess_coach.pipeline_work import run_analysis
    from chess_coach.related_pin_candidates import matches, prompt
    from chess_coach.related_pin_prevent_display import available as finder_available
    from chess_coach.related_pin_prevent_line import candidate_line as prevention_line
    from tests.test_pin_pipeline import Engine

    board = chess.Board("7k/5p2/8/8/8/4r3/4R2K/4Q3 w - - 0 1")
    if black:
        board = board.mirror()

    def uci(text):
        move = chess.Move.from_uci(text)
        if black:
            move = chess.Move(
                chess.square_mirror(move.from_square), chess.square_mirror(move.to_square)
            )
        return move.uci()

    game = chess.pgn.Game()
    game.setup(board)
    game.headers.update(
        {
            "White": "fixture_opponent" if black else SUBJECT,
            "Black": SUBJECT if black else "fixture_opponent",
            "Result": "*",
            "UTCDate": "2026.01.01",
            "UTCTime": "12:00:00",
        }
    )
    node = game.add_variation(board.parse_uci(uci("e2f2")))
    board.push_uci(uci("e2f2"))
    node.add_variation(board.parse_uci(uci("e3e1")))
    db = Database(":memory:")
    db.initialize()
    ingest_pgn(db, str(game))
    monkeypatch.setattr(chess.engine.SimpleEngine, "popen_uci", lambda _: Engine())
    config = PipelineConfig(
        learner=SUBJECT, engine_path=sys.executable, nodes=100, deep_enabled=False
    )
    assert (
        run_analysis(db, 1, game_input(db, 1), config, engine_identity(sys.executable))["status"]
        == "complete"
    )
    evidence = process_decision(db, 1, SUBJECT, "prevent")["evidence_ids"][0]
    source = source_for_evidence(db, SUBJECT, evidence)
    detail = inspect_evidence(db, evidence)
    assert finder_available(detail)
    for mode in ("created", "slide"):
        other = deepcopy(detail)
        if mode == "created":
            other["pin_explanation"]["proof"]["mode"] = "created"
        else:
            other["pin_explanation"]["alternative"]["move"] = uci("e2f2")
        assert not finder_available(other)
    candidate = chess.Board(source["prompt_fen"])
    candidate.turn = not candidate.turn
    setup = uci("f7f6")
    before = candidate.fen()
    candidate.push_uci(setup)
    line = [uci("e2e3"), uci("h8g8"), uci("e3e8")]
    assert prevention_line(candidate, line, source["features"], create())
    two_captures = candidate.copy(stack=True)
    bishop = chess.parse_square("b3" if black else "b6")
    two_captures.set_piece_at(bishop, chess.Piece(chess.BISHOP, two_captures.turn))
    assert two_captures.parse_uci(uci("b6e3")) in two_captures.legal_moves
    calls = []
    original_capture = prevent_line.capture

    def counted(*args):
        calls.append(args[1:3])
        return original_capture(*args)

    with monkeypatch.context() as patch:
        patch.setattr(prevent_line, "capture", counted)
        assert prevention_line(two_captures, line, source["features"], create())
    assert len(calls) == 1
    public = {
        "type": "public",
        "fen": candidate.fen(),
        "objective": "legal_line",
        "lines": ["a1a1", " ".join(line)],
    }
    public_board, public_lines = prompt(public)
    assert [
        index for index, _ in matches(public_board, public_lines, source["features"], create())
    ] == [1]
    assert (
        prevention_line(
            candidate, line, source["features"] | {"pin_kind": "absolute_pin"}, create()
        )
        is None
    )
    db.connection.execute(
        "INSERT INTO puzzle_corpora(version,source,checksum,state) VALUES('test','fixture','checksum','staging')"
    )
    corpus = db.connection.execute("SELECT id FROM puzzle_corpora WHERE version='test'").fetchone()[
        0
    ]
    db.connection.execute(
        """INSERT INTO puzzles(puzzle_id,corpus_id,fen,source,solution,rating,rating_deviation,themes_json,objective)
        VALUES('fixture-defense',?,?,'https://example.invalid',?,1200,80,'[]','unknown')""",
        (corpus, before, " ".join([setup, *line])),
    )
    db.connection.execute(
        "INSERT INTO puzzle_themes VALUES(?,?,'defensiveMove',1200)", (corpus, "fixture-defense")
    )
    db.connection.execute("UPDATE puzzle_corpora SET state='ready' WHERE id=?", (corpus,))
    db.connection.commit()
    result = preview(db, SUBJECT, evidence, "test")
    assert result["operation"] == "prevent" and len(result["items"]) == 1
    visible = {
        **result,
        "items": [{k: v for k, v in item.items() if k != "reference"} for item in result["items"]],
    }
    visible.pop("scope", None)
    assert line[0] not in json.dumps(visible)

    from flask import render_template

    from chess_coach import web_related_pin, web_views
    from chess_coach.related_session_filter import apply_filter
    from chess_coach.web import create_app

    monkeypatch.setattr(web_related_pin, "database", lambda: db)
    monkeypatch.setattr(web_views, "database", lambda: db)
    with pytest.raises(ValueError, match="line selection unavailable"):
        apply_filter({}, None, "related_pin", None)
    app = create_app(
        db_path=":memory:",
        subject=SUBJECT,
        actor="fixture",
        corpus="test",
        login="fixture",
        origin="https://coach.invalid",
    )
    client = app.test_client()
    base = "https://coach.invalid"
    headers = {"Tailscale-User-Login": "fixture"}
    url = f"/evidence/{evidence}/related-pins"
    evidence_page = client.get(f"/evidence/{evidence}", base_url=base, headers=headers)
    assert b"Find pinner-capture examples" in evidence_page.data
    example = {
        "evidence_id": evidence,
        "game_id": 1,
        "position_id": 1,
        "ply": 1,
        "operation": "prevent",
        "pin_related_capture": True,
        "facts": [],
        "lines": [],
    }
    with app.test_request_context(base_url=base):
        lesson = {"family": "pin-prevent-mapper", "examples": [example]}
        assert "Find pinner-capture examples" in render_template("lesson_body.html", lesson=lesson)
        example["pin_related_capture"] = False
        rendered = render_template("lesson_body.html", lesson=lesson)
        assert (
            "Find pinner-capture examples" not in rendered and "Practice pin prevention" in rendered
        )
    unsupported_detail = deepcopy(detail)
    unsupported_detail["pin_related_capture"] = False
    with monkeypatch.context() as patch:
        patch.setattr(web_views, "inspect_evidence", lambda *_: unsupported_detail)
        evidence_page = client.get(f"/evidence/{evidence}", base_url=base, headers=headers)
    assert b"Find pinner-capture examples" not in evidence_page.data
    assert b"Practice pin prevention" in evidence_page.data
    assert client.get(url, base_url=base).status_code == 403
    page = client.get(url, base_url=base, headers=headers)
    assert page.status_code == 200 and b"own-game pin prevention" in page.data
    assert b"Same pin kind and a proved pinner capture." in page.data
    assert b"Same pin kind and a supported defensive contrast." not in page.data
    from chess_coach import related_pin_prevent_source

    unsupported = deepcopy(source)
    unsupported["provenance"]["pin_prevention"]["origin"] = "created"
    with monkeypatch.context() as patch:
        patch.setattr(related_pin_prevent_source, "resolve", lambda *_: unsupported)
        unavailable = client.get(url, base_url=base, headers=headers)
    assert unavailable.status_code == 200 and b"no supported capture" in unavailable.data
    import re

    visible_page = re.sub(rb"<input\b[^>]*>", b"", page.data)
    assert line[0].encode() not in visible_page
    with client.session_transaction(base_url=base) as session:
        csrf = session["csrf"]
    data = {"csrf": csrf, "reference": result["items"][0]["reference"]}
    assert client.post(url + "/start", base_url=base, headers=headers, data=data).status_code == 403
    assert (
        client.post(
            url + "/start", base_url=base, headers=headers | {"Origin": base}, data=data
        ).status_code
        == 303
    )

    with client.session_transaction(base_url=base) as session:
        attempt = session["unified_attempt"]
    state = show(db, attempt, SUBJECT)
    assert state["status"] == "active" and state["objective"] == "legal_line"
    row = db.connection.execute(
        "SELECT provenance_json FROM unified_sessions WHERE attempt_id=?", (attempt,)
    ).fetchone()
    binding = json.loads(row["provenance_json"])["related_pin"]
    assert binding["operation"] == "prevent" and binding["pattern_cued"]
    assert submit(db, attempt, SUBJECT, event_id="answer", move=line[0])["status"] == "active"
    assert (
        submit(db, attempt, SUBJECT, event_id="finish", move=line[2])["status"] == "line_completed"
    )
    review_evidence(db, evidence, decision="reject", actor="fixture_reviewer")
    with pytest.raises(ValueError, match="stale"):
        show(db, attempt, SUBJECT)
    db.close()


def _created_transfer(monkeypatch, black):
    import sys

    import chess.engine
    import chess.pgn

    from chess_coach import related_pin_created_proof
    from chess_coach.db import Database
    from chess_coach.evidence_review import inspect_evidence
    from chess_coach.ingest import ingest_pgn
    from chess_coach.pin_geometry import pins
    from chess_coach.pin_pipeline import process_decision
    from chess_coach.pipeline_config import PipelineConfig
    from chess_coach.pipeline_inputs import engine_identity, game_input
    from chess_coach.pipeline_work import run_analysis
    from chess_coach.related_pin_created_line import candidate_line as created_line
    from tests.test_pin_pipeline import Engine

    root = chess.Board("4r3/b1p3k1/Bpnppppp/8/8/8/8/7K b - - 0 1")
    external = chess.Board("4r3/b1p3k1/Bpnppppp/8/8/8/P7/7K w - - 0 1")
    if not black:
        root, external = root.mirror(), external.mirror()

    def uci(text):
        move = chess.Move.from_uci(text)
        if not black:
            move = chess.Move(
                chess.square_mirror(move.from_square), chess.square_mirror(move.to_square)
            )
        return move.uci()

    before = root.copy(stack=True)
    before.turn = not before.turn
    assert pins(before, before.parse_uci(uci("a6b5")))
    game = chess.pgn.Game()
    game.setup(root)
    game.headers.update(
        {
            "White": "fixture_opponent" if black else SUBJECT,
            "Black": SUBJECT if black else "fixture_opponent",
            "Result": "*",
            "UTCDate": "2026.01.01",
            "UTCTime": "12:00:00",
        }
    )
    node = game.add_variation(root.parse_uci(uci("g7h8")))
    root.push_uci(uci("g7h8"))
    node.add_variation(root.parse_uci(uci("a6b5")))

    class Synthetic(Engine):
        def analyse(self, board, limit, multipv, root_moves=None):
            candidate = chess.Move.from_uci(uci("e8h8"))
            move = (
                root_moves[0]
                if root_moves
                else (
                    candidate if candidate in board.legal_moves else next(iter(board.legal_moves))
                )
            )
            after = board.copy()
            after.push(move)
            reply = chess.Move.from_uci(uci("a6c8") if move == candidate else uci("a6b5"))
            line = [move, reply] if reply in after.legal_moves else [move]
            return [
                {
                    "score": chess.engine.PovScore(chess.engine.Cp(0), board.turn),
                    "pv": line,
                    "nodes": 100,
                    "depth": 5,
                }
            ]

    db = Database(":memory:")
    db.initialize()
    ingest_pgn(db, str(game))
    with monkeypatch.context() as patch:
        patch.setattr(chess.engine.SimpleEngine, "popen_uci", lambda _: Synthetic())
        config = PipelineConfig(
            learner=SUBJECT, engine_path=sys.executable, nodes=100, deep_enabled=False
        )
        assert (
            run_analysis(db, 1, game_input(db, 1), config, engine_identity(sys.executable))[
                "status"
            ]
            == "complete"
        )
        evidence = process_decision(db, 1, SUBJECT, "prevent")["evidence_ids"][0]
        detail = inspect_evidence(db, evidence)
        assert detail["pin_related_created"] and not detail["pin_related_capture"]
        source = source_for_evidence(db, SUBJECT, evidence)
        assert source["features"]["origin"] == "counterfactual"

        original = external.fen()
        external.push_uci(uci("a2a3"))
        good, reply = uci("e8h8"), uci("a6c8")
        after = external.copy(stack=True)
        after.push_uci(good)
        after.push_uci(reply)
        last = next(iter(after.legal_moves)).uci()
        line = [good, reply, last]
        assert created_line(external, line, source["features"], create())
        from chess_coach import related_pin_created_search

        replayed = []
        original_replay = related_pin_created_search._replay

        def counted_replay(board, moves):
            replayed.append(1)
            return original_replay(board, moves)

        with monkeypatch.context() as bounded:
            bounded.setattr(related_pin_created_search, "_replay", counted_replay)
            exhausted = create()
            exhausted["line_limit"] = 0
            assert not created_line(external, line, source["features"], exhausted)
            assert exhausted["truncated"] and not replayed
            wrong_kind = create()
            assert not created_line(
                external, line, {**source["features"], "pin_kind": "absolute_pin"}, wrong_kind
            )
            assert len(replayed) == wrong_kind["lines"]
        from chess_coach.related_pin_candidates import matches as pin_matches

        assert not pin_matches(
            external, [" ".join(line)], {**source["features"], "origin": "existing"}, create()
        )

        with monkeypatch.context() as unresolved:
            unresolved.setattr(
                related_pin_created_proof, "judge", lambda *_: ("unresolved", "fixture", None)
            )
            assert not created_line(external, line, source["features"], create())

        db.connection.execute(
            "INSERT INTO puzzle_corpora(version,source,checksum,state) VALUES('created','fixture','checksum','staging')"
        )
        corpus = db.connection.execute(
            "SELECT id FROM puzzle_corpora WHERE version='created'"
        ).fetchone()[0]
        db.connection.execute(
            """INSERT INTO puzzles(puzzle_id,corpus_id,fen,source,solution,rating,rating_deviation,themes_json,objective)
            VALUES('fixture-created-pin',?,?,'https://example.invalid',?,1200,80,'[]','unknown')""",
            (corpus, original, " ".join([uci("a2a3"), *line])),
        )
        db.connection.execute(
            "INSERT INTO puzzle_themes VALUES(?,?,'defensiveMove',1200)",
            (corpus, "fixture-created-pin"),
        )
        db.connection.execute("UPDATE puzzle_corpora SET state='ready' WHERE id=?", (corpus,))
        db.connection.commit()
        result = preview(db, SUBJECT, evidence, "created")
        assert result["pin_origin"] == "counterfactual" and len(result["items"]) == 1
        from chess_coach import web_related_pin, web_unified_practice, web_views
        from chess_coach.web import create_app

        patch.setattr(web_related_pin, "database", lambda: db)
        patch.setattr(web_views, "database", lambda: db)
        patch.setattr(web_unified_practice, "database", lambda: db)
        app = create_app(
            db_path=":memory:",
            subject=SUBJECT,
            actor="fixture",
            corpus="created",
            login="fixture",
            origin="https://coach.invalid",
        )
        client = app.test_client()
        url = f"/evidence/{evidence}/related-pins"
        assert client.get(url, base_url="https://coach.invalid").status_code == 403
        page = client.get(
            url, base_url="https://coach.invalid", headers={"Tailscale-User-Login": "fixture"}
        )
        assert page.status_code == 200 and b"earlier consequence" in page.data
        assert b"Same pin kind and a supported defensive contrast." in page.data
        assert b"Same pin kind and a proved pinner capture." not in page.data
        evidence_page = client.get(
            f"/evidence/{evidence}",
            base_url="https://coach.invalid",
            headers={"Tailscale-User-Login": "fixture"},
        )
        assert b"Find related pin-prevention practice" in evidence_page.data
        import re

        visible_page = re.sub(rb"<input\b[^>]*>", b"", page.data)
        assert all(uci(move).encode() not in visible_page for move in ("e8h8", "g7h8", "a6b5"))
        reference = result["items"][0]["reference"]
        state = start_related(
            db,
            attempt_id="created-pin",
            subject=SUBJECT,
            evidence_id=evidence,
            corpus_version="created",
            reference=reference,
        )
        assert state["objective"] == "legal_line" and "pin_contrast" not in state
        assert "pin_contrast" not in show(db, "created-pin", SUBJECT)
        active_page = client.get(
            "/unified/created-pin",
            base_url="https://coach.invalid",
            headers={"Tailscale-User-Login": "fixture"},
        )
        assert b"avoids the tested pin consequence" not in active_page.data
        db.connection.execute(
            "UPDATE decision_analysis_lines SET score_value=score_value+1 WHERE position_id=1"
        )
        db.connection.commit()
        with pytest.raises(ValueError, match="stale"):
            show(db, "created-pin", SUBJECT)
        db.connection.execute(
            "UPDATE decision_analysis_lines SET score_value=score_value-1 WHERE position_id=1"
        )
        db.connection.commit()
        assert show(db, "created-pin", SUBJECT)["status"] == "active"
        first = submit(db, "created-pin", SUBJECT, event_id="first", move=good)
        assert first["status"] == "active" and "pin_contrast" not in first
        completed = submit(db, "created-pin", SUBJECT, event_id="last", move=last)
        assert completed["status"] == "line_completed"
        binding = json.loads(
            db.connection.execute(
                "SELECT provenance_json FROM unified_sessions WHERE attempt_id='created-pin'"
            ).fetchone()[0]
        )["related_pin"]
        proof = binding["candidate_certificates"][0]
        contrast = completed["pin_contrast"]
        assert contrast["good"] == external.san(chess.Move.from_uci(proof["branch"]["move"]))
        assert contrast["bad"] == external.san(
            chess.Move.from_uci(proof["branch"]["counterfactual"])
        )
        assert contrast["kind"] == proof["proof"]["type"]
        assert show(db, "created-pin", SUBJECT)["pin_contrast"] == contrast
        complete_page = client.get(
            "/unified/created-pin",
            base_url="https://coach.invalid",
            headers={"Tailscale-User-Login": "fixture"},
        )
        assert b"avoids the tested pin consequence" in complete_page.data
        assert b"earlier consequence" in complete_page.data
        review_evidence(db, evidence, decision="reject", actor="fixture_reviewer")
        with pytest.raises(ValueError, match="stale"):
            show(db, "created-pin", SUBJECT)
    db.close()


def _slide_transfer(monkeypatch, black):
    import re
    import sys

    import chess.engine
    import chess.pgn

    from chess_coach import web_related_pin, web_views
    from chess_coach.db import Database
    from chess_coach.ingest import ingest_pgn
    from chess_coach.pin_pipeline import process_decision
    from chess_coach.pipeline_config import PipelineConfig
    from chess_coach.pipeline_inputs import engine_identity, game_input
    from chess_coach.pipeline_work import run_analysis
    from chess_coach.related_pin_slide_line import candidate_line as slide_line
    from chess_coach.related_pin_slide_proof import pin, slide
    from chess_coach.web import create_app
    from tests.test_pin_pipeline import Engine

    board = chess.Board("4r2k/5p2/8/8/4R3/8/8/K3Q3 w - - 0 1")
    if black:
        board = board.mirror()

    def uci(text):
        move = chess.Move.from_uci(text)
        return (
            chess.Move(
                chess.square_mirror(move.from_square), chess.square_mirror(move.to_square)
            ).uci()
            if black
            else text
        )

    game = chess.pgn.Game()
    game.setup(board)
    game.headers.update(
        {
            "White": "fixture_opponent" if black else SUBJECT,
            "Black": SUBJECT if black else "fixture_opponent",
            "Result": "*",
            "UTCDate": "2026.01.01",
            "UTCTime": "12:00:00",
        }
    )
    node = game.add_variation(board.parse_uci(uci("e4f4")))
    after = board.copy()
    after.push_uci(uci("e4f4"))
    node.add_variation(after.parse_uci(uci("e8e1")))
    db = Database(":memory:")
    db.initialize()
    ingest_pgn(db, str(game))
    monkeypatch.setattr(chess.engine.SimpleEngine, "popen_uci", lambda _: Engine())
    config = PipelineConfig(
        learner=SUBJECT, engine_path=sys.executable, nodes=100, deep_enabled=False
    )
    assert (
        run_analysis(db, 1, game_input(db, 1), config, engine_identity(sys.executable))["status"]
        == "complete"
    )
    evidence = process_decision(db, 1, SUBJECT, "prevent")["evidence_ids"][0]
    source = source_for_evidence(db, SUBJECT, evidence, mechanism="slide")
    assert source["features"]["origin"] == "slide"
    named = pin(board)
    assert named and slide(board, board.parse_uci(uci("e4e3")), *named)
    assert not slide(board, board.parse_uci(uci("e4f4")), *named)
    assert not slide(board, chess.Move.from_uci(uci("e4a8")), *named)

    external = board.copy()
    external.turn = not external.turn
    before = external.fen()
    setup = uci("f7f6")
    external.push_uci(setup)
    line = [uci("e4e3"), uci("h8g8"), uci("e3e7")]
    assert slide_line(external, line, source["features"], create())
    assert not slide_line(external, [uci("e4f4")], source["features"], create())
    assert not slide_line(
        external, line, source["features"] | {"pin_kind": "absolute_pin"}, create()
    )
    db.connection.execute(
        "INSERT INTO puzzle_corpora(version,source,checksum,state) VALUES('slide','fixture','checksum','staging')"
    )
    corpus = db.connection.execute(
        "SELECT id FROM puzzle_corpora WHERE version='slide'"
    ).fetchone()[0]
    db.connection.execute(
        """INSERT INTO puzzles(puzzle_id,corpus_id,fen,source,solution,rating,rating_deviation,themes_json,objective)
        VALUES('fixture-slide',?,?,'https://example.invalid',?,1200,80,'[]','unknown')""",
        (corpus, before, " ".join([setup, *line])),
    )
    db.connection.execute(
        "INSERT INTO puzzle_themes VALUES(?,?,'defensiveMove',1200)", (corpus, "fixture-slide")
    )
    db.connection.execute("UPDATE puzzle_corpora SET state='ready' WHERE id=?", (corpus,))
    db.connection.commit()
    result = preview(db, SUBJECT, evidence, "slide", mechanism="slide")
    assert result["pin_origin"] == "slide" and len(result["items"]) == 1

    monkeypatch.setattr(web_related_pin, "database", lambda: db)
    monkeypatch.setattr(web_views, "database", lambda: db)
    app = create_app(
        db_path=":memory:",
        subject=SUBJECT,
        actor="fixture",
        corpus="slide",
        login="fixture",
        origin="https://coach.invalid",
    )
    client = app.test_client()
    base = "https://coach.invalid"
    headers = {"Tailscale-User-Login": "fixture"}
    url = f"/evidence/{evidence}/related-pins"
    page = client.get(url + "?mechanism=slide", base_url=base, headers=headers)
    assert page.status_code == 200 and b"supported slide" in page.data
    visible = re.sub(rb"<input\b[^>]*>", b"", page.data)
    assert line[0].encode() not in visible and uci("e4f4").encode() not in visible
    with client.session_transaction(base_url=base) as session:
        csrf = session["csrf"]
    response = client.post(
        url + "/start",
        base_url=base,
        headers=headers | {"Origin": base},
        data={"csrf": csrf, "mechanism": "slide", "reference": result["items"][0]["reference"]},
    )
    assert response.status_code == 303
    with client.session_transaction(base_url=base) as session:
        browser_attempt = session["unified_attempt"]
    assert "pin_contrast" not in show(db, browser_attempt, SUBJECT)

    state = show(db, browser_attempt, SUBJECT)
    assert state["status"] == "active" and "pin_contrast" not in state
    assert "pin_contrast" not in show(db, browser_attempt, SUBJECT)
    first = submit(db, browser_attempt, SUBJECT, event_id="first", move=line[0])
    assert first["status"] == "active" and "pin_contrast" not in first
    completed = submit(db, browser_attempt, SUBJECT, event_id="last", move=line[2])
    assert completed["status"] == "line_completed"
    assert completed["pin_contrast"]["mechanism"] == "slide"
    assert show(db, browser_attempt, SUBJECT)["pin_contrast"] == completed["pin_contrast"]
    db.connection.execute(
        "INSERT INTO puzzle_corpora(version,source,checksum,state) "
        "VALUES('empty','fixture','checksum','ready')"
    )
    db.connection.commit()
    empty = preview(db, SUBJECT, evidence, "empty", mechanism="slide")
    assert empty["items"] == [] and "insufficient" in empty["status"]
    review_evidence(db, evidence, decision="reject", actor="fixture_reviewer")
    with pytest.raises(ValueError, match="stale"):
        show(db, browser_attempt, SUBJECT)
    db.close()


@pytest.mark.parametrize("black", [False, True])
def test_owned_pin_transfer_playable_concealed_and_review_bound(tmp_path, monkeypatch, black):
    relative = False
    db, evidence, _, _ = fixture(
        tmp_path / "pin.sqlite", monkeypatch, black=black, relative=relative
    )
    result = preview(db, SUBJECT, evidence, "test")
    assert result["status"] == "available" and len(result["items"]) == 1
    source = source_for_evidence(db, SUBJECT, evidence)
    visible = {
        **result,
        "items": [{k: v for k, v in item.items() if k != "reference"} for item in result["items"]],
    }
    visible.pop("scope", None)
    assert source["lines"][0].split()[0] not in json.dumps(visible)
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
    _prevention_transfer(monkeypatch, black)
    _created_transfer(monkeypatch, black)
    _slide_transfer(monkeypatch, black)


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


def _long_candidate(source):
    import random

    for branch in source["provenance"]["pin_certificate"]["branches"]:
        if branch["mate"]:
            continue
        sample = dict(source)
        creation = source["provenance"]["pin_certificate"]["move"]
        sample["lines"] = [" ".join((creation, branch["reply"], branch["capture"]))]
        fen, initial = _candidate(sample)
        for seed in range(20):
            rng = random.Random(seed)
            board = chess.Board(fen)
            words = initial.split()
            for move in words:
                board.push_uci(move)
            while len(words) < 66:
                choices = list(board.legal_moves)
                rng.shuffle(choices)
                for move in choices:
                    board.push(move)
                    if not board.is_game_over(claim_draw=True):
                        words.append(move.uci())
                        break
                    board.pop()
                else:
                    break
            if len(words) == 66:
                return fen, words
    raise AssertionError("no long synthetic pin witness")


def _check_source_length(tmp_path, monkeypatch, source_kind, length, accepted):
    from chess_coach import related_pin_certificate
    from chess_coach.unified_sources import resolve_source

    db, evidence = owned_pin(tmp_path / "boundary.sqlite", monkeypatch, relative=True)
    source = source_for_evidence(db, SUBJECT, evidence)
    fen, full = _long_candidate(source)
    board = chess.Board(fen)
    board.push_uci(full[0])
    db.connection.execute(
        "INSERT INTO puzzle_corpora(version,source,checksum,state) VALUES('test','fixture','checksum','staging')"
    )
    corpus = db.connection.execute("SELECT id FROM puzzle_corpora WHERE version='test'").fetchone()[
        0
    ]
    if source_kind == "corpus":
        db.connection.execute(
            """INSERT INTO puzzles(puzzle_id,corpus_id,fen,source,solution,rating,rating_deviation,themes_json,objective)
            VALUES('boundary',?,?,'https://example.invalid',?,1200,80,'[]','unknown')""",
            (corpus, fen, " ".join(full[:length])),
        )
        db.connection.execute(
            "INSERT INTO puzzle_themes VALUES(?,?,'pin',1200)", (corpus, "boundary")
        )
        version, key = "test", "boundary"
    else:
        db.connection.execute("""INSERT INTO public_collections(version,source_url,source_revision,source_sha256,
            content_sha256,content_format,license,attribution,license_notice,accepted,excluded,state)
            VALUES('public-boundary','https://example.invalid','v1','a','b','fen_csv','CC0-1.0','fixture','notice',1,0,'staging')""")
        collection = db.connection.execute(
            "SELECT id FROM public_collections WHERE version='public-boundary'"
        ).fetchone()[0]
        db.connection.execute(
            "INSERT INTO public_tasks VALUES(?,?,?,?,?)",
            (
                collection,
                "boundary",
                board.fen(),
                "legal_line",
                json.dumps([" ".join(full[1 : length + 1])]),
            ),
        )
        db.connection.execute(
            "UPDATE public_collections SET state='ready' WHERE id=?", (collection,)
        )
        version, key = "public-boundary", "boundary"
    db.connection.execute("UPDATE puzzle_corpora SET state='ready' WHERE id=?", (corpus,))
    db.connection.commit()
    if not accepted:
        monkeypatch.setattr(
            related_pin_certificate, "proven", lambda *_: pytest.fail("oversize proof")
        )
    result = preview(db, SUBJECT, evidence, "test")
    if accepted:
        assert len(result["items"]) == 1
        state = start_related(
            db,
            attempt_id="boundary",
            subject=SUBJECT,
            evidence_id=evidence,
            corpus_version="test",
            reference=result["items"][0]["reference"],
        )
        assert state["status"] == "active"
    else:
        assert result["items"] == [] and result["pin_scan"]["root_proofs"] == 0
        with pytest.raises(ValueError):
            resolve_source(db, source_kind, version, key, subject=SUBJECT)
        with pytest.raises(ValueError):
            start_related(
                db,
                attempt_id="boundary",
                subject=SUBJECT,
                evidence_id=evidence,
                corpus_version="test",
                reference="stale-reference",
            )


def test_transfer_source_length_bound_matches_session_admission(tmp_path, monkeypatch):
    for kind, length, accepted in (
        ("corpus", 64, True),
        ("corpus", 66, False),
        ("public", 64, True),
        ("public", 65, False),
    ):
        case = tmp_path / f"{kind}-{length}"
        case.mkdir()
        with monkeypatch.context() as scoped:
            _check_source_length(case, scoped, kind, length, accepted)
