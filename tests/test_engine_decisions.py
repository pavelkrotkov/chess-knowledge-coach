from __future__ import annotations

import json
import sys
from pathlib import Path

import chess
import chess.engine
import pytest

from chess_coach.analysis import analyze_game, merge_analysis_outputs
from chess_coach.db import SCHEMA, Database
from chess_coach.ingest import ingest_pgn

PGN = """[Event "Test"]
[White "A"]
[Black "B"]
[Result "*"]

1. e4 e5 *
"""
CUSTOM = """[Event "Custom"]
[White "A"]
[Black "B"]
[Result "*"]
[SetUp "1"]
[FEN "8/8/8/8/8/5k2/8/4K3 b - - 0 1"]

1... Kf4 2. Kd2 *
"""
TERMINAL = """[Event "Terminal"]
[White "A"]
[Black "B"]
[Result "*"]
[SetUp "1"]
[FEN "7k/6Q1/5K2/8/8/8/8/8 b - - 0 1"]

*
"""


class FakeEngine:
    def __init__(self, *, fail: bool = False, empty: bool = False) -> None:
        self.id = {"name": "Fake Engine", "author": "Test"}
        self.options = {}
        self.boards = []
        self.fail = fail
        self.empty = empty
        self.closed = False

    def configure(self, settings):
        self.settings = settings

    def analyse(self, board, limit, multipv, root_moves=None):
        if root_moves is None:
            self.boards.append(board.copy())
        if self.fail and len(self.boards) == 2:
            raise RuntimeError("engine failed")
        if self.empty:
            return [
                {},
                {"score": chess.engine.PovScore(chess.engine.Cp(42), chess.WHITE), "pv": []},
            ]
        return [
            {
                "score": chess.engine.PovScore(chess.engine.Cp(100), chess.WHITE),
                "pv": [root_moves[0] if root_moves else next(iter(board.legal_moves))],
                "nodes": 10,
                "depth": 2,
            }
        ]

    def quit(self):
        self.closed = True


def database(pgn: str = PGN) -> Database:
    db = Database(":memory:")
    db.initialize()
    ingest_pgn(db, pgn)
    return db


def run_fake(monkeypatch, db: Database, engine: FakeEngine) -> int:
    monkeypatch.setattr(chess.engine.SimpleEngine, "popen_uci", lambda _: engine)
    return analyze_game(db, 1, sys.executable, nodes=100)


@pytest.mark.parametrize("pgn", [PGN, CUSTOM])
def test_decisions_match_pre_move_board_and_score_perspective(monkeypatch, pgn):
    db = database(pgn)
    raw_before = [
        tuple(row) for row in db.connection.execute("SELECT * FROM positions ORDER BY ply")
    ]
    engine = FakeEngine()
    run_id = run_fake(monkeypatch, db, engine)
    rows = db.connection.execute(
        "SELECT e.*, p.fen AS after_fen, p.ply FROM engine_outputs e "
        "JOIN positions p ON p.id = e.position_id WHERE run_id = ? ORDER BY p.ply",
        (run_id,),
    ).fetchall()
    assert len(rows) == 2
    for row, board in zip(rows, engine.boards, strict=True):
        assert row["decision_fen"] == board.fen()
        assert row["score_pov"] == ("white" if board.turn else "black")
        assert row["score_cp"] == (100 if board.turn else -100)
        assert chess.Move.from_uci(row["played_move"]) in board.legal_moves
        assert chess.Move.from_uci(row["best_move"]) in board.legal_moves
        board.push_uci(row["played_move"])
        assert row["after_fen"] == board.fen()
    if pgn == PGN:
        assert rows[0]["decision_fen"] == chess.Board().fen()
    else:
        assert rows[0]["score_pov"] == "black"
        assert rows[0]["decision_fen"] == "8/8/8/8/8/5k2/8/4K3 b - - 0 1"
    config = json.loads(
        db.connection.execute(
            "SELECT config_json FROM analysis_runs WHERE id = ?", (run_id,)
        ).fetchone()[0]
    )
    assert (config["position_semantics"], config["score_perspective"], config["mate_score"]) == (
        "pre_move_v1",
        "side_to_move",
        100000,
    )
    assert engine.closed
    assert [
        tuple(row) for row in db.connection.execute("SELECT * FROM positions ORDER BY ply")
    ] == raw_before


