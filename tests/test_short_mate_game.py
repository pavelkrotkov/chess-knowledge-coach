"""Single-game short-mate inspection preserves proof and coverage limits."""

import chess
import pytest

from chess_coach.db import Database
from chess_coach.ingest import ingest_pgn
from chess_coach.short_mate_game_proof import classify
from chess_coach.short_mate_game_report import report
from chess_coach.short_mate_game_source import prepare, recheck
from tests.test_mate_proof import FEN

SHORT = "6k1/5ppp/8/7Q/8/5R2/7r/K4R2 w - - 0 1"


@pytest.mark.parametrize(("move", "outcome"), [("a1b1", "missed"), ("h5f7", "preserved")])
def test_played_short_mate_outcomes_and_limits(monkeypatch, move, outcome):
    board = chess.Board(SHORT)
    assert classify(board, move, 1, lambda: 0) == (outcome, None)
    assert board.fen() == SHORT
    immediate = chess.Board(FEN)
    assert classify(immediate, "g6g1", 1, lambda: 0) == ("immediate", None)
    invalid = chess.Board("8/8/8/8/8/8/8/K7 w - - 0 1")
    assert classify(invalid, move, 1, lambda: 0) == ("unknown", "invalid_position")
    unknown_history = chess.Board(SHORT.replace("0 1", "8 1"))
    assert classify(unknown_history, move, 1, lambda: 0) == ("unknown", "history_unavailable")
    monkeypatch.setattr("chess_coach.short_mate_game_budget.MAX_NODES", 1)
    assert classify(board, move, 1, lambda: 0) == ("unknown", "node_limit")


def pgn(move):
    return f'''[Event "Synthetic"]
[White "fixture_a"]
[Black "fixture_b"]
[UTCDate "2026.01.01"]
[UTCTime "12:00:00"]
[SetUp "1"]
[FEN "{SHORT}"]
[Result "1-0"]

1. {move} 1-0
'''


def test_game_report_is_read_only_bounded_and_rechecks_source(tmp_path, monkeypatch):
    import chess_coach.web_short_mate_game as web_short_mate_game
    from chess_coach.web import create_app

    db = Database(tmp_path / "games.sqlite")
    db.initialize()
    ingest_pgn(db, pgn("Kb1"))
    db.connection.execute("BEGIN")
    with pytest.raises(ValueError, match="idle"):
        report(db, "fixture_a", 1, seconds=1, clock=lambda: 0)
    db.connection.rollback()
    before = db.connection.total_changes
    result = report(db, "fixture_a", 1, seconds=1, clock=lambda: 0)
    assert db.connection.total_changes == before
    assert result["eligible"] == result["checked"] == 1
    assert result["opportunities"] == result["missed"] == 1
    assert result["complete"] and result["unknown"] == result["unchecked"] == 0
    ticks = iter([0, 0, 0.1, 0.2])
    partial = report(db, "fixture_a", 1, seconds=1, clock=lambda: next(ticks, 2))
    assert not partial["complete"] and partial["unknown"] == 1
    assert partial["reasons"] == {"deadline": 1}
    app = create_app(
        db_path=tmp_path / "games.sqlite",
        subject="fixture_a",
        actor="fixture",
        corpus="test",
        login="fixture",
        origin="https://coach.invalid",
    )
    client = app.test_client()
    headers = {"Tailscale-User-Login": "fixture"}
    monkeypatch.setattr(
        web_short_mate_game,
        "report",
        lambda db, learner, game_id: report(db, learner, game_id, seconds=1, clock=lambda: 0),
    )
    page = client.get("/games/1/short-mate", base_url="https://coach.invalid", headers=headers)
    assert b"Miss rate: 100.0%" in page.data

    def partial_report(db, learner, game_id):
        ticks = iter([0, 0, 0.1, 0.2])
        return report(db, learner, game_id, seconds=1, clock=lambda: next(ticks, 2))

    monkeypatch.setattr(web_short_mate_game, "report", partial_report)
    page = client.get("/games/1/short-mate", base_url="https://coach.invalid", headers=headers)
    assert b"Coverage is incomplete" in page.data and b"Miss rate:" not in page.data
    assert b"/decisions/" in page.data
    with pytest.raises(ValueError):
        report(db, "fixture_c", 1, seconds=1, clock=lambda: 0)
    source = prepare(db, "fixture_a", 1)
    db.connection.execute("UPDATE games SET result='0-1' WHERE id=1")
    db.connection.commit()
    with pytest.raises(ValueError, match="changed"):
        recheck(db, "fixture_a", source)
    db.close()


def test_proved_opportunity_with_unresolved_play_does_not_get_rate(monkeypatch):
    from chess_coach.short_mate_game_counts import add, empty, finish

    statuses = iter(["unknown", "proved"])
    monkeypatch.setattr(
        "chess_coach.short_mate_game_budget._root",
        lambda *_: {"status": next(statuses)},
    )
    board = chess.Board(SHORT)
    outcome, reason = classify(board, "a1b1", 1, lambda: 0)
    assert (outcome, reason) == ("opportunity_unresolved", "played_move_unresolved")
    counts = empty(1)
    add(counts, {"position_id": 1}, outcome, reason)
    result = finish(counts)
    assert result["opportunities"] == result["opportunity_unresolved"] == 1
    assert result["checked"] == result["unknown"] == result["unchecked"] == 0
    assert not result["complete"]


def test_deadline_interrupts_inside_root_proof():
    calls = 0

    def clock():
        nonlocal calls
        calls += 1
        return 0 if calls <= 80 else 2

    board = chess.Board(SHORT)
    assert classify(board, "a1b1", 1, clock) == ("unknown", "deadline")
    assert calls > 80 and board.fen() == SHORT
