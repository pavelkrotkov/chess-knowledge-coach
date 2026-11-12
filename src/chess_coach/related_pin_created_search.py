"""Search the bounded counterfactual roots for a proved matching contrast."""

from .pin_defense_success import MAX_COUNTERFACTUAL_ROOTS, MAX_ROOT_MOVES
from .related_pin_budget import take
from .related_pin_created_nominate import nominate
from .related_pin_created_proof import check


def search(board, good, source, budget):
    moves = list(board.legal_moves)
    if len(moves) > MAX_ROOT_MOVES:
        return None
    return _search(board, good, source, budget, moves)


def _search(board, good, source, budget, moves):
    counted = False
    for bad in moves[:MAX_COUNTERFACTUAL_ROOTS]:
        if bad == good:
            continue
        found = nominate(board, bad, source, budget)
        if found is None:
            continue
        if not counted and not take(budget, "lines"):
            return None
        counted = True
        result = check(board, good, bad, *found, source, budget)
        if result or budget["truncated"]:
            return result
    return None
