"""Compare a shelter change with one bounded legal alternative, without grading."""

import chess

from .king_safety_alternative import alternatives
from .king_safety_geometry import change
from .king_safety_scan import MAX_MOVES, scan, terminal
from .king_safety_witness import witness
from .material_lines import continuation

VERSION = "1.0.0"


def _move(board, played):
    if not board.is_valid():
        raise ValueError("invalid position")
    if terminal(board):
        raise ValueError("draw or terminal history is outside the verified scope")
    moves = list(board.legal_moves)
    if len(moves) > MAX_MOVES:
        raise ValueError("legal move limit exceeded")
    move = chess.Move.from_uci(played)
    if move not in moves:
        raise ValueError("recorded move is not legal")
    return move


def lesson(board, played, best, played_line):
    move = _move(board, played)
    geometry = change(board, move)
    if geometry is None:
        return None
    before, after = geometry
    current = scan(board, move)
    if current["status"] != "complete":
        raise ValueError("played move has unresolved or terminal replies")
    comparison = alternatives(board, move)
    candidate = comparison["selected"]
    current["reply_witness"] = witness(board, current)
    if candidate:
        candidate["reply_witness"] = witness(board, candidate)
    return {
        "version": VERSION,
        "before": before,
        "after": after,
        "played": current,
        "alternative": candidate,
        "alternative_coverage": {
            key: value for key, value in comparison.items() if key != "selected"
        },
        "recorded_lines": {
            "best": continuation(board, best, allow_checks=True),
            "played": continuation(board, played_line, played, allow_checks=True),
        },
        "uncertainty": "Zone attacks are geometric, including pinned pieces, and do not establish legal threats. These scans cover only immediate legal checks, captures and promotions; they do not prove overall safety, compensation, or a decision failure. Recorded continuations are possibilities, not forced lines.",
        "mastery_eligible": False,
    }
