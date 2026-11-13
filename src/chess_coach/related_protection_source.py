"""Resolve one current owned protection source with its original target."""

import chess

from .objective_protection_before import probe
from .objective_protection_contract import VERSION
from .objective_protection_source import resolve_details
from .related_capture_position import _features
from .related_capture_source import _opening
from .related_protection_mechanism import mechanism


def source_for_evidence(db, subject, evidence_id):
    if type(evidence_id) is not int or not 0 < evidence_id < 2**63:
        raise ValueError("protection source unavailable")
    source, before, board = resolve_details(db, VERSION, str(evidence_id), subject)
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
