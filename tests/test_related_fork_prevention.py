"""Synthetic operation-matched anchored fork-prevention transfer."""

import json

import chess
import pytest

from chess_coach.fork_defense_detector import process_decision
from chess_coach.related_fork_prevention import preview, selection
from chess_coach.related_fork_prevention_start import start_related
from chess_coach.unified_session_events import show, submit
from tests.related_protection_support import learning_counts
from tests.test_fork_defense import mirror
from tests.test_fork_defense_pipeline import LEARNER, make_game
from tests.transfer_concealment_support import preview_text

PRE = "7k/8/6p1/8/1n6/8/7P/R3K3 b - - 0 1"


def source_and_corpus(path, monkeypatch, *, black=False, failure=False):
    db, _config = make_game(path, monkeypatch, black=black, failure=failure)
    evidence = process_decision(db, 1, LEARNER)["evidence_ids"][0]
    board = chess.Board(PRE)
    if black:
        board = board.mirror()
    db.connection.execute(
        "INSERT INTO puzzle_corpora(version,source,checksum,state) VALUES('test','fixture','checksum','staging')"
    )
    corpus = db.connection.execute("SELECT id FROM puzzle_corpora WHERE version='test'").fetchone()[
        0
    ]
    moves = ["g6g5", "a1b1", "h8g8", "e1f1"]
    if black:
        moves = [mirror(move) for move in moves]
    db.connection.execute(
        """INSERT INTO puzzles(puzzle_id,corpus_id,fen,source,solution,rating,rating_deviation,themes_json,objective)
        VALUES('fixture',?,?,'https://example.invalid',?,1200,80,'["fork"]','unknown')""",
        (corpus, board.fen(), " ".join(moves)),
    )
    db.connection.execute("INSERT INTO puzzle_themes VALUES(?,?,'fork',1200)", (corpus, "fixture"))
    db.connection.execute("UPDATE puzzle_corpora SET state='ready' WHERE id=?", (corpus,))
    db.connection.commit()
    return db, evidence


@pytest.mark.parametrize("black", [False, True])
@pytest.mark.parametrize("failure", [False, True])
def test_anchored_defense_reaches_playable_source_bound_session(
    tmp_path, monkeypatch, black, failure
):
    db, evidence = source_and_corpus(
        tmp_path / "fork-prevention.sqlite", monkeypatch, black=black, failure=failure
    )
    result = preview(db, LEARNER, evidence, "test")
    assert result["status"] == "available"
    assert len(result["items"]) == 1
    assert result["source_outcome"] == ("failure" if failure else "success")
    assert result["review_status"] == "unreviewed"
    before = learning_counts(db)
    item = result["items"][0]
    move = mirror("a1b1") if black else "a1b1"
    assert move not in preview_text(result, selection(db, LEARNER, evidence, "test"))
    state = start_related(
        db,
        attempt_id="synthetic",
        subject=LEARNER,
        evidence_id=evidence,
        corpus_version="test",
        reference=item["reference"],
    )
    assert state["related_fork_prevention"] is True
    response = submit(db, "synthetic", LEARNER, event_id="answer", move=move)
    assert response["feedback"] == "line_match"
    assert show(db, "synthetic", LEARNER)["status"] == "active"
    assert learning_counts(db) == before
    binding = json.loads(
        db.connection.execute(
            "SELECT provenance_json FROM unified_sessions WHERE attempt_id=?", ("synthetic",)
        ).fetchone()[0]
    )["related_fork_prevention"]
    assert binding["operation"] == "prevent"
    assert binding["threat_origin"] == "positional_before_played"
    assert binding["pattern_cued"] is True
    db.close()


def test_unlisted_legal_defense_requires_verification_without_learning(tmp_path, monkeypatch):
    db, evidence = source_and_corpus(tmp_path / "unlisted.sqlite", monkeypatch)
    item = preview(db, LEARNER, evidence, "test")["items"][0]
    before = learning_counts(db)
    start_related(
        db,
        attempt_id="unlisted",
        subject=LEARNER,
        evidence_id=evidence,
        corpus_version="test",
        reference=item["reference"],
    )
    result = submit(db, "unlisted", LEARNER, event_id="other", move="h2h3")
    assert result["status"] == "needs_verification"
    assert result["feedback"] == "needs_verification"
    assert learning_counts(db) == before
    db.close()
