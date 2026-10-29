"""Native same-board scores, history, persistence and inspection."""

import json
import sys
from pathlib import Path

import chess
import chess.engine
import pytest

from chess_coach.analysis import analyze_game, merge_analysis_outputs
from chess_coach.cli import main
from chess_coach.db import Database
from chess_coach.decision_inspection import inspect_decision
from chess_coach.ingest import ingest_pgn
from chess_coach.web import create_app

PGN = """[Event "Synthetic"]
[White "A"]
[Black "B"]
[Result "*"]

1. Nf3 Nf6 2. Ng1 Ng8 3. Nf3 *
"""


class Engine:
    def __init__(self):
        self.id = {"name": "Synthetic engine"}
        self.options = {"UCI_ShowWDL": object()}
        self.calls = []

    def configure(self, settings):
        self.settings = settings

    def analyse(self, board, limit, multipv, root_moves=None):
        self.calls.append((board.copy(), limit, root_moves))
        move = root_moves[0] if root_moves else next(iter(board.legal_moves))
        return [
            {
                "score": chess.engine.PovScore(chess.engine.Cp(42), chess.WHITE),
                "lowerbound": True,
                "wdl": chess.engine.PovWdl(chess.engine.Wdl(700, 200, 100), chess.WHITE),
                "pv": [move],
                "nodes": 19,
                "depth": 4,
                "seldepth": 5,
                "time": 0.02,
            }
        ]

    def quit(self):
        pass


def make_db(path, pgn=PGN):
    db = Database(path)
    db.initialize()
    ingest_pgn(db, pgn)
    return db


def run_fake(db, monkeypatch, engine):
    monkeypatch.setattr(chess.engine.SimpleEngine, "popen_uci", lambda _: engine)
    return analyze_game(db, 1, sys.executable, nodes=100, depth=4, time_limit=0.5)


def test_same_board_history_native_scores_bounds_and_wdl(tmp_path, monkeypatch):
    db = make_db(tmp_path / "comparison.sqlite")
    engine = Engine()
    run_id = run_fake(db, monkeypatch, engine)
    rows = db.connection.execute(
        """SELECT d.*, p.ply, p.uci FROM decision_analysis_lines d
        JOIN positions p ON p.id=d.position_id WHERE d.run_id=? ORDER BY p.ply,d.role""",
        (run_id,),
    ).fetchall()
    assert len(rows) == 10 and len(engine.calls) == 10
    assert engine.settings["UCI_ShowWDL"] is True
    for index in range(5):
        best, played = rows[2 * index : 2 * index + 2]
        a, b = engine.calls[2 * index : 2 * index + 2]
        assert best["role"] == "best" and played["role"] == "played"
        assert a[0].fen() == b[0].fen() == best["decision_fen"] == played["decision_fen"]
        assert a[0].move_stack == b[0].move_stack
        assert b[2] == [chess.Move.from_uci(played["uci"])]
        assert a[1].nodes == b[1].nodes == 100 and a[1].time == b[1].time == 0.5
        assert played["root_move"] == played["uci"]
        assert best["score_kind"] == "cp" and best["nodes"] == 19
        if best["score_pov"] == "white":
            assert (best["score_value"], best["score_bound"], json.loads(best["wdl_json"])) == (
                42,
                "lower",
                [700, 200, 100],
            )
        else:
            assert (best["score_value"], best["score_bound"], json.loads(best["wdl_json"])) == (
                -42,
                "upper",
                [100, 200, 700],
            )
    assert engine.calls[8][0].is_repetition(2)
    config = json.loads(
        db.connection.execute("SELECT config_json FROM analysis_runs").fetchone()[0]
    )
    assert config["limits_apply_per_search"] and config["native_wdl_requested"]
    assert config["multipv"] == config["played_multipv"] == 1
    assert len(config["engine_sha256"]) == 64
    assert db.connection.execute("SELECT COUNT(*) FROM evidence_mappings").fetchone()[0] == 0


