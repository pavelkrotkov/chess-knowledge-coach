import pytest

from chess_coach.analysis import analyze_game, detect_compatibility
from chess_coach.db import Database


def test_detect_compatibility_reports_x64_and_popcnt(monkeypatch):
    monkeypatch.setattr("platform.machine", lambda: "x86_64")
    monkeypatch.setattr("chess_coach.analysis._cpu_flags", lambda: {"popcnt", "sse4_2"})

    assert detect_compatibility()["generic_x64"] is True
    assert detect_compatibility()["popcnt"] is True


def test_analyze_game_fails_clearly_for_missing_engine(tmp_path):
    db = Database(tmp_path / "coach.sqlite")
    db.initialize()

    with pytest.raises(RuntimeError, match="engine binary"):
        analyze_game(db, 1, engine_path=str(tmp_path / "missing-stockfish"))


def test_analysis_schema_contains_provenance_columns():
    db = Database(":memory:")
    db.initialize()
    columns = {row[1] for row in db.connection.execute("PRAGMA table_info(analysis_runs)")}

    assert {"binary_path", "binary_version", "nnue", "compatibility_json"}.issubset(columns)
    output_columns = {row[1] for row in db.connection.execute("PRAGMA table_info(engine_outputs)")}
    assert "multipv" in output_columns
