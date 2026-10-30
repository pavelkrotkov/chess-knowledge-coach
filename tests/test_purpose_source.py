"""Synthetic purpose diagnostic coverage."""

import pytest

from chess_coach.purpose_view import show
from chess_coach.purpose_worker import run
from tests.purpose_fixtures import configure, request
from tests.purpose_ordinary_fixture import (
    assert_after_selection,
    assert_no_ordinary_analysis,
    run_ordinary_analysis,
    setup_unanalysed,
)
from tests.purpose_search_checks import install_repeated_history
from tests.purpose_stale_checks import assert_stale_attempt
from tests.test_deep_selection import LEARNER, PGN, setup_game


def test_repeated_history_is_rejected_before_engine(tmp_path, monkeypatch):
    install_repeated_history(monkeypatch)
    db = setup_game(tmp_path / "repeat.sqlite", monkeypatch)
    with pytest.raises(ValueError, match="draw-sensitive"):
        request(db, 5)
    assert (
        db.connection.execute("SELECT COUNT(*) FROM purpose_analysis_requests").fetchone()[0] == 0
    )


@pytest.mark.parametrize("change", ["position", "ownership"])
def test_position_or_ownership_change_makes_diagnostic_stale(tmp_path, monkeypatch, change):
    db = setup_game(tmp_path / f"{change}-stale.sqlite", monkeypatch)
    request_id = request(db)
    configure(monkeypatch, db)
    assert run(db, request_id, LEARNER)["status"] == "complete"
    if change == "position":
        db.connection.execute("UPDATE positions SET fen=fen || ? WHERE id=1", (" ",))
    else:
        db.connection.execute("UPDATE games SET white=? WHERE id=1", ("different",))
    db.connection.commit()
    assert_stale_attempt(db, request_id, "complete", "comparable")


def test_purpose_request_works_before_ordinary_analysis_and_survives_it(tmp_path, monkeypatch):
    db = setup_unanalysed(tmp_path / "unanalysed.sqlite", PGN)
    request_id = request(db)
    configure(monkeypatch, db)
    assert run(db, request_id, LEARNER)["status"] == "complete"
    before = show(db, request_id, LEARNER)
    assert_no_ordinary_analysis(db)
    assert run_ordinary_analysis(db, monkeypatch)["status"] == "complete"
    assert show(db, request_id, LEARNER) == before
    assert_after_selection(db, request_id, before)
