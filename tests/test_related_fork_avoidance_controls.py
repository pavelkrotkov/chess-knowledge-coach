"""Origin, work-budget, safety and currentness controls for created forks."""

import json

import chess
import pytest

from chess_coach.evidence_review import review_evidence
from chess_coach.fork_defense_probe import hypothetical
from chess_coach.fork_defense_safety import quiet_after, safe_material
from chess_coach.fork_targets import targets
from chess_coach.puzzle_session_validate import validate_line
from chess_coach.related_fork_avoidance import preview
from chess_coach.related_fork_avoidance_alternative import alternative
from chess_coach.related_fork_avoidance_source import source_for_evidence
from chess_coach.related_fork_avoidance_start import start_related
from chess_coach.related_fork_prevention_budget import create
from chess_coach.unified_session_events import show, submit
from tests.related_protection_support import learning_counts
from tests.test_fork_defense_pipeline import LEARNER
from tests.test_related_fork_avoidance import created_fixture
from tests.test_related_fork_prevention import source_and_corpus


def test_preexisting_source_never_enters_created_namespace(tmp_path, monkeypatch):
    db, evidence = source_and_corpus(tmp_path / "preexisting.sqlite", monkeypatch)
    with pytest.raises(ValueError, match="created-by-play"):
        source_for_evidence(db, LEARNER, evidence)
    db.close()


def test_particular_witness_is_bound_but_unlisted_move_remains_unknown(tmp_path, monkeypatch):
    db, evidence = created_fixture(tmp_path / "witness.sqlite", monkeypatch)
    item = preview(db, LEARNER, evidence, "test")["items"][0]
    before = learning_counts(db)
    start_related(
        db,
        attempt_id="witness",
        subject=LEARNER,
        evidence_id=evidence,
        corpus_version="test",
        reference=item["reference"],
    )
    row = db.connection.execute(
        "SELECT provenance_json FROM unified_sessions WHERE attempt_id='witness'"
    ).fetchone()
    binding = json.loads(row[0])["related_fork_avoidance"]
    assert binding["threat_origin"] == "created_by_played_move"
    assert binding["created_witness"]["bad_move"] != "b1b3"
    assert binding["created_witness"]["fork"]["move"]
    event = submit(db, "witness", LEARNER, event_id="other", move="h2h3")
    assert event["status"] == event["feedback"] == "needs_verification"
    assert learning_counts(db) == before
    db.close()


def test_rejected_review_and_changed_filter_stale_active_sessions(tmp_path, monkeypatch):
    from chess_coach import related_fork_avoidance_contract as contract

    db, evidence = created_fixture(tmp_path / "stale.sqlite", monkeypatch)
    item = preview(db, LEARNER, evidence, "test")["items"][0]
    start_related(
        db,
        attempt_id="session",
        subject=LEARNER,
        evidence_id=evidence,
        corpus_version="test",
        reference=item["reference"],
    )
    old_version = contract.FILTER_VERSION
    monkeypatch.setattr(contract, "FILTER_VERSION", "changed-filter")
    with pytest.raises(ValueError, match="stale"):
        show(db, "session", LEARNER)
    monkeypatch.setattr(contract, "FILTER_VERSION", old_version)
    review_evidence(db, evidence, decision="reject", actor="fixture_reviewer")
    with pytest.raises(ValueError, match="stale"):
        show(db, "session", LEARNER)
    with pytest.raises(ValueError):
        preview(db, LEARNER, evidence, "test")
    db.close()


def test_unknown_original_prefilter_and_exhaustion_are_not_positive(tmp_path, monkeypatch):
    from chess_coach import related_fork_avoidance_witness as implementation
    from chess_coach import related_fork_prevention_budget as limits

    db, evidence = created_fixture(tmp_path / "limits.sqlite", monkeypatch)
    monkeypatch.setattr(implementation, "hypothetical", lambda board: None)
    result = preview(db, LEARNER, evidence, "test")
    assert not result["items"] and result["avoidance_scan"]["unknown"] == 1
    monkeypatch.undo()
    monkeypatch.setattr(limits, "ANCHOR_LIMIT", 0)
    result = preview(db, LEARNER, evidence, "test")
    assert not result["items"] and result["avoidance_scan"]["truncated"]
    assert result["avoidance_scan"]["anchors"] == 0
    db.close()


