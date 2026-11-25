"""Read a selected recommendation from the existing private database."""

from .opening_profile_cli_db import private_database
from .opening_recommendation_preview import preview


def report(root, subject, game_id, position_id, alternative):
    with private_database(root, subject) as db:
        return preview(db, root, subject, game_id, position_id, alternative)