def test_inspection_cli_browser_and_merge(tmp_path, monkeypatch, capsys):
    source = make_db(tmp_path / "source.sqlite")
    target = make_db(tmp_path / "target.sqlite")
    run_id = run_fake(source, monkeypatch, Engine())
    assert merge_analysis_outputs(target, source) == 5
    assert (
        target.connection.execute("SELECT COUNT(*) FROM decision_analysis_lines").fetchone()[0]
        == 10
    )
    report = inspect_decision(target, 1, run_id=1)
    assert report["status"] == "limited" and report["played"]["san"] == ["Nf3"]
    assert report["best"]["score_bound"] == "lower" and report["run"]["config"]["nodes"] == 100
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "chess-coach",
            "--db",
            str(tmp_path / "target.sqlite"),
            "inspect-decision",
            "1",
            "--run-id",
            "1",
        ],
    )
    main()
    assert json.loads(capsys.readouterr().out)["played"]["san"] == ["Nf3"]
    app = create_app(
        db_path=tmp_path / "target.sqlite",
        subject="learner",
        actor="reviewer",
        corpus="test",
        login="fixture",
        origin="https://coach.invalid",
    )
    client = app.test_client()
    assert client.get("/decisions/1", base_url="https://coach.invalid").status_code == 403
    page = client.get(
        "/decisions/1",
        base_url="https://coach.invalid",
        headers={"Tailscale-User-Login": "fixture"},
    )
    assert page.status_code == 200 and b"Nf3" in page.data and b"bounded search" in page.data
    assert (
        source.connection.execute(
            "SELECT COUNT(*) FROM decision_analysis_lines WHERE run_id=?", (run_id,)
        ).fetchone()[0]
        == 10
    )


def test_legacy_unavailable_and_transactional_v15_upgrade(tmp_path):
    db = make_db(tmp_path / "upgrade.sqlite")
    db.connection.execute(
        "INSERT INTO analysis_runs(game_id,engine,engine_version,config_json) VALUES(1,'old','old','{}')"
    )
    db.connection.execute("DROP TABLE decision_analysis_lines")
    db.connection.execute("PRAGMA user_version=15")
    db.connection.commit()
    db.initialize()
    assert db.connection.execute("PRAGMA user_version").fetchone()[0] == 23
    result = inspect_decision(db, 1)
    assert result["status"] == "analysis_unavailable" and result["best"] is None
    assert result["run"]["engine"] == "old"


def test_illegal_forced_pv_rolls_back_all_outputs(tmp_path, monkeypatch):
    class Broken(Engine):
        def analyse(self, board, limit, multipv, root_moves=None):
            lines = super().analyse(board, limit, multipv, root_moves=root_moves)
            if root_moves:
                lines[0]["pv"] = [chess.Move.from_uci("a1a8")]
            return lines

    db = make_db(tmp_path / "broken.sqlite")
    with pytest.raises(ValueError, match="illegal PV"):
        run_fake(db, monkeypatch, Broken())
    assert db.connection.execute("SELECT COUNT(*) FROM analysis_runs").fetchone()[0] == 0
    assert db.connection.execute("SELECT COUNT(*) FROM decision_analysis_lines").fetchone()[0] == 0


@pytest.mark.skipif(not Path("/usr/games/stockfish").is_file(), reason="Stockfish not installed")
def test_real_stockfish_comparison(tmp_path):
    db = make_db(tmp_path / "real.sqlite")
    run_id = analyze_game(db, 1, nodes=300, threads=1, hash_mb=1)
    report = inspect_decision(db, 1, run_id=run_id)
    assert report["status"] == "limited"
    assert report["played"]["root_move"] == report["played_move"]
    assert report["best"]["score_kind"] in {"cp", "mate"}