def test_unrelated_immediate_capture_excludes_a_quiet_bad_root(tmp_path, monkeypatch):
    db, evidence = created_fixture(tmp_path / "counterplay.sqlite", monkeypatch)
    source = source_for_evidence(db, LEARNER, evidence)["features"]
    board = chess.Board("7k/8/6p1/8/1n6/8/P6P/rRB1K3 w - - 0 2")
    good, bad = chess.Move.from_uci("b1b3"), chess.Move.from_uci("b1b2")
    after = quiet_after(board, bad)
    assert board.is_valid() and bad in board.legal_moves and after is not None
    shape = targets(after, chess.Move.from_uci("b4d3"))
    assert shape is not None and hypothetical(board) is not None
    assert not safe_material(after)
    budget = create() | {"unknown": 0}
    assert alternative(board, good, bad, hypothetical(board), source, budget) is None
    assert budget["proofs"] == 0
    db.close()


def test_setup_rights_and_unresolved_en_passant_are_preserved():
    from chess_coach.related_fork_prevention_line import root

    fen = "r3k2r/7p/8/8/8/8/7P/R3K2R b KQkq - 0 1"
    prompt = validate_line(fen, "h7h6 e1g1")
    board = root(prompt, ["e1g1"])
    assert board is not None and board.has_kingside_castling_rights(chess.WHITE)
    assert chess.Move.from_uci("e1g1") in board.legal_moves
    ep = chess.Board("7k/8/8/3pP3/8/8/8/7K w - d6 0 1")
    assert hypothetical(ep) is None


def test_source_history_mutation_invalidates_created_session(tmp_path, monkeypatch):
    db, evidence = created_fixture(tmp_path / "history.sqlite", monkeypatch)
    item = preview(db, LEARNER, evidence, "test")["items"][0]
    start_related(
        db,
        attempt_id="history",
        subject=LEARNER,
        evidence_id=evidence,
        corpus_version="test",
        reference=item["reference"],
    )
    db.connection.execute("UPDATE games SET pgn = pgn || '\n{fixture mutation}' WHERE id=1")
    db.connection.commit()
    with pytest.raises(ValueError, match="stale"):
        show(db, "history", LEARNER)
    db.close()


def test_created_pair_identity_does_not_claim_other_forks_absent():
    from chess_coach.related_fork_avoidance_proof import _created

    before = {"b4c2": [chess.A1, chess.E1], "b4d3": [chess.B2, chess.E1]}
    assert not _created(before, {"move": "b4c2", "targets": ["a1", "e1"]})
    assert _created(before, {"move": "b4c2", "targets": ["b2", "e1"]})
    assert _created(before, {"move": "b4a2", "targets": ["c1", "e1"]})


def test_short_supplied_line_with_material_loss_is_unqualified():
    from chess_coach.related_fork_avoidance_line import non_losing

    board = chess.Board("2r1k3/8/8/8/8/8/7P/2BNK3 w - - 0 1")
    assert board.is_valid()
    assert not non_losing(board, ["h2h3", "c8c1"])


def test_same_tag_wrong_defender_and_forcing_bad_move_do_not_match(tmp_path, monkeypatch):
    from chess_coach.related_fork_avoidance_candidate_line import candidate_line
    from tests.test_related_fork_avoidance import PRE

    db, evidence = created_fixture(tmp_path / "wrong-role.sqlite", monkeypatch)
    source = source_for_evidence(db, LEARNER, evidence)["features"]
    prompt = validate_line(PRE, "g7g6 b1b3 h8g8 e1f1")
    budget = create() | {"unknown": 0}
    assert candidate_line(prompt, ["h2h3", "h8g8"], source, budget) is None
    board = chess.Board(prompt)
    forcing = chess.Move.from_uci("b1b4")
    assert forcing in board.legal_moves and board.is_capture(forcing)
    budget = create() | {"unknown": 0}
    assert (
        alternative(
            board, chess.Move.from_uci("b1b3"), forcing, hypothetical(board), source, budget
        )
        is None
    )
    assert budget["proofs"] == 0
    db.close()
