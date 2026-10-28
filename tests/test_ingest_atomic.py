from __future__ import annotations

import pytest

from chess_coach import ingest_game
from chess_coach.db import Database
from chess_coach.ingest import ingest_pgn

PGN = """[Event "Test"]
[Site "https://lichess.org/abc12345"]
[GameId "abc12345"]
[White "A"]
[Black "B"]
[Result "1-0"]

1. e4 e5 2. Nf3 1-0
"""


def database() -> Database:
    db = Database(":memory:")
    db.initialize()
    return db


def test_identical_replay_counts_only_new_records_and_preserves_raw_pgn() -> None:
    db = database()
    assert ingest_pgn(db, PGN, source="lichess", raw_pgn_override=PGN) == {
        "games": 1,
        "positions": 3,
    }
    before = [tuple(row) for row in db.connection.execute("SELECT * FROM positions ORDER BY ply")]
    assert ingest_pgn(db, PGN, source="lichess", raw_pgn_override=PGN) == {
        "games": 0,
        "positions": 0,
    }
    assert db.connection.execute("SELECT pgn, source_id FROM games").fetchone()[:] == (
        PGN,
        "abc12345",
    )
    assert [
        tuple(row) for row in db.connection.execute("SELECT * FROM positions ORDER BY ply")
    ] == before


def test_conflicting_stable_id_does_not_change_original() -> None:
    db = database()
    ingest_pgn(db, PGN, source="lichess", raw_pgn_override=PGN)
    before = [tuple(row) for row in db.connection.execute("SELECT * FROM positions ORDER BY ply")]
    changed = PGN.replace("2. Nf3", "2. Bc4")
    with pytest.raises(ValueError, match="conflicting PGN"):
        ingest_pgn(db, changed, source="lichess", raw_pgn_override=changed)
    assert db.connection.execute("SELECT pgn FROM games").fetchone()[0] == PGN
    assert [
        tuple(row) for row in db.connection.execute("SELECT * FROM positions ORDER BY ply")
    ] == before


def test_bad_later_game_rolls_back_whole_import() -> None:
    db = database()
    valid = PGN.replace("abc12345", "abc12346")
    invalid = PGN.replace("2. Nf3", "2. Ke3")
    with pytest.raises(ValueError, match="invalid PGN"):
        ingest_pgn(db, valid + "\n" + invalid, source="lichess")
    assert not db.connection.in_transaction
    db.connection.execute(
        "INSERT INTO games (pgn, white, black, result) VALUES ('later', 'A', 'B', '*')"
    )
    db.connection.commit()
    assert db.connection.execute("SELECT COUNT(*) FROM games").fetchone()[0] == 1
    assert db.connection.execute("SELECT COUNT(*) FROM positions").fetchone()[0] == 0


