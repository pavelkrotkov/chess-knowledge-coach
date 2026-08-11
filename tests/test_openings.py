from chess_coach.db import Database
from chess_coach.ingest import ingest_pgn
from chess_coach.openings import classify_game, import_openings

PGN = """[Event "Test"]
[White "A"]
[Black "B"]
[Result "*"]

1. d4 d5 2. Nf3 Nf6 *
"""


def test_opening_import_classifies_transposition(tmp_path) -> None:
    dataset = tmp_path / "openings.tsv"
    dataset.write_text(
        "eco\tname\tmoves\nD00\tQueen's Pawn\td4 d5 Nf3 Nf6\n"
        "A00\tTransposed Queen's Pawn\tNf3 Nf6 d4 d5\n",
        encoding="utf-8",
    )
    db = Database(":memory:")
    db.initialize()
    ingest_pgn(db, PGN)
    game_id = db.connection.execute("SELECT id FROM games").fetchone()[0]

    assert import_openings(db, dataset, version="test-1", source_url="cc0://test") == 2
    result = classify_game(db, game_id, version="test-1", source_url="cc0://test")

    assert result["matched"] is True
    assert result["confidence"] == 1.0
    assert result["name"] in {"Queen's Pawn", "Transposed Queen's Pawn"}
    assert db.connection.execute("SELECT COUNT(*) FROM opening_edges").fetchone()[0] >= 4


def test_unknown_position_is_reported_without_annotation(tmp_path) -> None:
    dataset = tmp_path / "openings.tsv"
    dataset.write_text("eco\tname\tmoves\nC20\tOpen Game\te4 e5\n", encoding="utf-8")
    db = Database(":memory:")
    db.initialize()
    ingest_pgn(db, PGN)
    game_id = db.connection.execute("SELECT id FROM games").fetchone()[0]

    import_openings(db, dataset, version="test-1", source_url="cc0://test")
    result = classify_game(db, game_id, version="test-1", source_url="cc0://test")

    assert result == {"matched": False, "confidence": 0.0}


def test_pgn_rows_and_reimport_are_supported(tmp_path) -> None:
    dataset = tmp_path / "openings.tsv"
    dataset.write_text("eco\tname\tpgn\nC20\tOpen Game\t1. e4 e5\n", encoding="utf-8")
    db = Database(":memory:")
    db.initialize()

    assert import_openings(db, dataset, version="test-1", source_url="cc0://test") == 1
    assert import_openings(db, dataset, version="test-1", source_url="cc0://test") == 1
    assert db.connection.execute("SELECT COUNT(*) FROM opening_datasets").fetchone()[0] == 1


def test_invalid_dataset_rolls_back(tmp_path) -> None:
    dataset = tmp_path / "bad.tsv"
    dataset.write_text("eco\tname\tmoves\nC20\tBad\te4 not-a-move\n", encoding="utf-8")
    db = Database(":memory:")
    db.initialize()

    import pytest

    with pytest.raises(ValueError):
        import_openings(db, dataset, version="bad", source_url="cc0://bad")
    assert db.connection.execute("SELECT COUNT(*) FROM opening_datasets").fetchone()[0] == 0


def test_unknown_game_id_is_rejected() -> None:
    db = Database(":memory:")
    db.initialize()

    import pytest

    with pytest.raises(ValueError, match="unknown game id"):
        classify_game(db, 999, version="test-1", source_url="cc0://test")
