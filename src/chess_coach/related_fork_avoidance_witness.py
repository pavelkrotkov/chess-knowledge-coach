"""Find a bounded real-history bad move that creates the particular knight fork."""

from .fork_defense_probe import hypothetical
from .related_fork_avoidance_alternative import alternative
from .related_fork_prevention_budget import take


def witness(board, good, source, budget):
    before = hypothetical(board)
    if before is None:
        budget["unknown"] += 1
        return None
    for bad in board.legal_moves:
        if not take(budget, "anchors"):
            return None
        if bad == good:
            continue
        found = alternative(board, good, bad, before, source, budget)
        if found is not None or budget["truncated"]:
            return found
    return None
