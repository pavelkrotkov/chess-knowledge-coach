from __future__ import annotations

import chess
import pytest

from chess_coach.db import Database
from chess_coach.ingest import ingest_pgn
from chess_coach.learner_context import decision_contexts

PGN = """[Event "Example"]
[Site "https://lichess.org/abcd1234"]
[GameId "abcd1234"]
[White "StudyPlayer"]
[Black "OtherPlayer"]
[Result "1-0"]
[UTCDate "2026.08.11"]
[UTCTime "12:30:45"]
[TimeControl "180+2"]
[WhiteElo "1500"]
[BlackElo "1400"]

1. e4 {[%clk 0:02:59]} e5 {[%clk 0:02:56]} 2. Nf3 {[%clk 0:02:58]} Nc6 {[%clk 0:02:55]} 1-0
"""
CUSTOM = """[Event "Custom"]
[White "OtherPlayer"]
[Black "StudyPlayer"]
[Result "*"]
[SetUp "1"]
[FEN "8/8/8/8/8/5k2/8/4K3 b - - 0 1"]

1... Kf4 2. Kd2 *
"""


def database(pgn: str = PGN, source: str = "lichess") -> Database:
    db = Database(":memory:")
    db.initialize()
    ingest_pgn(db, pgn, source=source)
    return db


def test_white_learner_only_matches_own_moves_and_preserves_context():
    db = database()
    rows = list(decision_contexts(db, 1, learner="  STUDYplayer "))
    assert [row["subject"] for row in rows] == ["studyplayer", None, "studyplayer", None]
    assert [row["mover"] for row in rows] == ["white", "black", "white", "black"]
    assert all(row["learner_color"] == "white" for row in rows)
    assert all(row["source"] == "lichess" and row["source_id"] == "abcd1234" for row in rows)
    assert rows[0]["pre_move_fen"] == chess.Board().fen()
    assert rows[0]["played_move"] == "e2e4"
    assert rows[0]["observation_at"] == "2026-08-11T12:30:45+00:00"
    assert rows[0]["observation_precision"] == "game_start"
    assert rows[0]["processed_at"] != rows[0]["observation_at"]
    assert [row["clock_before_seconds"] for row in rows] == [None, None, 179, 176]
    assert [row["clock_after_seconds"] for row in rows] == [179, 176, 178, 175]
    assert rows[0]["time_control"] == "180+2"
    assert (rows[0]["mover_rating"], rows[0]["other_rating"]) == (1500, 1400)
    assert (rows[1]["mover_rating"], rows[1]["other_rating"]) == (1400, 1500)


def test_black_learner_custom_start_and_unknown_time():
    db = database(CUSTOM, source="local")
    rows = list(decision_contexts(db, 1, learner="STUDYPLAYER"))
    assert [row["subject"] for row in rows] == ["studyplayer", None]
    assert rows[0]["learner_color"] == "black"
    assert rows[0]["mover"] == "black"
    assert rows[0]["pre_move_fen"] == "8/8/8/8/8/5k2/8/4K3 b - - 0 1"
    assert rows[0]["played_move"] == "f3f4"
    assert all(row["observation_at"] is None for row in rows)
    assert all(row["observation_precision"] is None for row in rows)
    assert all(row["clock_before_seconds"] is None for row in rows)
    assert all(row["mover_rating"] is None for row in rows)


@pytest.mark.parametrize("learner", [None, "", "?", "-", "default", "unrelated"])
def test_unknown_or_mismatched_learner_never_gets_credit(learner):
    rows = list(decision_contexts(database(), 1, learner=learner))
    assert all(row["subject"] is None and row["learner_color"] is None for row in rows)


def test_duplicate_player_names_are_ambiguous():
    ambiguous = PGN.replace('[Black "OtherPlayer"]', '[Black "STUDYPLAYER"]')
    rows = list(decision_contexts(database(ambiguous), 1, learner="studyplayer"))
    assert all(row["subject"] is None and row["learner_color"] is None for row in rows)


@pytest.mark.parametrize(
    "pgn",
    [
        PGN.replace('[UTCTime "12:30:45"]\n', ""),
        PGN.replace('[UTCDate "2026.08.11"]', '[UTCDate "????.??.??"]'),
        PGN.replace('[UTCDate "2026.08.11"]', '[Date "2026.08.11"]'),
    ],
)
def test_incomplete_or_non_utc_date_remains_unknown(pgn):
    rows = list(decision_contexts(database(pgn), 1, learner="studyplayer"))
    assert all(row["observation_at"] is None for row in rows)
    assert all(row["observation_precision"] is None for row in rows)
    assert all(row["processed_at"] for row in rows)


def test_unknown_game_id_is_rejected():
    with pytest.raises(ValueError, match="unknown game id"):
        list(decision_contexts(database(), 999, learner="studyplayer"))


def test_invalid_raw_game_does_not_log_player_names(caplog):
    db = database()
    bad = PGN.replace("2. Nf3", "2. Ke3")
    db.connection.execute("UPDATE games SET pgn = ? WHERE id = 1", (bad,))
    db.connection.commit()
    with caplog.at_level("ERROR", logger="chess.pgn"), pytest.raises(ValueError):
        list(decision_contexts(db, 1, learner="studyplayer"))
    assert "StudyPlayer" not in caplog.text
    assert "OtherPlayer" not in caplog.text


def test_missing_player_identity_does_not_match_unknown():
    pgn = PGN.replace('[White "StudyPlayer"]', '[White "?"]')
    rows = list(decision_contexts(database(pgn), 1, learner="studyplayer"))
    assert all(row["subject"] is None and row["learner_color"] is None for row in rows)


def test_inconsistent_stored_player_metadata_is_unassigned():
    db = database()
    db.connection.execute("UPDATE games SET white = 'DifferentPlayer' WHERE id = 1")
    db.connection.commit()
    rows = list(decision_contexts(db, 1, learner="DifferentPlayer"))
    assert all(row["subject"] is None and row["learner_color"] is None for row in rows)


def test_missing_previous_clock_does_not_borrow_opponent_clock():
    pgn = PGN.replace(" {[%clk 0:02:59]}", "")
    rows = list(decision_contexts(database(pgn), 1, learner="studyplayer"))
    assert rows[2]["clock_before_seconds"] is None
    assert rows[3]["clock_before_seconds"] == 176
