"""Licensed local proofs preserve outcome uncertainty and game history."""

import json
import sys

import chess

from chess_coach.cli import main
from chess_coach.pawn_inspection import inspect_pawn
from chess_coach.pawn_outcome_search import Budget, bounds
from chess_coach.pawn_proof import inspect
from chess_coach.pawn_tables import DIRECTORY, open_verified
from chess_coach.web import create_app
from tests.test_mate_proof import owned_game


def _moves(result):
    return {item["move"]["uci"]: item for item in result["alternatives"]}


def test_opposition_tempo_and_mirrored_colors():
    board = chess.Board("8/8/8/3k4/8/3K4/3P4/8 w - - 0 1")
    for original in (board, board.mirror()):
        result = inspect(original, node_limit=100, max_plies=2)
        assert (result["lower"], result["upper"]) == (0, 0)
        assert result["geometry"]["direct_opposition"]
        other = original.copy()
        other.turn = not other.turn
        result = inspect(other, node_limit=100, max_plies=2)
        assert (result["lower"], result["upper"]) == (-1, -1)


def test_underpromotions_stalemate_double_push_and_en_passant():
    board = chess.Board("7k/P1K5/8/8/8/8/8/8 w - - 0 1")
    choices = _moves(inspect(board, node_limit=100, max_plies=2))
    assert (choices["a7a8q"]["lower"], choices["a7a8q"]["upper"]) == (1, 1)
    assert (choices["a7a8r"]["lower"], choices["a7a8r"]["upper"]) == (1, 1)
    assert (choices["a7a8n"]["lower"], choices["a7a8n"]["upper"]) == (0, 0)
    assert (choices["a7a8b"]["lower"], choices["a7a8b"]["upper"]) == (0, 0)
    mirrored = _moves(inspect(board.mirror(), node_limit=100, max_plies=2))
    assert (mirrored["a2a1q"]["lower"], mirrored["a2a1q"]["upper"]) == (1, 1)
    assert (mirrored["a2a1n"]["lower"], mirrored["a2a1n"]["upper"]) == (0, 0)
    rook = chess.Board("k7/8/PK6/8/8/8/8/8 w - - 0 1")
    assert _moves(inspect(rook, node_limit=50, max_plies=2))["a6a7"]["reason"] == "automatic_draw"
    double = chess.Board("8/8/8/6k1/8/8/4P3/4K3 w - - 0 1")
    assert "e2e4" in _moves(inspect(double, node_limit=50, max_plies=2))
    ep = chess.Board("8/8/8/3pP3/8/8/8/4K2k w - d6 0 1")
    ep_choice = _moves(inspect(ep, node_limit=50, max_plies=2))["e5d6"]
    assert (ep_choice["lower"], ep_choice["upper"]) == (1, 1)
    assert ep_choice["reason"] == "wdl:-2"  # Child is losing; mover is winning.


def test_history_claims_automatic_draws_and_limit():
    board = chess.Board("8/8/8/8/8/8/4P3/K6k w - - 0 1")
    for move in ("a1b1", "h1g1", "b1a1", "g1h1") * 2:
        board.push_uci(move)
    assert board.can_claim_threefold_repetition()
    limited_board = board.copy()
    with open_verified() as tb:
        lower, upper, _ = bounds(board, tb, Budget(100), 0)
        assert (lower, upper) == (0, 1)
        fifty = chess.Board("8/8/8/8/8/8/4P3/K6k w - - 99 1")
        assert fifty.can_claim_fifty_moves()
        assert bounds(fifty, tb, Budget(1), 0)[:2] == (0, 1)
        for move in ("a1b1", "h1g1", "b1a1", "g1h1") * 2:
            board.push_uci(move)
        assert board.is_fivefold_repetition()
        assert bounds(board, tb, Budget(1), 2)[:2] == (0, 0)
        automatic = chess.Board("8/8/8/8/8/8/4P3/K6k w - - 150 1")
        assert bounds(automatic, tb, Budget(1), 2)[:2] == (0, 0)
        mate = chess.Board("7k/6Q1/5K2/8/8/8/8/8 b - - 150 1")
        assert mate.is_checkmate()
        assert bounds(mate, tb, Budget(1), 2)[:2] == (-1, -1)
    unknown = chess.Board("8/8/8/8/8/8/4P3/K6k w - - 99 1")
    assert inspect(unknown)["reason"] == "incomplete_repetition_history"
    unknown.push_uci("e2e4")
    assert inspect(unknown, node_limit=2, max_plies=1)["reason"] != "incomplete_repetition_history"
    limited = inspect(limited_board, node_limit=1, max_plies=1)
    assert limited["status"] == "unknown" and limited["nodes"] == 1


