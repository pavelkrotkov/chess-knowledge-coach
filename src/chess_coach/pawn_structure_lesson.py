"""Describe pawn plans and bounded legal continuations, without grading skill."""

import chess

from .pawn_structure_activity import activity
from .pawn_structure_geometry import geometry
from .pawn_structure_lines import line
from .structure_features import extract_features

VERSION = "1.1.0"


def _targets(board):
    features = extract_features(board)
    targets = []
    for kind in ("isolated", "backward"):
        for color in ("white", "black"):
            for square in features[f"{kind}_pawns"][color]:
                targets.append({"kind": kind, "color": color, "square": square})
    return targets


def _plans(target, mover):
    owner = target["color"] == mover
    if owner:
        return {
            "role": "defend",
            "plan": "Consider defending or advancing the pawn, and use the activity it can support.",
            "counterplan": "The opponent can consider blockading it and adding pressure along its file.",
        }
    return {
        "role": "attack",
        "plan": "Consider blockading the pawn and coordinating pressure against it.",
        "counterplan": "Its owner can seek an advance or active piece play as compensation.",
    }


def lesson(board, played, best, played_line):
    """Build descriptive lesson; a line is a possibility, never a forced result."""
    targets = _targets(board)
    if not targets:
        return None
    mover = "white" if board.turn == chess.WHITE else "black"
    for target in targets:
        target.update(_plans(target, mover))
        target.update(geometry(board, target))
    lines = {
        "best": line(board, best, None, targets),
        "played": line(board, played_line, played, targets),
    }
    return {
        "version": VERSION,
        "targets": targets,
        "lines": lines,
        "activity": activity(board, targets, lines),
        "consequence": "A listed capture shows one legal continuation and bounded target-square exchange, not a forced outcome.",
        "uncertainty": "Pawn geometry alone is not a mistake. Supported-piece exchanges are immediate and target-specific; overall activity, compensation, other defenses and later tactics are not assessed. Plans are ideas, not verified recommendations or evidence of skill.",
        "hypothesis": "Pressure on the pawn or activity for its owner may influence the choice; these possibilities are unverified.",
        "mastery_eligible": False,
    }