def test_failure_after_game_insert_cannot_be_committed_later(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = database()

    def fail(*args):
        raise RuntimeError("injected failure")

    monkeypatch.setattr(ingest_game, "store_positions", fail)
    with pytest.raises(RuntimeError, match="injected"):
        ingest_pgn(db, PGN, source="lichess", raw_pgn_override=PGN)
    db.connection.execute(
        "INSERT INTO games (pgn, white, black, result) VALUES ('later', 'A', 'B', '*')"
    )
    db.connection.commit()
    assert db.connection.execute("SELECT pgn FROM games").fetchone()[0] == "later"
    assert db.connection.execute("SELECT COUNT(*) FROM positions").fetchone()[0] == 0


@pytest.mark.parametrize(
    "raw",
    [
        PGN.replace('[Result "1-0"]', '[Result "*"]').replace("Nf3 1-0", "Nf3 *"),
        PGN.replace('[Event "Test"]', '[Event "Test"]\n[Variant "Chess960"]'),
        PGN.removesuffix("1-0\n"),
        PGN.replace("2. Nf3", "2. Qh9"),
        "not a PGN",
    ],
)
def test_invalid_or_unsupported_lichess_input_is_rejected(raw: str) -> None:
    db = database()
    with pytest.raises(ValueError):
        ingest_pgn(db, raw, source="lichess", raw_pgn_override=raw)
    assert db.connection.execute("SELECT COUNT(*) FROM games").fetchone()[0] == 0


def test_raw_override_must_match_one_game() -> None:
    db = database()
    with pytest.raises(ValueError, match="override"):
        ingest_pgn(db, PGN, source="lichess", raw_pgn_override=PGN.replace("Nf3", "Bc4"))
    with pytest.raises(ValueError, match="override"):
        ingest_pgn(db, PGN + "\n" + PGN, source="lichess", raw_pgn_override=PGN)
    assert db.connection.execute("SELECT COUNT(*) FROM games").fetchone()[0] == 0


def test_pgn_variations_comments_and_bom_remain_supported() -> None:
    db = database()
    raw = (
        chr(0xFEFF)
        + """[Event "Example"]
[Result "*"]

1. e4 $1 { comment } (1. d4 d5) e5 2. Nf3!? Nc6 *
"""
    )
    assert ingest_pgn(db, raw) == {"games": 1, "positions": 4}


def test_unrecognized_trailing_text_is_not_silently_ignored() -> None:
    db = database()
    with pytest.raises(ValueError, match="invalid PGN"):
        ingest_pgn(db, PGN + "\nnot-a-game", source="lichess")
    assert db.connection.execute("SELECT COUNT(*) FROM games").fetchone()[0] == 0


@pytest.mark.parametrize("batched", [False, True])
def test_truncated_lichess_record_is_rejected_without_override(batched: bool) -> None:
    db = database()
    incomplete = PGN.removesuffix("1-0\n")
    preceding = PGN.replace("abc12345", "abc12346") + "\n" if batched else ""

    with pytest.raises(ValueError, match="incomplete Lichess game PGN"):
        ingest_pgn(db, preceding + incomplete, source="lichess")

    assert db.connection.execute("SELECT COUNT(*) FROM games").fetchone()[0] == 0
    assert db.connection.execute("SELECT COUNT(*) FROM positions").fetchone()[0] == 0


@pytest.mark.parametrize("bad_override", [False, True])
def test_malformed_pgn_does_not_log_player_headers(caplog, bad_override: bool) -> None:
    db = database()
    good = PGN.replace('[White "A"]', '[White "SyntheticPrivateWhite"]').replace(
        '[Black "B"]', '[Black "SyntheticPrivateBlack"]'
    )
    bad = good.replace("2. Nf3", "2. Ke3")
    source = good if bad_override else bad
    override = bad if bad_override else None

    with caplog.at_level("ERROR", logger="chess.pgn"), pytest.raises(ValueError):
        ingest_pgn(db, source, source="lichess", raw_pgn_override=override)

    assert "SyntheticPrivateWhite" not in caplog.text
    assert "SyntheticPrivateBlack" not in caplog.text
    assert db.connection.execute("SELECT COUNT(*) FROM games").fetchone()[0] == 0


def test_default_storage_is_normalized_but_explicit_override_remains_exact() -> None:
    import io

    import chess.pgn

    no_override, with_override = database(), database()
    ingest_pgn(no_override, PGN, source="lichess")
    ingest_pgn(with_override, PGN, source="lichess", raw_pgn_override=PGN)

    assert no_override.connection.execute("SELECT pgn FROM games").fetchone()[0] == str(
        chess.pgn.read_game(io.StringIO(PGN))
    )
    assert with_override.connection.execute("SELECT pgn FROM games").fetchone()[0] == PGN


@pytest.mark.parametrize("override", [False, True])
@pytest.mark.parametrize(
    "movetext",
    [
        "1. e4 e5 2. Nf3 ; 1-0",
        "1. e4 e5 2. Nf3 0-1 ; 1-0",
        "1. e4 e5 2. Nf3 { 1-0 }",
        "1. e4 (1. d4 { 1-0 }) e5 2. Nf3",
    ],
)
def test_comment_or_variation_result_cannot_complete_lichess_game(movetext, override):
    raw = PGN.replace("1. e4 e5 2. Nf3 1-0", movetext)
    db = database()
    with pytest.raises(ValueError, match="incomplete Lichess game PGN"):
        ingest_pgn(db, raw, source="lichess", raw_pgn_override=raw if override else None)
    assert db.connection.execute("SELECT COUNT(*) FROM games").fetchone()[0] == 0


@pytest.mark.parametrize("override", [False, True])
@pytest.mark.parametrize("tail", [" { final comment }", " ; final comment", "\n% final comment"])
def test_completed_lichess_result_allows_trailing_comments(tail, override):
    raw = PGN.replace("2. Nf3 1-0\n", "2. Nf3 1-0" + tail + "\n")
    db = database()
    assert ingest_pgn(db, raw, source="lichess", raw_pgn_override=raw if override else None) == {
        "games": 1,
        "positions": 3,
    }
    if override:
        assert db.connection.execute("SELECT pgn FROM games").fetchone()[0] == raw


def test_comment_only_result_in_later_game_rolls_back_batch():
    valid = PGN.replace("abc12345", "abc12346")
    incomplete = PGN.replace("2. Nf3 1-0\n", "2. Nf3 ; 1-0")
    db = database()
    with pytest.raises(ValueError, match="incomplete Lichess game PGN"):
        ingest_pgn(db, valid + "\n" + incomplete, source="lichess")
    assert db.connection.execute("SELECT COUNT(*) FROM games").fetchone()[0] == 0
    assert db.connection.execute("SELECT COUNT(*) FROM positions").fetchone()[0] == 0


@pytest.mark.parametrize("override", [False, True])
def test_nested_variations_do_not_hide_mainline_result(override):
    raw = PGN.replace(
        "1. e4 e5 2. Nf3 1-0",
        "1. e4 (1. d4 d5 (1... Nf6)) e5 2. Nf3 1-0 { done }",
    )
    db = database()
    assert ingest_pgn(db, raw, source="lichess", raw_pgn_override=raw if override else None) == {
        "games": 1,
        "positions": 3,
    }
