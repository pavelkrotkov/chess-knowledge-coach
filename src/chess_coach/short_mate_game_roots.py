"""Resolve played and alternative roots within one bounded proof budget."""

from .short_mate_game_budget import checked_root, new_budget


def solve(board, moves, played, deadline, clock):
    move = board.parse_uci(played)
    budget = new_budget(clock, deadline)
    first = checked_root(board, move, budget)
    if first is None:
        return "unknown", "deadline"
    if first == "proved":
        return "preserved", None
    return _alternatives(board, moves, move, first, budget)


def _alternatives(board, moves, played, first, budget):
    uncertain = first == "unknown"
    for move in moves:
        if move == played:
            continue
        if budget.nodes >= budget.limit:
            return "unknown", "node_limit"
        result = checked_root(board, move, budget)
        if result is None:
            return "unknown", "deadline"
        if result == "proved":
            if first == "disproved":
                return "missed", None
            return "opportunity_unresolved", "played_move_unresolved"
        uncertain |= result == "unknown"
    return ("unknown", "proof_limit") if uncertain else ("no_opportunity", None)
