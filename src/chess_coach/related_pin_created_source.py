"""Recheck the owned contrast without claiming its earlier threat origin."""

import chess

from .decision_history import decision_board
from .mate_inspection_source import position_row
from .objective_pin_prevent_budget import scope, take_answer
from .objective_pin_prevent_created import judge
from .objective_pin_prevent_preflight import reserve
from .related_capture_source import _opening
from .related_pin_contract import UnsupportedPinTransfer
from .related_pin_prevent_shape import features


def enrich(db, subject, source, bound):
    board = decision_board(db, position_row(db, source["provenance"]["position_id"]))
    if board.fen() != source["prompt_fen"]:
        raise ValueError("pin source position changed")
    bad, good = board.parse_uci(bound["bad"]), board.parse_uci(bound["good"])
    if bad == good or bad not in board.legal_moves or good not in board.legal_moves:
        raise UnsupportedPinTransfer("pin contrast unavailable")
    reserve(board)
    with scope():
        take_answer()
        bad_result = judge(board, bad, bound)
        take_answer()
        good_result = judge(board, good, bound)
    if bad_result[0] != "incorrect" or good_result[0] != "correct":
        raise UnsupportedPinTransfer("pin contrast unresolved")
    pin = {
        "type": bound["kind"],
        "pinned": chess.parse_square(bound["pinned"]),
        "rear": chess.parse_square(bound["rear"]),
    }
    source["features"] = {
        **features(board, good, chess.parse_square(bound["attacker"]), pin),
        "origin": "counterfactual",
    }
    source["opening"] = _opening(db, source["provenance"]["position_id"])
    source["outcome"] = source["provenance"]["source_outcome"]
    return source
