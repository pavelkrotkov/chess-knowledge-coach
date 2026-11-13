"""Build a current teaching context without certifying its owned move."""

from .decision_history import decision_board
from .mate_inspection_source import position_row
from .objective_capture_current import current
from .objective_protection_before import probe
from .objective_protection_snapshot import _check_recorded_target
from .pawn_scope import history_known
from .related_capture_position import _features
from .related_capture_source import _opening
from .related_protection_mechanism import mechanism
from .unified_sources import resolve_source

VERSION = "protection-course-transfer-v1"
PER_BAND = 200


class ContextUnavailable(ValueError):
    """The current source does not establish the supported teaching context."""


def source(db, subject, choice):
    evidence = choice["evidence_id"]
    before, review = current(db, evidence, subject, kind="material_protection", operation="prevent")
    snapshot = resolve_source(db, "own-game", choice["version"], choice["key"], subject=subject)
    provenance = snapshot["provenance"]
    if (provenance["evidence_id"], provenance["position_id"], provenance["source_fingerprint"]) != (
        evidence,
        choice["position_id"],
        before["source_fingerprint"],
    ):
        raise ValueError("protection source changed")
    try:
        board = decision_board(db, position_row(db, before["position_id"]))
        if not history_known(board) or board.fen() != snapshot["prompt_fen"]:
            raise ValueError
        threat = probe(board)
        if threat is None:
            raise ValueError
        target = next(iter(threat["targets"]))
        _check_recorded_target(board, before, target)
        move = board.parse_uci(snapshot["lines"][0].split()[0])
        features = _features(board, move, board.piece_at(move.from_square), board.piece_at(target))
        features["mechanism"] = mechanism(board, move, target, threat)
    except (ValueError, TypeError, KeyError, IndexError, AttributeError, StopIteration):
        raise ContextUnavailable("protection teaching context unavailable") from None
    if (before, review) != current(
        db, evidence, subject, kind="material_protection", operation="prevent"
    ):
        raise ValueError("protection source changed")
    return {
        **snapshot,
        "features": features,
        "opening": _opening(db, before["position_id"]),
        "outcome": before["outcome"],
    }
