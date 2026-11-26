"""Rebind one worker-certified owned capture without repeating proof."""

import chess

from .capture_certificate_producer import identity
from .capture_certificate_store import load, location
from .material_opportunity_current import _qualify, _same_source
from .material_reply_guard import MAX_REPLIES
from .material_source import prepare
from .material_source_marker import source_marker
from .objective_capture_contract import TARGET_VERSION
from .objective_capture_judge import VERSION as JUDGE_VERSION
from .objective_capture_snapshot import _snapshot
from .objective_short_history import history_hash
from .opening_study_source import fingerprint
from .pawn_scope import history_known
from .unified_own_game_evidence import _review


# The retained verifier result must describe this exact original legal history.
def _proof(board, view, review, evidence_id, entry):
    move = board.parse_uci(view["objective_witness"]["uci"][0])
    after = board.copy(stack=True)
    after.push(move)
    expected = {
        "status": "correct",
        "reason": "bounded_capture_proved",
        "verifier": JUDGE_VERSION,
        "history_hash": history_hash(board),
        "move": move.uci(),
        "san": board.san(move),
        "proven_gain_floor": 3,
        "legal_replies": sorted(item.uci() for item in after.legal_moves),
        "limits": {"plies": 2, "reply_limit": MAX_REPLIES, "compute_timeout_seconds": 5.0},
    }
    proof = entry["proof"]
    return (
        entry["snapshot"] == _snapshot(board, view, review, evidence_id, TARGET_VERSION)
        and all(proof.get(key) == value for key, value in expected.items())
        and proof["exchange_gain"] >= 3
        and board.is_capture(move)
        and move.to_square == chess.parse_square(view["objective"]["target"])
    )


def _entry(db, subject, evidence, fact, source):
    if evidence["lifecycle_status"] != "active" or fact["detector_status"] != "active":
        return None
    root = db.capture_root
    path = location(db, root, subject)
    if path is None:
        return None
    # The worker can atomically replace this file while a request is reading it.
    before = fingerprint([path])
    data = load(db, root, subject)
    entry = data["certificates"].get(str(evidence["id"])) if data else None
    if entry is None:
        return None
    review = _review(db, evidence["id"])
    if entry["input"] != identity(evidence, fact, source, review):
        return None
    return path, before, entry, review


def _source_valid(prepared, source):
    board = prepared["board"]
    return _same_source(prepared, source) and board.is_valid() and history_known(board)


def _apply(db, subject, evidence, fact, source, result, history, check):
    binding = _entry(db, subject, evidence, fact, source)
    if binding is None:
        return
    path, before, entry, review = binding
    prepared = prepare(db, evidence["position_id"], subject, history=history)
    check()
    if not _source_valid(prepared, source):
        return
    result["currentness"] = "current"
    result["learner_color"] = prepared["context"]["learner_color"]
    result["decision_fen"] = prepared["context"]["pre_move_fen"]
    result["objective_witness"] = entry["witness"]
    _qualify(result, evidence, entry["witness"])
    # Review or analysis can change without advancing the curriculum revision.
    if (
        not result["eligible_for_exercise_candidate"]
        or not _proof(prepared["board"], result, review, evidence["id"], entry)
        or source_marker(db, evidence["position_id"], evidence["game_id"], subject)
        != prepared["source_marker"]
        or fingerprint([path]) != before
    ):
        raise ValueError("capture certificate changed")


def apply(db, subject, evidence, fact, source, result, history=None, *, check=None):
    try:
        _apply(db, subject, evidence, fact, source, result, history, check or (lambda: None))
    except (ValueError, TypeError, KeyError, IndexError, AttributeError):
        result["currentness"] = "stale"
        result["eligible_for_exercise_candidate"] = False
        result["objective_witness"] = None