def test_empty_pv_and_terminal_position(monkeypatch):
    db = database()
    engine = FakeEngine(empty=True)
    run_fake(monkeypatch, db, engine)
    rows = db.connection.execute(
        "SELECT best_move, pv, played_move, score_cp FROM engine_outputs"
    ).fetchall()
    assert len(rows) == 4
    assert all(
        row["best_move"] is None and row["pv"] is None and row["played_move"] for row in rows
    )
    assert any(row["score_cp"] is None for row in rows)
    terminal = database(TERMINAL)
    engine = FakeEngine()
    run_fake(monkeypatch, terminal, engine)
    assert engine.boards == []
    assert terminal.connection.execute("SELECT COUNT(*) FROM engine_outputs").fetchone()[0] == 0


def test_failed_engine_run_rolls_back_before_later_commit(monkeypatch):
    db = database()
    engine = FakeEngine(fail=True)
    with pytest.raises(RuntimeError, match="engine failed"):
        run_fake(monkeypatch, db, engine)
    assert engine.closed
    assert not db.connection.in_transaction
    db.connection.execute("UPDATE games SET event = 'later' WHERE id = 1")
    db.connection.commit()
    assert db.connection.execute("SELECT COUNT(*) FROM analysis_runs").fetchone()[0] == 0
    assert db.connection.execute("SELECT COUNT(*) FROM engine_outputs").fetchone()[0] == 0


def test_mismatched_raw_position_rejects_and_rolls_back(monkeypatch):
    db = database()
    db.connection.execute("UPDATE positions SET fen = 'wrong' WHERE ply = 2")
    db.connection.commit()
    with pytest.raises(ValueError, match="stored position"):
        run_fake(monkeypatch, db, FakeEngine())
    assert db.connection.execute("SELECT COUNT(*) FROM analysis_runs").fetchone()[0] == 0


def test_merge_preserves_decision_provenance(monkeypatch):
    source, target = database(), database()
    run_fake(monkeypatch, source, FakeEngine())
    assert merge_analysis_outputs(target, source) == 2
    assert [
        tuple(row)
        for row in source.connection.execute(
            "SELECT decision_fen, score_pov FROM engine_outputs ORDER BY id"
        )
    ] == [
        tuple(row)
        for row in target.connection.execute(
            "SELECT decision_fen, score_pov FROM engine_outputs ORDER BY id"
        )
    ]


def test_upgrade_from_v1_keeps_old_engine_decision_unknown():
    db = Database(":memory:")
    legacy = SCHEMA.replace("    decision_fen TEXT, score_pov TEXT\n", "")
    # Before version 2, the preceding depth column ended the table definition.
    legacy = legacy.replace(
        "    pv TEXT, nodes INTEGER, depth INTEGER,\n",
        "    pv TEXT, nodes INTEGER, depth INTEGER\n",
    )
    db.connection.executescript(legacy)
    db.connection.execute(
        "INSERT INTO games (pgn, white, black, result) VALUES ('x', 'A', 'B', '*')"
    )
    db.connection.execute(
        "INSERT INTO positions (game_id, ply, fen, san, uci) VALUES (1, 1, 'x', 'e4', 'e2e4')"
    )
    db.connection.execute(
        "INSERT INTO analysis_runs (game_id, engine, engine_version, config_json) VALUES (1, 'old', 'old', '{}')"
    )
    db.connection.execute(
        "INSERT INTO engine_outputs (run_id, position_id, score_cp) VALUES (1, 1, 10)"
    )
    db.connection.execute("PRAGMA user_version = 1")
    db.connection.commit()
    db.initialize()
    output = db.connection.execute(
        "SELECT score_cp, decision_fen, score_pov FROM engine_outputs"
    ).fetchone()
    assert tuple(output) == (10, None, None)
    assert db.connection.execute("PRAGMA user_version").fetchone()[0] == 27


@pytest.mark.skipif(not Path("/usr/games/stockfish").is_file(), reason="Stockfish not installed")
def test_actual_stockfish_bounded_smoke(tmp_path):
    db = Database(tmp_path / "engine-smoke.sqlite")
    db.initialize()
    ingest_pgn(db, PGN)
    run_id = analyze_game(db, 1, nodes=300, threads=1, hash_mb=1)
    rows = db.connection.execute(
        "SELECT * FROM engine_outputs WHERE run_id = ? ORDER BY id", (run_id,)
    ).fetchall()
    assert len(rows) == 2
    for row in rows:
        board = chess.Board(row["decision_fen"])
        assert chess.Move.from_uci(row["played_move"]) in board.legal_moves
        assert chess.Move.from_uci(row["best_move"]) in board.legal_moves
        assert row["score_pov"] == ("white" if board.turn else "black")


