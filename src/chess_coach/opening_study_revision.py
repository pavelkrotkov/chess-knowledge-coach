"""Resolve old and recommendation-bound opening courses without changing old versions."""

from .opening_revision_course import preview as legacy
from .opening_revision_roles import three_roles
from .opening_study_source import inputs


def current(db, root, learner, game, position, move, version, *, deadline, with_identity=False):
    value = legacy(
        db, root, learner, game, position, move, deadline=deadline, with_identity=with_identity
    )
    if value["version"] == version:
        return value
    updated = three_roles(value)
    if updated["version"] == version:
        return updated
    from .opening_recommendation_preview import preview

    try:
        return preview(
            db, root, learner, game, position, move, deadline=deadline, with_identity=with_identity
        )
    except FileNotFoundError as error:
        raise ValueError("opening preview version differs") from error


def watched(first, directory, root, budget, deadline):
    if "_deadline" in first:
        budget.expires = min(budget.expires, first["_deadline"])
        return first["_paths"], budget.expires
    return inputs(directory, first["_identity"], root), deadline
