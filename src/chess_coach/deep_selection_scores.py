"""Compare native, same-board scores solely for analysis nomination."""

from .decision_line_view import view_line
from .deep_selection_uncertainty import uncertainty_reasons
from .deep_selection_wdl import wdl_gap as wdl_difference


def score_reasons(position, board, lines, cp_gap, wdl_gap):
    if set(lines) != {"best", "played"}:
        return {"score_unavailable"}
    best = view_line(lines["best"], board, position["uci"])
    played = view_line(lines["played"], board, position["uci"])
    if best["status"] != "limited" or played["status"] != "limited":
        return {"score_unavailable"}
    if any(type(item["score_value"]) is not int for item in (best, played)):
        return {"score_unavailable"}
    uncertain = uncertainty_reasons(best, played)
    if uncertain:
        return uncertain
    return _gap_reasons(best, played, cp_gap, wdl_gap)


def _gap_reasons(best, played, cp_gap, wdl_gap):
    reasons = set()
    delta = best["score_value"] - played["score_value"]
    if delta >= cp_gap:
        reasons.add("cp_score_gap")
    elif delta <= -cp_gap:
        reasons.add("score_inversion")
    if wdl_difference(best["wdl"], played["wdl"], wdl_gap):
        reasons.add("wdl_score_gap")
    return reasons
