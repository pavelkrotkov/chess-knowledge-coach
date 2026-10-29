"""Describe a bounded legal choice against a concrete fork threat."""

from .fork_defense_failure import failure
from .fork_defense_probe import hypothetical
from .fork_defense_safety import safe_material
from .fork_defense_scan import scan
from .fork_defense_success import success
from .material_ambiguity import ambiguous


def observe(board, played, best_line, played_line):
    candidates = hypothetical(board)
    if candidates is None:
        return ambiguous("fork_defense", "hypothetical_probe_unavailable")
    try:
        actual = board.parse_uci(played)
    except ValueError:
        return ambiguous("fork_defense", "invalid_played_move")
    if actual not in board.legal_moves:
        return ambiguous("fork_defense", "invalid_played_move")
    if board.is_capture(actual) or board.gives_check(actual) or actual.promotion:
        return ambiguous("fork_defense", "forcing_defense_unresolved") if candidates else None
    return _assess(board, actual, best_line, played_line, candidates)


def _assess(board, actual, best_line, played_line, candidates):
    after = board.copy()
    after.push(actual)
    following = scan(after)
    if following is None or following["uncertain"]:
        return ambiguous("fork_defense", "post_move_fork_unresolved")
    if not safe_material(after):
        return ambiguous("fork_defense", "post_move_material_threat")
    if not following["proven"]:
        return success(board, actual, played_line, candidates) if candidates else None
    return failure(board, actual, best_line, played_line, candidates, following)
