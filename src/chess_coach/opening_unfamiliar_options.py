"""Recheck a small group of unfamiliar catalog moves under one source guard."""

from .opening_storage import position_key
from .opening_unfamiliar import prepare
from .opening_unfamiliar_guard import check, start
from .opening_unfamiliar_history import seen
from .opening_unfamiliar_public import public
from .opening_unfamiliar_sources import choices

LIMIT = 3


def available(db, root, subject, dataset, board, color, budget, move=None):
    parent = position_key(board)
    with budget.scope(snapshot=True):
        options = choices(db, dataset, board)
    result = []
    for item in options:
        if move is not None and item["uci"] != move:
            continue
        with budget.scope(snapshot=True):
            familiar = seen(db, subject, item, color, parent)
        if familiar:
            continue
        reference = public(root, subject, parent, item["uci"], budget)
        if reference:
            line, data = reference
            result.append({**item, "line": line, "profile": data})
        if len(result) == (1 if move is not None else LIMIT):
            break
    budget.check()
    return result


def group(db, root, learner, *, include_fit=False):
    from .learner_identity import normalize_identity

    subject = normalize_identity(learner)
    guard = start(db, root, subject)
    budget, subject, dataset, report, white, black = prepare(db, learner)
    items = {}
    for color, board, enabled in (
        ("white", white, report["white_count"]),
        ("black", black, report["parent"]),
    ):
        values = available(db, root, subject, dataset, board, color, budget) if enabled else []
        items[color] = [
            {
                "selection": {"color": color, "parent": position_key(board), "move": item["uci"]},
                **item,
            }
            for item in values
        ]
    # Fit is a choices-page annotation, not part of versioned course content.
    if include_fit:
        from .opening_fit import assess

        black_parent = black.peek().uci() if black.move_stack else None
        report["fit"] = assess(db, subject, guard, budget, items, black_parent)
        if report["fit"]["status"] != "deferred":
            for color in ("white", "black"):
                recommended = report["fit"]["colors"].get(color, {}).get("recommended")
                if recommended:
                    items[color].sort(key=lambda item: item["uci"] != recommended)
    check(db, root, subject, guard, budget)
    return {**report, "public_index_identity": list(guard[2])}, items
