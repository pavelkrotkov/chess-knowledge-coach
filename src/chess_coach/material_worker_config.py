"""Validate bounded material-observation worker settings."""


def validate_material_config(config):
    limits = ((config.material_max_scan, 1, 1000), (config.material_max_decisions, 1, 100))
    if type(config.material_enabled) is not bool or any(
        type(value) is not int or not low <= value <= high for value, low, high in limits
    ):
        raise ValueError("invalid material-observation budget")
