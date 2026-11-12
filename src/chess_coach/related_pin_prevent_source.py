"""Resolve a current owned capture of one proved existing pinner."""

from .decision_history import decision_board
from .mate_inspection_source import position_row
from .material_lines import material
from .objective_pin_prevent_contract import VERSION
from .objective_pin_prevent_existing import _matches
from .objective_pin_prevent_source import resolve
from .pin_capture import capture
from .pin_existing import existing
from .related_capture_source import _opening
from .related_pin_contract import UnsupportedPinTransfer
from .related_pin_prevent_shape import features


def source_for_evidence(db, subject, evidence_id):
    source = resolve(db, VERSION, str(evidence_id), subject)
    bound = source["provenance"]["pin_prevention"]
    if bound["origin"] != "existing":
        raise UnsupportedPinTransfer("existing pin source unavailable")
    board = decision_board(db, position_row(db, source["provenance"]["position_id"]))
    if board.fen() != source["prompt_fen"]:
        raise ValueError("pin source position changed")
    pins = existing(board)
    if len(pins) != 1 or not _matches(pins[0], bound):
        raise ValueError("named pin source unavailable")
    move = board.parse_uci(bound["good"])
    attacker, pin = pins[0]
    if move.to_square != attacker:
        raise UnsupportedPinTransfer("pinner capture unavailable")
    if not capture(board, move.from_square, attacker, board.turn, material(board, board.turn)):
        raise UnsupportedPinTransfer("pinner capture unproved")
    source["features"] = features(board, move, attacker, pin)
    source["opening"] = _opening(db, source["provenance"]["position_id"])
    source["outcome"] = source["provenance"]["source_outcome"]
    return source
