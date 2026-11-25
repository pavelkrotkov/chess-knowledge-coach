"""Select the legacy or source-bound opening course without engine work."""

from .opening_revision_course import preview as legacy


def preview(db, root, learner, game, position, move, mode):
    if mode == "1":
        from .opening_recommendation_preview import preview as recommendation

        return recommendation(db, root, learner, game, position, move)
    return legacy(db, root, learner, game, position, move)
