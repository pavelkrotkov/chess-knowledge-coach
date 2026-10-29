"""Bounded minimax intervals, with draw claims as optional actions."""

from dataclasses import dataclass, field

from .pawn_outcome_leaf import reset_value, terminal
from .pawn_outcome_walk import moves


@dataclass
class Budget:
    limit: int
    nodes: int = 0
    native_wdl: dict[str, int] = field(default_factory=dict)


def bounds(board, tablebase, budget, depth):
    """Return inclusive WDL bounds for the current player under optimal claims."""
    if budget.nodes >= budget.limit:
        return (-1, 1, "node_limit")
    budget.nodes += 1
    outcome = terminal(board)
    if outcome is not None:
        return outcome
    if board.halfmove_clock == 0:
        result = reset_value(board, tablebase)
        if result[2].startswith("wdl:"):
            budget.native_wdl[result[2]] = budget.native_wdl.get(result[2], 0) + 1
        return result
    if depth == 0:
        if board.can_claim_draw():
            return (0, 1, "draw_claim_and_depth_limit")
        return (-1, 1, "depth_limit")
    return moves(board, tablebase, budget, depth, bounds)
