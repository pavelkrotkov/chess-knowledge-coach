"""Resolve one current owned protection source with its original target."""

import chess

from .decision_history import decision_board
from .mate_inspection_source import position_row
from .objective_capture_current import current
from .objective_protection_before import probe
from .objective_protection_contract import VERSION
from .objective_protection_source import resolve
from .related_capture_position import _features
from .related_capture_source import _opening
from .related_protection_mechanism import mechanism


def source_for_evidence(db, subject, evidence_id):
    before, review = current(
        db, evidence_id, subject, kind="material_protection", operation="prevent"
    )
    source = resolve(db, VERSION, str(evidence_id), subject)
    after, latest = current(
        db, evidence_id, subject, kind="material_protection", operation="prevent"
    )
    if (before, review) != (after, latest):
        raise ValueError("protection source changed")
    board = decision_board(db, position_row(db, before["position_id"]))
    move = board.parse_uci(source["lines"][0])
    target = chess.parse_square(source["provenance"]["objective_target"])
    source["features"] = _features(
        board, move, board.piece_at(move.from_square), board.piece_at(target)
    )
    threat = probe(board)
    if threat is None or set(threat["targets"]) != {target}:
        raise ValueError("protection threat changed")
    source["features"]["mechanism"] = mechanism(board, move, target, threat)
    source["opening"] = _opening(db, before["position_id"])
    source["outcome"] = before["outcome"]
    return source
