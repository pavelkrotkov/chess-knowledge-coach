"""Narrow central pawn geometry shared with existing structure features."""

import chess

from .structure_files import _open_files
from .structure_position import _locked_center


def features(board):
    contacts = []
    black = board.pieces(chess.PAWN, chess.BLACK)
    for white in board.pieces(chess.PAWN, chess.WHITE):
        for other in board.attacks(white) & black:
            if chess.square_file(white) in (3, 4) or chess.square_file(other) in (3, 4):
                contacts.append(f"{chess.square_name(white)}:{chess.square_name(other)}")
    return {
        "center_contacts": sorted(contacts),
        "center_open_files": [file for file in _open_files(board) if file in ("d", "e")],
        "center_locked": _locked_center(board),
    }
