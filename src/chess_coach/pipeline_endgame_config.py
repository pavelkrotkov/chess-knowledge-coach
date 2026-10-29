"""Validate the independent automatic endgame worker budgets."""

from .mate_worker_config import validate_mate_config
from .pawn_coach_config import validate_pawn_config


def validate_endgame_config(config):
    validate_mate_config(config)
    validate_pawn_config(config)