def test_mate_terminal_equal_move_custom_fen(tmp_path, monkeypatch):
    pgn = """[Event "Synthetic"]
[White "A"]
[Black "B"]
[Result "1-0"]
[SetUp "1"]
[FEN "7k/8/6K1/2Q5/8/8/8/8 w - - 1 2"]

2. Qf8# 1-0
"""

    class MateEngine(Engine):
        def analyse(self, board, limit, multipv, root_moves=None):
            self.calls.append((board.copy(), limit, root_moves))
            return [
                {
                    "score": chess.engine.PovScore(chess.engine.Mate(1), board.turn),
                    "pv": [chess.Move.from_uci("c5f8")],
                    "nodes": 20,
                    "depth": 2,
                }
            ]

    db = make_db(tmp_path / "mate.sqlite", pgn)
    engine = MateEngine()
    run_fake(db, monkeypatch, engine)
    report = inspect_decision(db, 1)
    assert len(engine.calls) == 2 and report["best"]["root_move"] == report["played_move"]
    for role in ("best", "played"):
        assert report[role]["score_kind"] == "mate" and report[role]["score_value"] == 1
        assert report[role]["score_bound"] == "exact" and report[role]["san"] == ["Qf8#"]
        assert report[role]["terminal"] == "1-0" and report[role]["terminal_reason"] == "checkmate"
        assert report[role]["wdl"] is None


def test_mismatched_game_history_aborts_merge(tmp_path, monkeypatch):
    source = make_db(tmp_path / "source-history.sqlite")
    target = make_db(tmp_path / "target-history.sqlite")
    run_fake(source, monkeypatch, Engine())
    target.connection.execute("UPDATE games SET pgn = pgn || ' '")
    target.connection.commit()
    with pytest.raises(ValueError, match="history does not match"):
        merge_analysis_outputs(target, source)
    assert target.connection.execute("SELECT COUNT(*) FROM analysis_runs").fetchone()[0] == 0
    assert (
        target.connection.execute("SELECT COUNT(*) FROM decision_analysis_lines").fetchone()[0] == 0
    )


def test_migration_failure_rolls_back(tmp_path, monkeypatch):
    from chess_coach import db_recent

    db = make_db(tmp_path / "rollback.sqlite")
    db.connection.execute("DROP TABLE decision_analysis_lines")
    db.connection.execute("PRAGMA user_version=15")
    db.connection.commit()
    original = db_recent.add_comparison_lines

    def fail(connection):
        original(connection)
        raise ValueError("synthetic migration failure")

    monkeypatch.setattr(db_recent, "add_comparison_lines", fail)
    with pytest.raises(ValueError, match="synthetic migration failure"):
        db.initialize()
    assert db.connection.execute("PRAGMA user_version").fetchone()[0] == 15
    assert (
        db.connection.execute(
            "SELECT 1 FROM sqlite_master WHERE name='decision_analysis_lines'"
        ).fetchone()
        is None
    )
    assert db.connection.execute("SELECT COUNT(*) FROM games").fetchone()[0] == 1


def test_pipeline_replays_complete_pair_and_rebuilds_missing_line(tmp_path, monkeypatch):
    from chess_coach.pipeline_config import PipelineConfig
    from chess_coach.pipeline_work import run_analysis

    db = make_db(tmp_path / "replay.sqlite")
    monkeypatch.setattr(chess.engine.SimpleEngine, "popen_uci", lambda _: Engine())
    config = PipelineConfig(learner="learner", engine_path=sys.executable, nodes=100)
    first = run_analysis(db, 1, "synthetic-game", config, "synthetic-engine")
    assert first["status"] == "complete" and not first["replayed"]
    replay = run_analysis(db, 1, "synthetic-game", config, "synthetic-engine")
    assert replay["replayed"] and replay["output_id"] == first["output_id"]
    db.connection.execute(
        "DELETE FROM decision_analysis_lines WHERE run_id=? AND position_id=1 AND role='played'",
        (first["output_id"],),
    )
    db.connection.commit()
    rebuilt = run_analysis(db, 1, "synthetic-game", config, "synthetic-engine")
    assert rebuilt["status"] == "complete" and not rebuilt["replayed"]
    assert rebuilt["output_id"] != first["output_id"]
    assert (
        db.connection.execute(
            "SELECT COUNT(*) FROM decision_analysis_lines WHERE run_id=?", (rebuilt["output_id"],)
        ).fetchone()[0]
        == 10
    )


