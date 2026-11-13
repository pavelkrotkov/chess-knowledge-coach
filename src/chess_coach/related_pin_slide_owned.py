"""Revalidate the exact owned pin exposure and history."""

from .decision_history import decision_board
from .mate_inspection_source import position_row
from .objective_pin_prevent_existing import _matches
from .pin_exposure_geometry import exposed
from .related_pin_slide_proof import pin


def checked(db, source, bound):
    board = decision_board(db, position_row(db, source["provenance"]["position_id"]))
    named = pin(board)
    if board.fen() != source["prompt_fen"] or named is None or not _matches(named, bound):
        raise ValueError("named pin source changed")
    bad = board.parse_uci(bound["bad"])
    if bad not in board.legal_moves:
        raise ValueError("named exposure unavailable")
    if exposed(board, bad, [named]) != source["provenance"]["pin_witness"]:
        raise ValueError("named exposure changed")
    return board, named, bad
