"""Attach separate fit and development judgments to an inventory parent."""

from .opening_context_development import assess as development
from .opening_context_fit import assess as fit
from .opening_context_fit_inputs import attach as attach_fit


def annotate(
    group,
    db,
    root,
    subject,
    color,
    path,
    items,
    games,
    budget,
    verified,
    incomplete,
    annotation,
    owned_development,
):
    result = attach_fit(
        fit, group, db, root, subject, color, path, items, budget, verified, annotation
    )
    if annotation is None:
        result["development"] = development(
            db, subject, color, games, result, budget, incomplete, owned_development
        )
    return result
