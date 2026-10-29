"""Validate automatic mate scan bounds."""


def validate_mate_config(config):
    limits = ((config.mate_max_scan, 1, 1000), (config.mate_max_decisions, 1, 100))
    if type(config.mate_enabled) is not bool or any(
        type(value) is not int or not low <= value <= high for value, low, high in limits
    ):
        raise ValueError("invalid automatic mate budget")