def test_final_checkmate_board_is_not_an_extra_decision(monkeypatch):
    game = PGN.replace("1. e4 e5 *", "1. f3 e5 2. g4 Qh4# 0-1")
    db = database(game)
    engine = FakeEngine()
    run_fake(monkeypatch, db, engine)
    assert len(engine.boards) == 4
    last_fen = db.connection.execute(
        "SELECT fen FROM positions ORDER BY ply DESC LIMIT 1"
    ).fetchone()[0]
    assert chess.Board(last_fen).is_checkmate()
    assert all(not board.is_game_over() for board in engine.boards)


def test_merge_uninitialized_v1_source_preserves_legacy_outputs_and_source(tmp_path):
    source_path = tmp_path / "legacy.sqlite"
    legacy = SCHEMA.replace("    decision_fen TEXT, score_pov TEXT\n", "").replace(
        "    pv TEXT, nodes INTEGER, depth INTEGER,\n",
        "    pv TEXT, nodes INTEGER, depth INTEGER\n",
    )
    setup = Database(source_path)
    setup.connection.executescript(legacy)
    setup.connection.execute("PRAGMA user_version = 1")
    ingest_pgn(setup, PGN)
    setup.connection.execute(
        "INSERT INTO analysis_runs (game_id, engine, engine_version, config_json) "
        "VALUES (1, 'legacy', 'v1', '{}')"
    )
    setup.connection.executemany(
        "INSERT INTO engine_outputs (run_id, position_id, score_cp) VALUES (1, ?, ?)",
        [(1, 42), (2, -25)],
    )
    setup.connection.commit()
    setup.close()
    before = source_path.read_bytes()
    source = Database(source_path)  # A read source need not be migrated.
    target = database()
    incomplete_target = database()
    incomplete_target.connection.execute("DELETE FROM positions WHERE game_id = 1 AND ply = 2")
    incomplete_target.connection.commit()

    with pytest.raises(ValueError, match="missing ply 2"):
        merge_analysis_outputs(incomplete_target, source)
    assert (
        incomplete_target.connection.execute("SELECT COUNT(*) FROM analysis_runs").fetchone()[0]
        == 0
    )
    assert (
        incomplete_target.connection.execute("SELECT COUNT(*) FROM engine_outputs").fetchone()[0]
        == 0
    )

    assert merge_analysis_outputs(target, source) == 2
    rows = target.connection.execute(
        "SELECT score_cp, decision_fen, score_pov FROM engine_outputs ORDER BY id"
    ).fetchall()
    assert [tuple(row) for row in rows] == [(42, None, None), (-25, None, None)]
    assert source.connection.execute("PRAGMA user_version").fetchone()[0] == 1
    assert source_path.read_bytes() == before
    source.close()


def test_engine_transport_closes_if_quit_fails(monkeypatch):
    class BrokenQuit(FakeEngine):
        def __init__(self):
            super().__init__()
            self.transport_closed = False

        def quit(self):
            raise TimeoutError("engine did not exit")

        def close(self):
            self.transport_closed = True

    db = database()
    engine = BrokenQuit()
    with pytest.raises(TimeoutError):
        run_fake(monkeypatch, db, engine)
    assert engine.transport_closed
    assert db.connection.execute("SELECT COUNT(*) FROM analysis_runs").fetchone()[0] == 0
    assert db.connection.execute("SELECT COUNT(*) FROM engine_outputs").fetchone()[0] == 0


def test_analysis_spools_only_required_fields_beside_database(tmp_path, monkeypatch):
    import os
    from contextlib import contextmanager

    from chess_coach import analysis_transaction

    db = Database(tmp_path / "engine.sqlite")
    db.initialize()
    ingest_pgn(db, PGN)
    original = analysis_transaction.TemporaryFile
    sizes = []

    @contextmanager
    def inspect_spool(*args, **kwargs):
        assert kwargs["dir"] == tmp_path
        with original(*args, **kwargs) as spool:
            assert os.fstat(spool.fileno()).st_mode & 0o777 == 0o600
            yield spool
            sizes.append(os.fstat(spool.fileno()).st_size)

    class ExtraEngine(FakeEngine):
        def analyse(self, board, limit, multipv, root_moves=None):
            lines = super().analyse(board, limit, multipv, root_moves=root_moves)
            lines[0]["unused"] = object()
            lines[0]["large_unused"] = "x" * 1_000_000
            return lines

    monkeypatch.setattr(analysis_transaction, "TemporaryFile", inspect_spool)
    before = set(tmp_path.iterdir())
    run_id = run_fake(monkeypatch, db, ExtraEngine())
    assert sizes and sizes[0] < 4096
    assert set(tmp_path.iterdir()) == before
    assert (
        db.connection.execute(
            "SELECT COUNT(*) FROM engine_outputs WHERE run_id=?", (run_id,)
        ).fetchone()[0]
        == 2
    )