def test_resources_fail_closed(tmp_path):
    manifest = (DIRECTORY / "manifest.json").read_bytes()
    (tmp_path / "manifest.json").write_bytes(manifest)
    assert open_verified(tmp_path) is None
    for source in DIRECTORY.glob("*.rtbw"):
        (tmp_path / source.name).write_bytes(source.read_bytes())
    victim = tmp_path / "KPvK.rtbw"
    data = bytearray(victim.read_bytes())
    data[4] ^= 1
    victim.write_bytes(data)
    assert open_verified(tmp_path) is None


def test_owned_inspection_cli_browser_and_stale(tmp_path, monkeypatch, capsys):
    fen = "8/8/8/8/4k3/8/4P3/4K3 w - - 0 1"
    path = tmp_path / "pawn.sqlite"
    db = owned_game(path, monkeypatch, fen=fen, move="e3")
    changes = db.connection.total_changes
    result = inspect_pawn(db, 1, learner="fixture_a")
    assert result["status"] == "current" and result["proof"]["lower"] == 0
    assert db.connection.total_changes == changes
    assert inspect_pawn(db, 1, learner="fixture_b")["status"] == "unavailable"
    assert inspect_pawn(db, 1, learner="fixture_a", expected_fingerprint="old")["status"] == "stale"
    monkeypatch.setenv("LICHESS_USERNAME", "fixture_a")
    monkeypatch.setattr(sys, "argv", ["chess-coach", "--db", str(path), "inspect-pawn", "1"])
    main()
    assert json.loads(capsys.readouterr().out)["status"] == "current"
    app = create_app(
        db_path=path,
        subject="fixture_a",
        actor="operator",
        corpus="test",
        login="fixture",
        origin="https://coach.invalid",
    )
    client = app.test_client()
    assert client.get("/decisions/1/pawn", base_url="https://coach.invalid").status_code == 403
    page = client.get(
        "/decisions/1/pawn",
        base_url="https://coach.invalid",
        headers={"Tailscale-User-Login": "fixture"},
    )
    assert page.status_code == 200 and b"not skill or mastery" in page.data
    stale = client.get(
        "/decisions/1/pawn?source=old",
        base_url="https://coach.invalid",
        headers={"Tailscale-User-Login": "fixture"},
    )
    assert b"stale" in stale.data and b"Source fingerprint" not in stale.data
    assert db.connection.execute("SELECT COUNT(*) FROM evidence_mappings").fetchone()[0] == 0


def test_cursed_and_blessed_wdl_remain_distinct():
    from chess_coach.pawn_outcome_leaf import reset_value

    class Table:
        def __init__(self, result):
            self.result = result

        def probe_wdl(self, board):
            return self.result

    board = chess.Board("8/8/8/8/8/8/4P3/K6k w - - 0 1")
    assert reset_value(board, Table(1)) == (0, 0, "wdl:1")
    assert reset_value(board, Table(-1)) == (0, 0, "wdl:-1")
    claimable = chess.Board("8/8/8/8/8/8/4P3/K6k w - - 99 1")
    assert claimable.can_claim_draw()
    assert bounds(claimable, Table(-2), Budget(50), 1)[:2] == (1, 1)


def test_source_changed_during_inspection_is_stale(tmp_path, monkeypatch):
    import chess_coach.pawn_inspection as module

    db = owned_game(
        tmp_path / "stale.sqlite", monkeypatch, fen="8/8/8/8/4k3/8/4P3/4K3 w - - 0 1", move="e3"
    )
    original = module.inspect

    def changed(board):
        result = original(board, node_limit=1)
        db.connection.execute("UPDATE pipeline_stages SET status='pending' WHERE stage='analysis'")
        db.connection.commit()
        return result

    monkeypatch.setattr(module, "inspect", changed)
    assert module.inspect_pawn(db, 1, learner="fixture_a") == {
        "status": "stale",
        "version": "pawn-proof-v1",
    }


def test_missing_proof_and_unsupported_compositions_are_unknown(monkeypatch):
    import chess_coach.pawn_proof as proof

    board = chess.Board("8/8/8/8/8/8/4P3/K6k w - - 0 1")
    monkeypatch.setattr(proof, "open_verified", lambda: None)
    assert proof.inspect(board)["reason"] == "proof_resources_unavailable"
    extra = chess.Board("8/8/8/8/8/8/3PP3/K6k w - - 0 1")
    assert proof.inspect(extra)["status"] == "unsupported"