def test_missing_engine_line_preserves_requested_root_but_is_unavailable(tmp_path, monkeypatch):
    class EmptyEngine(Engine):
        def analyse(self, board, limit, multipv, root_moves=None):
            return [{}]

    db = make_db(tmp_path / "missing.sqlite")
    run_fake(db, monkeypatch, EmptyEngine())
    report = inspect_decision(db, 1)
    assert report["status"] == "incomplete"
    assert report["played"]["root_move"] == report["played_move"]
    assert report["played"]["status"] == "unavailable"
    assert report["best"]["status"] == "unavailable"


@pytest.mark.parametrize(
    "defect",
    ["board", "pov", "semantics", "root", "illegal_pv", "wrong_played_root", "empty_wrong_pov"],
)
def test_rejected_line_never_displays_its_score_or_wdl(tmp_path, monkeypatch, capsys, defect):
    db_path = tmp_path / "rejected.sqlite"
    db = make_db(db_path)
    run_fake(db, monkeypatch, Engine())
    role = "played" if defect in {"wrong_played_root", "empty_wrong_pov"} else "best"
    row = db.connection.execute(
        "SELECT * FROM decision_analysis_lines WHERE position_id=1 AND role=?", (role,)
    ).fetchone()
    changes = {
        "board": {"decision_fen": "different"},
        "pov": {"score_pov": "black"},
        "semantics": {"semantics": "unsupported"},
        "root": {"root_move": "a2a3"},
        "illegal_pv": {"pv": row["root_move"] + " a2a3"},
        "wrong_played_root": {"root_move": "g1h3", "pv": "g1h3"},
        "empty_wrong_pov": {"score_pov": "black", "pv": None},
    }[defect]
    assignments = ", ".join(f"{column}=?" for column in changes)
    db.connection.execute(
        f"UPDATE decision_analysis_lines SET {assignments}, score_kind='cp', score_value=987654, "
        "score_bound='lower', wdl_json='[777,111,112]' WHERE id=?",
        (*changes.values(), row["id"]),
    )
    db.connection.commit()
    report = inspect_decision(db, 1)
    rejected = report[role]
    assert rejected["status"] == "unavailable"
    assert rejected["score_kind"] is None and rejected["score_value"] is None
    assert rejected["score_bound"] is None and rejected["wdl"] is None
    assert rejected["pv"] is None and rejected["root_move"] is None
    assert rejected["nodes"] is None and rejected["depth"] is None
    other = "best" if role == "played" else "played"
    assert report[other]["status"] == "limited" and report[other]["score_value"] == 42
    persisted = db.connection.execute(
        "SELECT score_value, wdl_json FROM decision_analysis_lines WHERE id=?", (row["id"],)
    ).fetchone()
    assert tuple(persisted) == (987654, "[777,111,112]")

    monkeypatch.setattr(sys, "argv", ["chess-coach", "--db", str(db_path), "inspect-decision", "1"])
    main()
    cli = json.loads(capsys.readouterr().out)
    assert cli[role]["score_value"] is None and cli[role]["wdl"] is None

    app = create_app(
        db_path=db_path,
        subject="learner",
        actor="reviewer",
        corpus="test",
        login="fixture",
        origin="https://coach.invalid",
    )
    page = app.test_client().get(
        "/decisions/1",
        base_url="https://coach.invalid",
        headers={"Tailscale-User-Login": "fixture"},
    )
    assert page.status_code == 200
    assert b"987654" not in page.data and b"777, 111, 112" not in page.data
    assert b"Status: unavailable. Score: unavailable" in page.data
    assert b"Status: limited. Score: cp 42" in page.data
