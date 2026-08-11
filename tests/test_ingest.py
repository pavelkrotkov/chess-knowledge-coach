from chess_coach.db import Database
from chess_coach.ingest import ingest_pgn

PGN = """[Event "Test"]
[Site "Local"]
[Date "2026.01.01"]
[Round "1"]
[White "Alice"]
[Black "Bob"]
[Result "1-0"]
[TimeControl "300+3"]
[WhiteElo "1500"]
[BlackElo "1450"]

1. e4 {[%clk 0:05:00]} e5 {[%clk 0:05:00]} 2. Nf3 {[%clk 0:04:58]} Nc6 {[%clk 0:04:59]} 1-0
"""


def test_ingest_preserves_game_metadata_moves_and_clocks(tmp_path):
    db = Database(tmp_path / "coach.sqlite")
    db.initialize()

    result = ingest_pgn(db, PGN)

    assert result == {"games": 1, "positions": 4}
    game = db.connection.execute("SELECT white, black, result, time_control FROM games").fetchone()
    assert tuple(game) == ("Alice", "Bob", "1-0", "300+3")
    moves = db.connection.execute(
        "SELECT ply, san, clock_seconds FROM positions ORDER BY ply"
    ).fetchall()
    assert [tuple(row) for row in moves] == [
        (1, "e4", 300.0),
        (2, "e5", 300.0),
        (3, "Nf3", 298.0),
        (4, "Nc6", 299.0),
    ]
