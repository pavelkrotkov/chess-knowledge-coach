"""Validate the pawn worker's independent resource budget."""


def validate_pawn_config(config):
    limits = ((config.pawn_max_scan, 1, 1000), (config.pawn_max_decisions, 1, 100))
    if type(config.pawn_enabled) is not bool or any(
        type(value) is not int or not low <= value <= high for value, low, high in limits
    ):
        raise ValueError("invalid pawn-observation budget")
