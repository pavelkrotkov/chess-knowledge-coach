"""Select the legacy or source-bound opening course without engine work."""

from .opening_revision_roles import preview as direct


def preview(db, root, learner, game, position, move, mode):
    if mode == "1":
        from .opening_recommendation_preview import preview as recommendation

        return recommendation(db, root, learner, game, position, move)
    return direct(db, root, learner, game, position, move)
