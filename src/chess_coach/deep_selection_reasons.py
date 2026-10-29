"""Nominate observations without mapping engine losses to skill evidence."""

from .deep_selection_scores import score_reasons
from .motif_detectors import detect_motifs
from .tactical_rules import mate_in_one_fact


def decision_reasons(position, board, lines, cp_gap, wdl_gap):
    reasons = score_reasons(position, board, lines, cp_gap, wdl_gap)
    motifs = {item["motif"] for item in detect_motifs(board)}
    reasons.update("possible_" + motif for motif in motifs)
    if mate_in_one_fact(board.fen(), position["uci"]) is not None:
        reasons.add("mate_in_one_available")
    return sorted(reasons)
