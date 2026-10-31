"""Derive a source example from a current owned full-history pin certificate."""

import chess

from .objective_pin_contract import VERSION
from .objective_pin_source import resolve
from .puzzle_session_validate import legal_move
from .related_capture_source import _opening
from .related_pin_contract import PIN_GEOMETRY_LIMIT, SOURCE_ROOT_PROOF_RESERVATION
from .related_pin_shape import features


def source_for_evidence(db, subject, evidence_id):
    reservation = {
        "root_proofs": SOURCE_ROOT_PROOF_RESERVATION,
        "pin_geometry_limit": PIN_GEOMETRY_LIMIT,
    }
    source = resolve(db, VERSION, str(evidence_id), subject)
    proof = source["provenance"]["pin_certificate"]
    board = chess.Board(source["prompt_fen"])
    move = board.parse_uci(proof["move"])
    branches = sorted(proof["branches"], key=lambda item: (item["reply"], item["capture"]))
    if not branches:
        raise ValueError("pin branch unavailable")
    branch = branches[0]
    _validate_branch(board, move, branch)
    source["features"] = features(board, move, proof)
    source["lines"] = [" ".join((move.uci(), branch["reply"], branch["capture"]))]
    source["opening"] = _opening(db, source["provenance"]["position_id"])
    source["outcome"] = source["provenance"]["source_outcome"]
    source["source_branch"] = branch
    source["source_work_reservation"] = reservation
    return source


def _validate_branch(board, move, branch):
    replay = board.copy(stack=True)
    replay.push(legal_move(replay, move.uci()))
    replay.push(legal_move(replay, branch["reply"]))
    capture = legal_move(replay, branch["capture"])
    if not replay.is_capture(capture):
        raise ValueError("pin branch capture unavailable")
    replay.push(capture)
    if replay.is_checkmate() != branch["mate"]:
        raise ValueError("pin branch changed")
