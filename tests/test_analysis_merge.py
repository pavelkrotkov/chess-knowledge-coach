import pytest

from chess_coach.analysis import merge_analysis_outputs
from chess_coach.db import Database


def test_merge_missing_later_position_rolls_back_all_insertions() -> None:
    source = Database(":memory:")
    target = Database(":memory:")
    for db in (source, target):
        db.initialize()
        db.connection.execute(
            "INSERT INTO games (source, source_id, pgn, white, black, result) "
            "VALUES ('test', 'game', 'pgn', 'A', 'B', '*')"
        )
        db.connection.execute(
            "INSERT INTO positions (game_id, ply, fen, san, uci) VALUES (1, 1, 'fen1', 'e4', 'e2e4')"
        )
        db.connection.commit()
    source.connection.execute(
        "INSERT INTO positions (game_id, ply, fen, san, uci) VALUES (1, 2, 'fen2', 'e5', 'e7e5')"
    )
    source.connection.execute(
        "INSERT INTO analysis_runs (game_id, engine, engine_version, config_json) "
        "VALUES (1, 'test', 'v1', '{}')"
    )
    source.connection.executemany(
        "INSERT INTO engine_outputs (run_id, position_id, score_cp) VALUES (1, ?, ?)",
        [(1, 10), (2, 20)],
    )
    source.connection.commit()
    # A pre-profile source has no compatibility view and remains importable.
    source.connection.execute("DROP VIEW analysis_runs_read")
    source.connection.execute("PRAGMA user_version=32")
    source.connection.commit()

    with pytest.raises(ValueError, match="missing ply 2"):
        merge_analysis_outputs(target, source)

    assert target.connection.execute("SELECT COUNT(*) FROM analysis_runs").fetchone()[0] == 0
    assert target.connection.execute("SELECT COUNT(*) FROM engine_outputs").fetchone()[0] == 0
    target.connection.commit()
    assert target.connection.execute("SELECT COUNT(*) FROM analysis_runs").fetchone()[0] == 0
    target.connection.execute(
        "INSERT INTO positions (game_id,ply,fen,san,uci) VALUES(1,2,'fen2','e5','e7e5')"
    )
    target.connection.commit()
    assert merge_analysis_outputs(target, source) == 2
    assert (
        target.connection.execute("SELECT config_json FROM analysis_runs_read").fetchone()[0]
        == "{}"
    )
