from chess_coach.db import Database
from chess_coach.puzzles import import_puzzles, query_puzzles


def test_streaming_puzzle_import_is_versioned_and_queryable(tmp_path) -> None:
    source = tmp_path / "puzzles.csv"
    source.write_text(
        "PuzzleId,FEN,Moves,Rating,RatingDeviation,Themes,GameUrl,OpeningTags\n"
        "p1,fen1,e2e4 e7e5,1200,80,fork middlegame,https://lichess.org/game1,Italian_Game\n"
        "p2,fen2,d2d4 d7d5,1800,60,backRankMate endgame,https://lichess.org/game2,Queen's_Gambit\n",
        encoding="utf-8",
    )
    db = Database(":memory:")
    db.initialize()

    assert import_puzzles(db, source, version="2026-01", batch_size=1) == 2
    assert import_puzzles(db, source, version="2026-01", batch_size=1) == 2
    rows = query_puzzles(db, version="2026-01", theme="fork", min_rating=1000, max_rating=1500)

    assert rows == [
        {
            "puzzle_id": "p1",
            "rating": 1200,
            "rating_deviation": 80,
            "themes": ["fork", "middlegame"],
            "opening": "Italian_Game",
            "objective": "execute",
        }
    ]
    stored = db.connection.execute(
        "SELECT source, solution FROM puzzles WHERE puzzle_id = 'p1'"
    ).fetchone()
    assert tuple(stored) == ("https://lichess.org/game1", "e2e4 e7e5")


def test_failed_reimport_preserves_existing_corpus_rows(tmp_path) -> None:
    good = tmp_path / "good.csv"
    good.write_text(
        "PuzzleId,FEN,Moves,Rating,RatingDeviation,Themes,GameUrl,OpeningTags\n"
        "p1,fen1,e2e4 e7e5,1200,80,fork middlegame,,\n",
        encoding="utf-8",
    )
    bad = tmp_path / "bad.csv"
    bad.write_text(
        "PuzzleId,FEN,Moves,Rating,RatingDeviation,Themes,GameUrl,OpeningTags\n"
        "p1,fen1,e2e4 e7e5,1200,80,fork middlegame,,\n"
        "p2,,d2d4 d7d5,1800,60,endgame,,\n",
        encoding="utf-8",
    )
    db = Database(":memory:")
    db.initialize()
    assert import_puzzles(db, good, version="v") == 1

    try:
        import_puzzles(db, bad, version="v")
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError for malformed re-import")

    # The original corpus rows survive the failed re-import.
    assert db.connection.execute("SELECT count(*) FROM puzzles").fetchone()[0] == 1
    assert (
        db.connection.execute(
            "SELECT imported_rows FROM puzzle_corpora WHERE version = 'v'"
        ).fetchone()["imported_rows"]
        == 1
    )


def test_empty_rating_cell_is_rejected(tmp_path) -> None:
    source = tmp_path / "empty_rating.csv"
    source.write_text(
        "PuzzleId,FEN,Moves,Rating,RatingDeviation,Themes,GameUrl,OpeningTags\n"
        "p1,fen1,e2e4 e7e5,,80,fork,,\n",
        encoding="utf-8",
    )
    db = Database(":memory:")
    db.initialize()
    try:
        import_puzzles(db, source, version="v")
    except ValueError as exc:
        assert "Rating" in str(exc)
    else:
        raise AssertionError("expected ValueError for empty rating")
