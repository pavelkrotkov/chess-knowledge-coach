"""Collect one color's checked context candidates and requested annotations."""

from .opening_context_candidates import choices
from .opening_context_choice import token
from .opening_context_fit import assess as fit
from .opening_context_fit_inputs import attach
from .opening_context_history import ordered
from .opening_context_owned_measure import enrich as owned_comparison
from .opening_distance_history import history
from .opening_distance_inventory import enrich
from .opening_public_comparison_read import enrich as comparison


def _requested(items, annotation):
    if annotation is False:
        return []
    if annotation in (None, ""):
        return items
    return [item for item in items if token(item["selection"]) == annotation]


def collect(
    db, root, subject, dataset, color, contexts, sample, budget, index, identity, annotation
):
    games, seen, incomplete, history_verified = sample
    selected, omitted, tied = ordered(contexts)
    checked_history = (
        history(db, subject, color, budget) if selected and annotation is None else None
    )
    history_ready = annotation is None
    parents = []
    for (parent, path), count in selected:
        found = choices(
            db, root, subject, dataset, color, parent, path, seen, incomplete, budget, index
        )
        for item in found["items"]:
            item["selection"].update(identity)
        items = _requested(found["items"], annotation)
        if items:
            if not history_ready:
                checked_history = history(db, subject, color, budget)
                history_ready = True
            enrich(items, checked_history, budget, index)
            owned_comparison(db, root, subject, games, color, parent, path, items, budget)
            comparison(root, subject, items, index, budget)
        group = {"parent": parent, "path": list(path), "occurrences": count, **found}
        parents.append(
            attach(
                fit,
                group,
                db,
                root,
                subject,
                color,
                path,
                items,
                budget,
                history_verified,
                annotation,
            )
        )
    return {
        "parents": parents,
        "omitted": omitted,
        "truncated": bool(omitted),
        "boundary_tie": tied,
    }
