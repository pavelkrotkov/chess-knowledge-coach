"""Record the measured rook entry and immediate responses."""

import chess

from .pawn_structure_immediate import _capture_status
from .rook_plan_activity import activity
from .rook_plan_geometry import entries

VERSION = "1.0.0"


def _root(board, line, source):
    move = board.parse_uci(line["uci"][0])
    after = board.copy()
    after.push(move)
    square = move.to_square if move.from_square == source else source
    piece = after.piece_at(square)
    if piece != chess.Piece(chess.ROOK, board.turn):
        return None
    return {
        "square": chess.square_name(square),
        "captures": _capture_status(after, square),
        "rook_attacks_enemy_half": activity(after, board.turn),
    }


def observation(board, move, features, color, kind, lines):
    source = move.from_square
    roots = {role: _root(board, value, source) for role, value in lines.items()}
    return {
        "version": VERSION,
        "color": color,
        "rook": chess.square_name(source),
        "file": chess.FILE_NAMES[chess.square_file(move.to_square)],
        "file_kind": kind,
        "entries": entries(board, source, features),
        "lines": lines,
        "roots": roots,
        "plan": "Consider using this file to reach an entry square or attack a target.",
        "counterplan": "The opponent can contest entry squares or capture an exposed rook.",
        "uncertainty": "Legal roots and immediate captures are local observations, not forced continuations, overall safety, positional advantage, intent or evidence of skill. Later tactics and compensation are not assessed.",
        "mastery_eligible": False,
    }
