"""Reconstruct one explicitly selected current back-rank attacking root."""

from .back_rank_practice_attack import attacks
from .back_rank_scan import MAX_MOVES
from .decision_history import decision_board
from .mate_inspection_source import position_row
from .related_backrank_roots import roots as roots
from .related_backrank_snapshot import snapshot


def source_for_evidence(db, subject, evidence_id, root_move):
    evidence, fact, fingerprint, choices = roots(db, subject, evidence_id)
    root = _selected(choices, root_move)
    if len(root.get("defenses", [])) > MAX_MOVES:
        raise ValueError("back-rank reply limit exceeded")
    board = decision_board(db, position_row(db, evidence["position_id"]))
    lines = attacks(board, {"attack": {"alternatives": [root]}})
    _check_timing(lines, root["distance_plies"])
    return snapshot(db, board, evidence, fact, fingerprint, root_move, root, lines)


def _selected(choices, root_move):
    selected = [root for root in choices if root["move"]["uci"] == root_move]
    if len(selected) != 1:
        raise ValueError("selected back-rank root unavailable")
    return selected[0]


def _check_timing(lines, plies):
    if any(len(line.split()) != plies for line in lines):
        raise ValueError("selected back-rank timing unavailable")
