"""Development smoke tests for current owned-deep fork processing."""

from pathlib import Path

import chess
import chess.pgn
import httpx
import pytest

from chess_coach.db import Database
from chess_coach.evidence_review import inspect_evidence
from chess_coach.ingest import ingest_pgn
from chess_coach.pipeline import process_pipeline
from chess_coach.pipeline_config import PipelineConfig
from chess_coach.web import create_app


@pytest.mark.skipif(not Path("/usr/games/stockfish").is_file(), reason="Stockfish not installed")
@pytest.mark.parametrize("black", [False, True])
def test_real_deep_played_knight_fork_worker_and_browser(tmp_path, black):
    board = chess.Board("r3k3/7p/8/1N6/8/8/6P1/7K w - - 0 1")
    if black:
        board = board.mirror()
    move, reply = ("b4c2", "e1f1") if black else ("b5c7", "e8f8")
    game = chess.pgn.Game()
    game.setup(board)
    game.headers["White"] = "fixture_opponent" if black else "fixture_learner"
    game.headers["Black"] = "fixture_learner" if black else "fixture_opponent"
    game.headers["Result"] = "*"
    node = game.add_variation(board.parse_uci(move))
    board.push_uci(move)
    node.add_variation(board.parse_uci(reply))
    db = Database(tmp_path / "fork-deep.sqlite")
    db.initialize()
    ingest_pgn(db, str(game))
    config = PipelineConfig(
        learner="fixture_learner",
        engine_path="/usr/games/stockfish",
        nodes=10000,
        seconds_per_position=1.0,
        deep_per_game=1,
        deep_max_jobs=1,
        deep_max_games=1,
        material_max_decisions=1,
    )
    report = process_pipeline(
        db, config, transport=httpx.MockTransport(lambda request: httpx.Response(200))
    )
    assert report["deep"]["processed"] == 1
    row = db.connection.execute(
        "SELECT id FROM evidence_mappings WHERE skill=?", ("fork",)
    ).fetchone()
    assert row is not None, report["forks"]
    evidence = inspect_evidence(db, row["id"])
    assert evidence["context"]["provenance"]["kind"] == "deep", evidence["context"]["provenance"]
    assert evidence["outcome"] == "success", evidence["context"]["fork_observation"]
    assert (
        evidence["review_status"] == "unreviewed"
        and evidence["fork_source_currentness"] == "current"
    )
    app = create_app(
        db_path=tmp_path / "fork-deep.sqlite",
        subject="fixture_learner",
        actor="fixture_reviewer",
        corpus="test",
        login="fixture-login",
        origin="https://coach.invalid",
    )
    page = app.test_client().get(
        f"/evidence/{row['id']}",
        base_url="https://coach.invalid",
        headers={"Tailscale-User-Login": "fixture-login"},
    )
    assert page.status_code == 200 and b"Fork source: current" in page.data
    assert b"Provisional bounded observation" in page.data


@pytest.mark.skipif(not Path("/usr/games/stockfish").is_file(), reason="Stockfish not installed")
@pytest.mark.parametrize("black", [False, True])
@pytest.mark.parametrize("played_kind", ["king", "pawn"])
def test_real_deep_missed_knight_fork_worker(tmp_path, black, played_kind):
    from chess_coach.fork_proof import fork_proof
    from chess_coach.material_lines import continuation, material, unopposed_material_loss
    from chess_coach.material_source import prepare

    board = chess.Board("r3k3/7p/8/1N6/8/8/6P1/7K w - - 0 1")
    if black:
        board = board.mirror()
    played = {"king": ("h1g1", "h8g8"), "pawn": ("g2g3", "g7g6")}[played_kind][black]
    reply = "e1f1" if black else "e8f8"
    game = chess.pgn.Game()
    game.setup(board)
    game.headers["White"] = "fixture_opponent" if black else "fixture_learner"
    game.headers["Black"] = "fixture_learner" if black else "fixture_opponent"
    game.headers["Result"] = "*"
    node = game.add_variation(board.parse_uci(played))
    board.push_uci(played)
    node.add_variation(board.parse_uci(reply))
    db = Database(tmp_path / "missed.sqlite")
    db.initialize()
    ingest_pgn(db, str(game))
    config = PipelineConfig(
        learner="fixture_learner",
        engine_path="/usr/games/stockfish",
        nodes=10000,
        seconds_per_position=1.0,
        deep_per_game=1,
        deep_max_jobs=1,
        deep_max_games=1,
        material_max_decisions=1,
    )
    report = process_pipeline(
        db, config, transport=httpx.MockTransport(lambda request: httpx.Response(200))
    )
    prepared = prepare(db, 1, "fixture_learner")
    row = db.connection.execute(
        "SELECT id FROM evidence_mappings WHERE skill=?", ("fork",)
    ).fetchone()
    assert prepared["provenance"]["kind"] == "deep", prepared["provenance"]
    assert prepared["provenance"]["qualified_roles"] == ["best", "played"]
    assert row is not None, {
        "forks": report["forks"],
        "best": prepared["best"],
        "played": prepared["played"],
    }
    evidence = inspect_evidence(db, row["id"])
    fact = evidence["context"]["fork_observation"]
    root = game.board()
    best_move = chess.Move.from_uci(prepared["best"]["root_move"])
    proof = fork_proof(root, best_move)
    assert proof and proof["minimum_gain"] == 3
    after = root.copy()
    after.push(best_move)
    assert {branch["reply"] for branch in proof["branches"]} == {
        move.uci() for move in after.legal_moves
    }
    initial = material(root, root.turn)
    for branch in proof["branches"]:
        reply = after.copy()
        reply.push_uci(branch["reply"])
        capture = chess.Move.from_uci(branch["capture"])
        assert capture in reply.legal_moves and reply.is_capture(capture)
        reply.push(capture)
        counters = list(reply.legal_moves)
        assert 0 < len(counters) <= 64
        for counter in counters:
            assert not (
                reply.gives_check(counter) or counter.promotion or reply.is_en_passant(counter)
            )
            final = reply.copy()
            final.push(counter)
            assert material(final, root.turn) - initial >= 3
    best = continuation(root, prepared["best"], best_move.uci(), allow_checks=True, minimum_plies=4)
    actual = continuation(root, prepared["played"], played)
    if evidence["outcome"] == "ambiguous":
        assert fact["reason"] == "continuation_unavailable"
        assert best is None or actual is None
    else:
        assert evidence["outcome"] == "failure" and fact["proof"] == proof
        assert best is not None and actual is not None
        assert unopposed_material_loss(prepared["best"], prepared["played"])
        assert best["material_delta"] >= 3
        assert actual["material_delta"] <= best["material_delta"] - 3
        assert fact["best"] == best and fact["played"] == actual
    assert evidence["fork_source_currentness"] == "current"
    assert evidence["review_status"] == "unreviewed"
