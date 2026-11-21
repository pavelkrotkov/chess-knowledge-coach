"""Read both exact branches within the existing browser budget."""

from .opening_fit_reference import sample


def samples(index, decision, moves, control, budget, source):
    result = {}
    for move in moves:
        budget.check()
        result[move] = sample(
            index[0],
            decision["catalog"]["parent"],
            move,
            decision["color"],
            control,
            budget.expires,
            decision_ply=decision["ply"],
            transform=index[2],
            source_metadata=index[3] if source == "recent" else None,
            match_context=source == "recent",
        )
    return result
