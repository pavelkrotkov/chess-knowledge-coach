"""Describe immediate material protection in explicitly bounded continuations."""

from .material_ambiguity import ambiguous
from .material_defense_guard import best_protects
from .material_defense_probe import candidate
from .material_defense_result import assess
from .material_lines import continuation, unopposed_material_loss


def defense_observation(board, played, best_line, played_line):
    probe = candidate(board, played)
    if probe is None or "outcome" in probe:
        return probe
    played_pv = continuation(board, played_line, played, allow_checks=True)
    best_pv = continuation(board, best_line)
    if played_pv is None:
        return ambiguous("material_protection", "continuation_unavailable")
    outcome = assess(board, probe, best_pv, played_pv)
    reason = _failure_reason(outcome, board, probe, best_pv, best_line, played_line)
    if reason:
        return ambiguous("material_protection", reason)
    return outcome


def _failure_reason(outcome, board, probe, best_pv, best_line, played_line):
    if outcome["outcome"] != "failure":
        return None
    if not best_protects(board, probe, best_pv):
        return "alternative_defense_unverified"
    if not unopposed_material_loss(best_line, played_line):
        return "engine_disagreement_or_compensation"
    return None
